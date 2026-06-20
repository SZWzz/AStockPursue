// Package feed provides real-time market data via WebSocket connections.
// Supports OKX and EastMoney exchanges with automatic reconnection.
package feed

import (
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// Bar represents a real-time OHLCV bar received via WebSocket.
type Bar struct {
	Symbol    string
	Open      float64
	High      float64
	Low       float64
	Close     float64
	Volume    float64
	Timestamp time.Time
}

// BarHandler is called for each new bar received from the feed.
type BarHandler func(bar Bar)

// ErrorHandler is called when the feed encounters an error.
type ErrorHandler func(symbol string, err error)

// MarketFeed is the interface for real-time market data feeds.
type MarketFeed interface {
	// Name returns the feed identifier.
	Name() string
	// Connect establishes the WebSocket connection.
	Connect() error
	// Subscribe starts receiving data for the given symbols.
	Subscribe(symbols []string) error
	// Unsubscribe stops receiving data for the given symbols.
	Unsubscribe(symbols []string) error
	// Close shuts down the feed.
	Close() error
	// OnBar registers a handler for incoming bars.
	OnBar(handler BarHandler)
	// OnError registers a handler for feed errors.
	OnError(handler ErrorHandler)
}

// ── OKX WebSocket Feed ────────────────────────────────────────────

// OKXFeed receives real-time candlestick data from OKX WebSocket API.
// Documentation: https://www.okx.com/docs-v5/en/#websocket-api-public-channel-candlesticks-channel
type OKXFeed struct {
	url       string
	interval  string // "1H", "5m", "15m", etc.
	conn      *websocket.Conn
	mu        sync.Mutex
	subs      map[string]bool
	barCb     BarHandler
	errCb     ErrorHandler
	done      chan struct{}
	reconnect bool
}

type okxWSMessage struct {
	Event string          `json:"event,omitempty"`
	Arg   okxWSArg        `json:"arg,omitempty"`
	Data  [][]string      `json:"data,omitempty"`
}

type okxWSArg struct {
	Channel  string `json:"channel"`
	InstID   string `json:"instId"`
}

// NewOKXFeed creates a new OKX WebSocket feed for the given interval.
// Interval format: "1H", "4H", "1D", "5m", "15m", "1m".
func NewOKXFeed(interval string) *OKXFeed {
	if interval == "" {
		interval = "1H"
	}
	return &OKXFeed{
		url:       "wss://ws.okx.com:8443/ws/v5/public",
		interval:  interval,
		subs:      make(map[string]bool),
		done:      make(chan struct{}),
		reconnect: true,
	}
}

func (f *OKXFeed) Name() string { return "okx" }

func (f *OKXFeed) OnBar(handler BarHandler)   { f.barCb = handler }
func (f *OKXFeed) OnError(handler ErrorHandler) { f.errCb = handler }

func (f *OKXFeed) Connect() error {
	conn, _, err := websocket.DefaultDialer.Dial(f.url, nil)
	if err != nil {
		return fmt.Errorf("okx feed connect: %w", err)
	}
	f.conn = conn

	// Subscribe to already-registered symbols
	if len(f.subs) > 0 {
		symbols := make([]string, 0, len(f.subs))
		for s := range f.subs {
			symbols = append(symbols, s)
		}
		f.subscribe(symbols)
	}

	go f.readLoop()
	return nil
}

func (f *OKXFeed) Subscribe(symbols []string) error {
	f.mu.Lock()
	for _, s := range symbols {
		f.subs[s] = true
	}
	f.mu.Unlock()
	if f.conn != nil {
		return f.subscribe(symbols)
	}
	return nil
}

func (f *OKXFeed) Unsubscribe(symbols []string) error {
	f.mu.Lock()
	for _, s := range symbols {
		delete(f.subs, s)
	}
	f.mu.Unlock()
	if f.conn != nil {
		return f.unsubscribe(symbols)
	}
	return nil
}

func (f *OKXFeed) Close() error {
	f.reconnect = false
	close(f.done)
	if f.conn != nil {
		return f.conn.Close()
	}
	return nil
}

func (f *OKXFeed) subscribe(symbols []string) error {
	args := make([]okxWSArg, len(symbols))
	for i, s := range symbols {
		args[i] = okxWSArg{Channel: "candle" + f.interval, InstID: f.toOKXInstID(s)}
	}
	return f.conn.WriteJSON(okxWSMessage{Event: "subscribe", Arg: args[0]})
}

func (f *OKXFeed) unsubscribe(symbols []string) error {
	args := make([]okxWSArg, len(symbols))
	for i, s := range symbols {
		args[i] = okxWSArg{Channel: "candle" + f.interval, InstID: f.toOKXInstID(s)}
	}
	return f.conn.WriteJSON(okxWSMessage{Event: "unsubscribe", Arg: args[0]})
}

func (f *OKXFeed) readLoop() {
	defer func() {
		if f.reconnect {
			log.Printf("okx feed: reconnecting in 5s...")
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
				f.errCb("", fmt.Errorf("okx feed read: %w", err))
			}
			return
		}

		var wsMsg okxWSMessage
		if err := json.Unmarshal(msg, &wsMsg); err != nil {
			continue
		}

		// Parse candle data: [[ts, open, high, low, close, vol, ...], ...]
		for _, candle := range wsMsg.Data {
			if len(candle) < 6 {
				continue
			}
			ts, _ := parseInt64(candle[0])
			open, _ := parseFloat(candle[1])
			high, _ := parseFloat(candle[2])
			low, _ := parseFloat(candle[3])
			close, _ := parseFloat(candle[4])
			vol, _ := parseFloat(candle[5])

			if f.barCb != nil {
				f.barCb(Bar{
					Symbol:    f.fromOKXInstID(wsMsg.Arg.InstID),
					Open:      open,
					High:      high,
					Low:       low,
					Close:     close,
					Volume:    vol,
					Timestamp: time.UnixMilli(ts),
				})
			}
		}
	}
}

// toOKXInstID converts e.g. "BTC-USDT" → "BTC-USDT-SWAP"
func (f *OKXFeed) toOKXInstID(symbol string) string {
	return symbol + "-SWAP"
}

// fromOKXInstID converts e.g. "BTC-USDT-SWAP" → "BTC-USDT"
func (f *OKXFeed) fromOKXInstID(instID string) string {
	if len(instID) > 5 && instID[len(instID)-5:] == "-SWAP" {
		return instID[:len(instID)-5]
	}
	return instID
}

// ── Helpers ───────────────────────────────────────────────────────

func parseInt64(s string) (int64, error) {
	var v int64
	_, err := fmt.Sscanf(s, "%d", &v)
	return v, err
}

func parseFloat(s string) (float64, error) {
	var v float64
	_, err := fmt.Sscanf(s, "%f", &v)
	return v, err
}
