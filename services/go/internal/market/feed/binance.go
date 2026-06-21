package feed

import (
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// BinanceFeed receives real-time kline data from Binance WebSocket.
// URL: wss://stream.binance.com:9443/ws
type BinanceFeed struct {
	url       string
	interval  string
	conn      *websocket.Conn
	mu        sync.Mutex
	subs      map[string]bool
	barCb     BarHandler
	errCb     ErrorHandler
	done      chan struct{}
	reconnect bool
	reqID     int
}

type binanceKlineMsg struct {
	EventType string `json:"e"`
	EventTime int64  `json:"E"`
	Symbol    string `json:"s"`
	Kline     struct {
		StartTime int64  `json:"t"`
		CloseTime int64  `json:"T"`
		Symbol    string `json:"s"`
		Interval  string `json:"i"`
		Open      string `json:"o"`
		High      string `json:"h"`
		Low       string `json:"l"`
		Close     string `json:"c"`
		Volume    string `json:"v"`
	} `json:"k"`
}

// NewBinanceFeed creates a new Binance WebSocket feed.
// Default interval is "1m".
func NewBinanceFeed(interval ...string) *BinanceFeed {
	iv := "1m"
	if len(interval) > 0 && interval[0] != "" {
		iv = interval[0]
	}
	return &BinanceFeed{
		url:       "wss://stream.binance.com:9443/ws",
		interval:  iv,
		subs:      make(map[string]bool),
		done:      make(chan struct{}),
		reconnect: true,
	}
}

func (f *BinanceFeed) Name() string { return "binance" }

func (f *BinanceFeed) OnBar(handler BarHandler)   { f.barCb = handler }
func (f *BinanceFeed) OnError(handler ErrorHandler) { f.errCb = handler }

func (f *BinanceFeed) Connect() error {
	conn, _, err := websocket.DefaultDialer.Dial(f.url, nil)
	if err != nil {
		return fmt.Errorf("binance feed connect: %w", err)
	}
	f.conn = conn

	if len(f.subs) > 0 {
		symbols := make([]string, 0, len(f.subs))
		for s := range f.subs {
			symbols = append(symbols, s)
		}
		_ = f.subscribe(symbols)
	}

	go f.readLoop()
	return nil
}

func (f *BinanceFeed) Subscribe(symbols []string) error {
	f.mu.Lock()
	for _, s := range symbols {
		f.subs[strings.ToLower(s)] = true
	}
	f.mu.Unlock()
	if f.conn != nil {
		return f.subscribe(symbols)
	}
	return nil
}

func (f *BinanceFeed) Unsubscribe(symbols []string) error {
	f.mu.Lock()
	for _, s := range symbols {
		delete(f.subs, strings.ToLower(s))
	}
	f.mu.Unlock()
	if f.conn != nil {
		return f.unsubscribe(symbols)
	}
	return nil
}

func (f *BinanceFeed) Close() error {
	f.reconnect = false
	close(f.done)
	if f.conn != nil {
		return f.conn.Close()
	}
	return nil
}

func (f *BinanceFeed) subscribe(symbols []string) error {
	params := make([]string, len(symbols))
	for i, s := range symbols {
		params[i] = binanceStreamName(s, f.interval)
	}
	f.reqID++
	return f.conn.WriteJSON(map[string]interface{}{
		"method": "SUBSCRIBE",
		"params": params,
		"id":     f.reqID,
	})
}

func (f *BinanceFeed) unsubscribe(symbols []string) error {
	params := make([]string, len(symbols))
	for i, s := range symbols {
		params[i] = binanceStreamName(s, f.interval)
	}
	f.reqID++
	return f.conn.WriteJSON(map[string]interface{}{
		"method": "UNSUBSCRIBE",
		"params": params,
		"id":     f.reqID,
	})
}

func (f *BinanceFeed) readLoop() {
	defer func() {
		if f.reconnect {
			log.Printf("binance feed: reconnecting in 5s...")
			time.Sleep(5 * time.Second)
			if err := f.Connect(); err != nil && f.errCb != nil {
				f.errCb("", err)
			}
		}
	}()

	for {
		select {
		case <-f.done:
			return
		default:
		}

		_, msg, err := f.conn.ReadMessage()
		if err != nil {
			if f.errCb != nil {
				f.errCb("", fmt.Errorf("binance feed read: %w", err))
			}
			return
		}

		// Binance sends kline data either wrapped in a stream object or directly
		var kline binanceKlineMsg
		if err := json.Unmarshal(msg, &kline); err != nil {
			// Try stream-wrapped format: {"stream":"...","data":{...}}
			var wrapped struct {
				Data binanceKlineMsg `json:"data"`
			}
			if err2 := json.Unmarshal(msg, &wrapped); err2 != nil {
				continue
			}
			kline = wrapped.Data
		}

		if kline.Kline.Symbol == "" {
			continue
		}

		open := parseFloatStr(kline.Kline.Open)
		high := parseFloatStr(kline.Kline.High)
		low := parseFloatStr(kline.Kline.Low)
		close := parseFloatStr(kline.Kline.Close)
		vol := parseFloatStr(kline.Kline.Volume)

		if f.barCb != nil {
			f.barCb(Bar{
				Symbol:    strings.ToUpper(kline.Kline.Symbol),
				Open:      open,
				High:      high,
				Low:       low,
				Close:     close,
				Volume:    vol,
				Timestamp: time.UnixMilli(kline.Kline.CloseTime),
			})
		}
	}
}

// binanceStreamName formats a symbol and interval into a Binance stream name.
// e.g. ("btcusdt", "1m") → "btcusdt@kline_1m"
func binanceStreamName(symbol, interval string) string {
	clean := strings.ToLower(strings.ReplaceAll(symbol, "-", ""))
	return fmt.Sprintf("%s@kline_%s", clean, interval)
}

// parseFloatStr parses a string to float64, returning 0 on failure.
func parseFloatStr(s string) float64 {
	var v float64
	_, _ = fmt.Sscanf(s, "%f", &v)
	return v
}
