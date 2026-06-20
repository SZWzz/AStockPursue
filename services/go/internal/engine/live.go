package engine

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"
)

// TradingStatus represents the state of a live trading session.
type TradingStatus string

const (
	TradingStopped TradingStatus = "stopped"
	TradingRunning TradingStatus = "running"
	TradingPaused  TradingStatus = "paused"
)

// ── Interfaces (defined here to avoid import cycles) ──────────────

// BrokerExecutor abstracts broker operations for live order execution.
type BrokerExecutor interface {
	PlaceOrder(ctx context.Context, symbol string, side string, orderType string, quantity float64, price float64) (*BrokerOrder, error)
	GetPositions(ctx context.Context) ([]*BrokerPosition, error)
}

type BrokerOrder struct {
	OrderID, Symbol, Side, Status string
	FilledQty, FilledPrice        float64
}

type BrokerPosition struct {
	Symbol        string
	Quantity      float64
	AvgPrice      float64
	CurrentPrice  float64
	UnrealizedPnL float64
}

// BarFetcher abstracts data retrieval for polling mode.
type BarFetcher interface {
	GetBars(symbol string, start, end time.Time, freq string) ([]BarData, error)
}

type BarData struct {
	Symbol                        string
	Open, High, Low, Close        float64
	Volume                        int64
	Timestamp                     time.Time
}

// FeedHandler receives real-time bars from push-based market data.
type FeedHandler interface {
	Connect() error
	Subscribe(symbols []string) error
	Close() error
	OnBar(func(symbol string, open, high, low, close, volume float64, ts time.Time))
	OnError(func(symbol string, err error))
}

// ── LiveTradingRunner ─────────────────────────────────────────────

// TrackedOrder is a lightweight record of a placed order.
type TrackedOrder struct {
	OrderID    string  `json:"order_id"`
	Symbol     string  `json:"symbol"`
	Side       string  `json:"side"`
	OrderType  string  `json:"order_type"`
	Quantity   float64 `json:"quantity"`
	Price      float64 `json:"price"`
	FilledQty  float64 `json:"filled_qty"`
	Status     string  `json:"status"`
	CreatedAt  string  `json:"created_at"`
}

type LiveTradingRunner struct {
	mu       sync.RWMutex
	status   TradingStatus
	pipeline *Pipeline
	interval time.Duration
	stopCh   chan struct{}

	fetcher  BarFetcher
	feed     FeedHandler
	broker   BrokerExecutor
	symbols  []string
	freq     string

	orders     []TrackedOrder
	orderCount int

	OnBarResult func(symbol string, equity float64)
	OnError     func(err error)
}

func NewLiveTradingRunner(pipeline *Pipeline, interval time.Duration) *LiveTradingRunner {
	return &LiveTradingRunner{
		status:   TradingStopped,
		pipeline: pipeline,
		interval: interval,
	}
}

func (l *LiveTradingRunner) WithFetcher(f BarFetcher, symbols []string, freq string) *LiveTradingRunner {
	l.fetcher = f
	l.symbols = symbols
	l.freq = freq
	return l
}

func (l *LiveTradingRunner) WithFeed(f FeedHandler) *LiveTradingRunner {
	l.feed = f
	return l
}

func (l *LiveTradingRunner) WithBroker(b BrokerExecutor) *LiveTradingRunner {
	l.broker = b
	return l
}

func (l *LiveTradingRunner) Start() error {
	l.mu.Lock()
	defer l.mu.Unlock()

	if l.status == TradingRunning {
		return nil
	}
	l.status = TradingRunning
	l.stopCh = make(chan struct{})

	if l.feed != nil {
		return l.startFeed()
	}
	return l.startPoll()
}

func (l *LiveTradingRunner) Stop() error {
	l.mu.Lock()
	defer l.mu.Unlock()

	if l.status != TradingRunning {
		return nil
	}
	l.status = TradingStopped
	close(l.stopCh)
	if l.feed != nil {
		l.feed.Close()
	}
	log.Print("live trading stopped")
	return nil
}

func (l *LiveTradingRunner) Status() TradingStatus {
	l.mu.RLock()
	defer l.mu.RUnlock()
	return l.status
}

func (l *LiveTradingRunner) Portfolio() *Portfolio {
	l.mu.RLock()
	defer l.mu.RUnlock()
	return l.pipeline.Portfolio
}

func (l *LiveTradingRunner) ExecuteOrder(ctx context.Context, order *Order) (*BrokerOrder, error) {
	if l.broker == nil {
		return nil, fmt.Errorf("broker not connected")
	}
	result, err := l.broker.PlaceOrder(ctx, order.Symbol, string(order.Side), string(order.Type), order.Quantity, order.Price)
	if err == nil && result != nil {
		l.recordOrder(order, result)
	}
	return result, err
}

func (l *LiveTradingRunner) recordOrder(order *Order, result *BrokerOrder) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.orderCount++
	tracked := TrackedOrder{
		OrderID:   fmt.Sprintf("ord-%d", l.orderCount),
		Symbol:    order.Symbol,
		Side:      string(order.Side),
		OrderType: string(order.Type),
		Quantity:  order.Quantity,
		Price:     order.Price,
		FilledQty: result.FilledQty,
		Status:    result.Status,
		CreatedAt: time.Now().Format(time.RFC3339),
	}
	l.orders = append(l.orders, tracked)
}

func (l *LiveTradingRunner) Orders() []TrackedOrder {
	l.mu.RLock()
	defer l.mu.RUnlock()
	result := make([]TrackedOrder, len(l.orders))
	copy(result, l.orders)
	return result
}

func (l *LiveTradingRunner) SyncPositions(ctx context.Context) error {
	if l.broker == nil {
		return nil
	}
	positions, err := l.broker.GetPositions(ctx)
	if err != nil {
		return err
	}
	l.mu.Lock()
	defer l.mu.Unlock()
	for _, bp := range positions {
		pos, ok := l.pipeline.Portfolio.Positions[bp.Symbol]
		if !ok && bp.Quantity != 0 {
			pos = &Position{Symbol: bp.Symbol}
			l.pipeline.Portfolio.Positions[bp.Symbol] = pos
		}
		if pos != nil {
			pos.CurrentPrice = bp.CurrentPrice
		}
	}
	return nil
}

// ── Private ───────────────────────────────────────────────────────

func (l *LiveTradingRunner) startPoll() error {
	log.Printf("live trading started (poll interval=%s, symbols=%v)", l.interval, l.symbols)
	go l.pollLoop()
	return nil
}

func (l *LiveTradingRunner) startFeed() error {
	l.feed.OnBar(func(symbol string, open, high, low, close, volume float64, ts time.Time) {
		eb := &Bar{Symbol: symbol, Open: open, High: high, Low: low, Close: close, Volume: int64(volume)}
		l.pipeline.OnBar(eb, ts)
		if l.OnBarResult != nil {
			l.OnBarResult(symbol, l.pipeline.Portfolio.Equity)
		}
	})
	l.feed.OnError(func(symbol string, err error) {
		if l.OnError != nil {
			l.OnError(err)
		}
	})
	if err := l.feed.Connect(); err != nil {
		return err
	}
	if len(l.symbols) > 0 {
		if err := l.feed.Subscribe(l.symbols); err != nil {
			return err
		}
	}
	log.Printf("live trading started (feed mode, symbols=%v)", l.symbols)
	return nil
}

func (l *LiveTradingRunner) pollLoop() {
	ticker := time.NewTicker(l.interval)
	defer ticker.Stop()
	var lastTS int64
	for {
		select {
		case <-l.stopCh:
			return
		case <-ticker.C:
			if l.fetcher != nil {
				end := time.Now()
				for _, sym := range l.symbols {
					bars, err := l.fetcher.GetBars(sym, end.Add(-l.interval*2), end, l.freq)
					if err != nil {
						if l.OnError != nil {
							l.OnError(err)
						}
						continue
					}
					for _, b := range bars {
						if b.Timestamp.UnixMilli() > lastTS {
							lastTS = b.Timestamp.UnixMilli()
							eb := &Bar{Symbol: b.Symbol, Open: b.Open, High: b.High, Low: b.Low, Close: b.Close, Volume: b.Volume}
							l.pipeline.OnBar(eb, b.Timestamp)
							if l.OnBarResult != nil {
								l.OnBarResult(sym, l.pipeline.Portfolio.Equity)
							}
						}
					}
				}
			}
		}
	}
}
