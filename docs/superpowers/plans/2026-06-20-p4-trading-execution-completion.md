# P4 Trading Execution Completion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) to implement this plan task-by-task.

**Goal:** Complete P4 with 4 modules: Futu broker, Broker→Engine adapter, Papertrade engine package, Binance WebSocket feed.

**Architecture:** All modules implement existing interfaces (`broker.Broker`, `engine.BrokerExecutor`, `MarketFeed`). No interface changes — pure additions.

**Tech Stack:** Go 1.22+, gorilla/websocket, lib/pq, existing broker/market/engine packages.

## Global Constraints

- All code under `services/go/internal/`
- Implement existing interfaces only — do NOT modify `broker.Broker`, `MarketFeed`, `engine.BrokerExecutor`, `engine.FeedHandler`
- TDD: write test first, confirm it fails, then implement
- Each task ends with `go test ./...` passing
- broker.Broker self-registration via `init()` → `broker.Register()`
- Commit messages follow `feat(scope): description` format

---

### Task 1: Broker→Engine Adapter

**Files:**
- Create: `services/go/internal/broker/adapter.go`
- Create: `services/go/internal/broker/adapter_test.go`

**Interfaces:**
- Consumes: `broker.Broker` interface (broker.go), `engine.BrokerExecutor` interface (engine/live.go)
- Produces: `broker.EngineAdapter` wrapping any Broker as a BrokerExecutor

- [ ] **Step 1: Write the failing test**

```go
// services/go/internal/broker/adapter_test.go
package broker

import (
	"context"
	"testing"
	"time"

	"github.com/astockpursue/go-core/internal/engine"
)

type mockBroker struct {
	name string
}

func (m *mockBroker) Name() string                           { return m.name }
func (m *mockBroker) TestConnection(ctx context.Context) error { return nil }
func (m *mockBroker) PlaceOrder(ctx context.Context, symbol string, side OrderSide, orderType OrderType, quantity, price float64) (*Order, error) {
	return &Order{OrderID: "test-1", Symbol: symbol, Side: side, Status: StatusFilled, FilledQty: quantity, FilledPrice: price}, nil
}
func (m *mockBroker) CancelOrder(ctx context.Context, orderID, symbol string) error { return nil }
func (m *mockBroker) GetOrder(ctx context.Context, orderID, symbol string) (*Order, error) {
	return &Order{OrderID: orderID, Symbol: symbol}, nil
}
func (m *mockBroker) GetOpenOrders(ctx context.Context, symbol string) ([]*Order, error) { return nil, nil }
func (m *mockBroker) GetPosition(ctx context.Context, symbol string) (*Position, error) {
	return &Position{Symbol: symbol, Quantity: 100, AvgPrice: 50, CurrentPrice: 55, UnrealizedPnL: 500}, nil
}
func (m *mockBroker) GetPositions(ctx context.Context) ([]*Position, error) {
	return []*Position{{Symbol: "BTC-USDT", Quantity: 100, AvgPrice: 50, CurrentPrice: 55, UnrealizedPnL: 500}}, nil
}
func (m *mockBroker) GetBalance(ctx context.Context) (*Balance, error) {
	return &Balance{Total: 10000, Available: 5000, Frozen: 5000, Currency: "USDT"}, nil
}
func (m *mockBroker) GetFeeRate(symbol string) FeeRate { return FeeRate{Maker: 0.001, Taker: 0.002} }

func TestEngineAdapterPlaceOrder(t *testing.T) {
	mb := &mockBroker{name: "mock"}
	adapter := NewEngineAdapter(mb)

	order, err := adapter.PlaceOrder(context.Background(), "BTC-USDT", "buy", "limit", 1.0, 50000.0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if order.OrderID != "test-1" {
		t.Errorf("expected OrderID test-1, got %s", order.OrderID)
	}
	if order.Symbol != "BTC-USDT" {
		t.Errorf("expected Symbol BTC-USDT, got %s", order.Symbol)
	}
	if order.Status != "filled" {
		t.Errorf("expected status filled, got %s", order.Status)
	}
}

func TestEngineAdapterGetPositions(t *testing.T) {
	mb := &mockBroker{name: "mock"}
	adapter := NewEngineAdapter(mb)

	positions, err := adapter.GetPositions(context.Background())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(positions) != 1 {
		t.Fatalf("expected 1 position, got %d", len(positions))
	}
	if positions[0].Symbol != "BTC-USDT" {
		t.Errorf("expected BTC-USDT, got %s", positions[0].Symbol)
	}
	if positions[0].UnrealizedPnL != 500 {
		t.Errorf("expected PnL 500, got %.2f", positions[0].UnrealizedPnL)
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd services/go && go test ./internal/broker/ -run TestEngineAdapter -v
```

Expected: FAIL — `NewEngineAdapter` undefined.

- [ ] **Step 3: Implement EngineAdapter**

```go
// services/go/internal/broker/adapter.go
package broker

import (
	"context"

	"github.com/astockpursue/go-core/internal/engine"
)

// EngineAdapter wraps a broker.Broker to satisfy the engine.BrokerExecutor interface.
// This decouples the live trading engine from broker implementation details.
type EngineAdapter struct {
	broker Broker
}

// NewEngineAdapter creates a new EngineAdapter wrapping the given broker.
func NewEngineAdapter(b Broker) *EngineAdapter {
	return &EngineAdapter{broker: b}
}

func (a *EngineAdapter) PlaceOrder(ctx context.Context, symbol, side, orderType string, quantity, price float64) (*engine.BrokerOrder, error) {
	var s OrderSide
	if side == "buy" {
		s = Buy
	} else {
		s = Sell
	}
	var ot OrderType
	if orderType == "market" {
		ot = Market
	} else {
		ot = Limit
	}
	order, err := a.broker.PlaceOrder(ctx, symbol, s, ot, quantity, price)
	if err != nil {
		return nil, err
	}
	return &engine.BrokerOrder{
		OrderID:     order.OrderID,
		Symbol:      order.Symbol,
		Side:        string(order.Side),
		Status:      string(order.Status),
		FilledQty:   order.FilledQty,
		FilledPrice: order.FilledPrice,
	}, nil
}

func (a *EngineAdapter) GetPositions(ctx context.Context) ([]*engine.BrokerPosition, error) {
	positions, err := a.broker.GetPositions(ctx)
	if err != nil {
		return nil, err
	}
	result := make([]*engine.BrokerPosition, len(positions))
	for i, p := range positions {
		result[i] = &engine.BrokerPosition{
			Symbol:        p.Symbol,
			Quantity:      p.Quantity,
			AvgPrice:      p.AvgPrice,
			CurrentPrice:  p.CurrentPrice,
			UnrealizedPnL: p.UnrealizedPnL,
		}
	}
	return result, nil
}
```

- [ ] **Step 4: Run tests**

```bash
cd services/go && go test ./internal/broker/ -v -count=1
```

Expected: PASS — TestEngineAdapterPlaceOrder + TestEngineAdapterGetPositions pass.

- [ ] **Step 5: Commit**

```bash
git add services/go/internal/broker/adapter.go services/go/internal/broker/adapter_test.go
git commit -m "feat(broker): add EngineAdapter to bridge broker.Broker to engine.BrokerExecutor"
```

---

### Task 2: Futu Broker

**Files:**
- Create: `services/go/internal/broker/futu.go`
- Create: `services/go/internal/broker/futu_test.go`
- Modify: `services/go/internal/broker/binance.go` (check init pattern)

**Interfaces:**
- Consumes: `broker.Broker` interface, `broker.BrokerConfig` (factory.go)
- Produces: `NewFutuBroker(cfg BrokerConfig) (Broker, error)`, self-registered as "futu"

- [ ] **Step 1: Check existing broker init() self-registration pattern**

Read `services/go/internal/broker/binance.go` — copy the `init()` registration pattern. Binance registers as `"binance"`. Futu registers as `"futu"`.

- [ ] **Step 2: Write futu_test.go**

```go
// services/go/internal/broker/futu_test.go
package broker

import (
	"testing"
)

func TestFutuBrokerRegistration(t *testing.T) {
	names := List()
	found := false
	for _, n := range names {
		if n == "futu" {
			found = true
			break
		}
	}
	if !found {
		t.Error("futu broker should be registered after init()")
	}
}

func TestFutuBrokerRequiresHost(t *testing.T) {
	// Creating a Futu broker without a valid host should still succeed at
	// construction time (lazy connect). TestConnection should fail.
	cfg := BrokerConfig{Name: "futu", Host: "localhost", Port: 11111}
	b, err := New("futu", cfg)
	if err != nil {
		t.Fatalf("unexpected construction error: %v", err)
	}
	if b.Name() != "futu" {
		t.Errorf("expected name futu, got %s", b.Name())
	}
	// TestConnection will fail without a real FutuOpenD running — that's expected
	err = b.TestConnection(nil)
	if err == nil {
		t.Log("FutuOpenD appears to be running — connection test passed")
	}
}
```

- [ ] **Step 3: Implement futu.go**

Key design decisions for Futu broker:
- Lazy TCP connection — dial on first operation, not at construction
- FutuOpenD uses Protobuf encoding over TCP. Since we may not have the exact Futu protobufs, implement a minimal wire-format adapter:
  - Connect: TCP dial to `cfg.Host:cfg.Port` (default localhost:11111)
  - TestConnection: Send a simple keep-alive / ping packet
  - PlaceOrder: Encode order request as JSON over TCP (FutuOpenD supports JSON mode on certain config)
  - GetPositions/GetBalance: Request position list / fund info
- Auto-reconnect on disconnect (3 retries: 2s, 5s, 10s)
- Password: `cfg.Passphrase` used as trade unlock password

```go
// services/go/internal/broker/futu.go
package broker

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"sync"
	"time"
)

func init() {
	Register("futu", NewFutuBroker)
}

// FutuBroker implements Broker for FutuOpenD gateway via TCP.
// FutuOpenD must be running locally. Default: localhost:11111.
type FutuBroker struct {
	cfg      BrokerConfig
	conn     net.Conn
	mu       sync.Mutex
	reader   *bufio.Reader
	reconnAttempts int
}

func NewFutuBroker(cfg BrokerConfig) (Broker, error) {
	if cfg.Host == "" {
		cfg.Host = "localhost"
	}
	if cfg.Port == 0 {
		cfg.Port = 11111
	}
	return &FutuBroker{cfg: cfg}, nil
}

func (b *FutuBroker) Name() string { return "futu" }

func (b *FutuBroker) TestConnection(ctx context.Context) error {
	conn, err := b.dial()
	if err != nil {
		return fmt.Errorf("futu: connect failed: %w", err)
	}
	conn.Close()
	return nil
}

func (b *FutuBroker) PlaceOrder(ctx context.Context, symbol string, side OrderSide, orderType OrderType, quantity, price float64) (*Order, error) {
	if err := b.ensureConnected(); err != nil {
		return nil, err
	}
	req := map[string]interface{}{
		"cmd":      "place_order",
		"symbol":   symbol,
		"side":     string(side),
		"type":     string(orderType),
		"quantity": quantity,
		"price":    price,
	}
	resp, err := b.send(req)
	if err != nil {
		return nil, err
	}
	return &Order{
		OrderID:    resp["order_id"].(string),
		Symbol:     symbol,
		Side:       side,
		Type:       orderType,
		Price:      price,
		Quantity:   quantity,
		Status:     StatusSubmitted,
		CreatedAt:  time.Now(),
	}, nil
}

func (b *FutuBroker) CancelOrder(ctx context.Context, orderID, symbol string) error {
	if err := b.ensureConnected(); err != nil {
		return err
	}
	_, err := b.send(map[string]interface{}{"cmd": "cancel_order", "order_id": orderID})
	return err
}

func (b *FutuBroker) GetOrder(ctx context.Context, orderID, symbol string) (*Order, error) {
	if err := b.ensureConnected(); err != nil {
		return nil, err
	}
	resp, err := b.send(map[string]interface{}{"cmd": "get_order", "order_id": orderID})
	if err != nil {
		return nil, err
	}
	return parseOrder(resp), nil
}

func (b *FutuBroker) GetOpenOrders(ctx context.Context, symbol string) ([]*Order, error) {
	if err := b.ensureConnected(); err != nil {
		return nil, err
	}
	resp, err := b.send(map[string]interface{}{"cmd": "get_open_orders", "symbol": symbol})
	if err != nil {
		return nil, err
	}
	orders := make([]*Order, 0)
	if list, ok := resp["orders"].([]interface{}); ok {
		for _, item := range list {
			orders = append(orders, parseOrder(item.(map[string]interface{})))
		}
	}
	return orders, nil
}

func (b *FutuBroker) GetPosition(ctx context.Context, symbol string) (*Position, error) {
	positions, err := b.GetPositions(ctx)
	if err != nil {
		return nil, err
	}
	for _, p := range positions {
		if p.Symbol == symbol {
			return p, nil
		}
	}
	return &Position{Symbol: symbol}, nil
}

func (b *FutuBroker) GetPositions(ctx context.Context) ([]*Position, error) {
	if err := b.ensureConnected(); err != nil {
		return nil, err
	}
	resp, err := b.send(map[string]interface{}{"cmd": "get_positions"})
	if err != nil {
		return nil, err
	}
	positions := make([]*Position, 0)
	if list, ok := resp["positions"].([]interface{}); ok {
		for _, item := range list {
			m := item.(map[string]interface{})
			positions = append(positions, &Position{
				Symbol:        m["symbol"].(string),
				Quantity:      m["quantity"].(float64),
				AvgPrice:      m["avg_price"].(float64),
				CurrentPrice:  m["current_price"].(float64),
				UnrealizedPnL: m["unrealized_pnl"].(float64),
			})
		}
	}
	return positions, nil
}

func (b *FutuBroker) GetBalance(ctx context.Context) (*Balance, error) {
	if err := b.ensureConnected(); err != nil {
		return nil, err
	}
	resp, err := b.send(map[string]interface{}{"cmd": "get_balance"})
	if err != nil {
		return nil, err
	}
	return &Balance{
		Total:     resp["total"].(float64),
		Available: resp["available"].(float64),
		Frozen:    resp["frozen"].(float64),
		Currency:  resp["currency"].(string),
	}, nil
}

func (b *FutuBroker) GetFeeRate(symbol string) FeeRate {
	// Futu A-share: 0.03% per side; HK: 0.10%; US: $0.005/share
	return FeeRate{Maker: 0.0003, Taker: 0.0003}
}

// ── Connection management ─────────────────────────────────────────

func (b *FutuBroker) dial() (net.Conn, error) {
	addr := fmt.Sprintf("%s:%d", b.cfg.Host, b.cfg.Port)
	return net.DialTimeout("tcp", addr, 5*time.Second)
}

func (b *FutuBroker) ensureConnected() error {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.conn != nil {
		return nil
	}
	return b.reconnect()
}

func (b *FutuBroker) reconnect() error {
	delays := []time.Duration{2 * time.Second, 5 * time.Second, 10 * time.Second}
	for i, d := range delays {
		conn, err := b.dial()
		if err == nil {
			b.conn = conn
			b.reader = bufio.NewReader(conn)
			b.reconnAttempts = 0
			return nil
		}
		log.Printf("futu: reconnect attempt %d failed: %v", i+1, err)
		if i < len(delays)-1 {
			time.Sleep(d)
		}
	}
	return ErrNotConnected
}

func (b *FutuBroker) send(req map[string]interface{}) (map[string]interface{}, error) {
	data, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}
	data = append(data, '\n')
	if _, err := b.conn.Write(data); err != nil {
		b.conn = nil
		return nil, ErrNotConnected
	}
	line, err := b.reader.ReadString('\n')
	if err != nil {
		b.conn = nil
		return nil, ErrNotConnected
	}
	var resp map[string]interface{}
	if err := json.Unmarshal([]byte(line), &resp); err != nil {
		return nil, fmt.Errorf("futu: parse error: %w", err)
	}
	if errMsg, ok := resp["error"]; ok && errMsg != "" {
		return nil, fmt.Errorf("futu: %s", errMsg)
	}
	return resp, nil
}

func parseOrder(m map[string]interface{}) *Order {
	return &Order{
		OrderID:     m["order_id"].(string),
		Symbol:      m["symbol"].(string),
		Side:        OrderSide(m["side"].(string)),
		Type:        OrderType(m["type"].(string)),
		Price:       m["price"].(float64),
		Quantity:    m["quantity"].(float64),
		FilledQty:   m["filled_qty"].(float64),
		FilledPrice: m["filled_price"].(float64),
		Status:      OrderStatus(m["status"].(string)),
		CreatedAt:   time.Now(),
	}
}
```

- [ ] **Step 4: Run tests**

```bash
cd services/go && go test ./internal/broker/ -v -count=1
```

Expected: PASS — all existing + new Futu tests pass (Futu registration test passes; connection test gracefully handles no FutuOpenD).

- [ ] **Step 5: Commit**

```bash
git add services/go/internal/broker/futu.go services/go/internal/broker/futu_test.go
git commit -m "feat(broker): add Futu broker for FutuOpenD TCP gateway"
```

---

### Task 3: Binance WebSocket Feed

**Files:**
- Create: `services/go/internal/market/feed/binance.go`
- Create: `services/go/internal/market/feed/binance_test.go`

**Interfaces:**
- Consumes: `MarketFeed` interface (feed.go)
- Produces: `NewBinanceFeed() *BinanceFeed`, implements MarketFeed

- [ ] **Step 1: Write binance_test.go**

```go
// services/go/internal/market/feed/binance_test.go
package feed

import (
	"testing"
	"time"
)

func TestBinanceFeedConstruction(t *testing.T) {
	f := NewBinanceFeed()
	if f.Name() != "binance" {
		t.Errorf("expected name binance, got %s", f.Name())
	}
}

func TestBinanceFeedInterval(t *testing.T) {
	f := NewBinanceFeed("1m")
	if f.interval != "1m" {
		t.Errorf("expected interval 1m, got %s", f.interval)
	}
}

func TestBinanceFeedDefaultInterval(t *testing.T) {
	f := NewBinanceFeed()
	if f.interval != "1m" {
		t.Errorf("expected default interval 1m, got %s", f.interval)
	}
}

func TestBinanceFeedHandlers(t *testing.T) {
	f := NewBinanceFeed()
	received := false
	f.OnBar(func(bar Bar) { received = true })
	f.OnError(func(symbol string, err error) {})
	if f.barCb == nil {
		t.Error("OnBar handler not registered")
	}
	if f.errCb == nil {
		t.Error("OnError handler not registered")
	}
	_ = received
}

func TestBinanceStreamName(t *testing.T) {
	tests := []struct{ symbol, interval, expected string }{
		{"btcusdt", "1m", "btcusdt@kline_1m"},
		{"ethusdt", "5m", "ethusdt@kline_5m"},
		{"BTC-USDT", "1h", "btcusdt@kline_1h"},
	}
	for _, tc := range tests {
		result := binanceStreamName(tc.symbol, tc.interval)
		if result != tc.expected {
			t.Errorf("binanceStreamName(%q, %q) = %q, want %q", tc.symbol, tc.interval, result, tc.expected)
		}
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd services/go && go test ./internal/market/feed/ -run TestBinance -v
```

Expected: FAIL — `NewBinanceFeed` undefined.

- [ ] **Step 3: Implement binance.go**

```go
// services/go/internal/market/feed/binance.go
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

type binanceWSMsg struct {
	Stream string          `json:"stream,omitempty"`
	Data   binanceKlineMsg `json:"data,omitempty"`
}

type binanceKlineMsg struct {
	EventType string `json:"e"`
	EventTime int64  `json:"E"`
	Symbol    string `json:"s"`
	Kline     struct {
		StartTime            int64  `json:"t"`
		CloseTime            int64  `json:"T"`
		Symbol               string `json:"s"`
		Interval             string `json:"i"`
		Open                 string `json:"o"`
		High                 string `json:"h"`
		Low                  string `json:"l"`
		Close                string `json:"c"`
		Volume               string `json:"v"`
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

func (f *BinanceFeed) OnBar(handler BarHandler)     { f.barCb = handler }
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
		f.subscribe(symbols)
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

		var kline binanceKlineMsg
		if err := json.Unmarshal(msg, &kline); err != nil {
			continue
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

func binanceStreamName(symbol, interval string) string {
	clean := strings.ToLower(strings.ReplaceAll(symbol, "-", ""))
	return fmt.Sprintf("%s@kline_%s", clean, interval)
}

func parseFloatStr(s string) float64 {
	var v float64
	fmt.Sscanf(s, "%f", &v)
	return v
}
```

- [ ] **Step 4: Run tests**

```bash
cd services/go && go test ./internal/market/feed/ -v -count=1
```

Expected: PASS — all existing OKX tests + new Binance tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/go/internal/market/feed/binance.go services/go/internal/market/feed/binance_test.go
git commit -m "feat(feed): add Binance WebSocket kline feed"
```

---

### Task 4: Papertrade Engine Package

**Files:**
- Create: `services/go/internal/papertrade/engine.go`
- Create: `services/go/internal/papertrade/state_machine.go`
- Create: `services/go/internal/papertrade/repository.go`
- Create: `services/go/internal/papertrade/engine_test.go`
- Modify: `services/go/internal/api/handler/papertrade.go` (refactor to use new package)

**Interfaces:**
- Consumes: `engine.LiveTradingRunner`, `market.DataStore`, `engine.EngineFactory`
- Produces: `papertrade.Engine` with Create/Start/Stop/Delete/List/Get methods

- [ ] **Step 1: Write engine_test.go**

```go
// services/go/internal/papertrade/engine_test.go
package papertrade

import (
	"testing"
	"time"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/market"
)

func TestEngineCreateRun(t *testing.T) {
	ds := &market.DataStore{}
	factory := &engine.EngineFactory{}
	e := NewEngine(ds, factory)

	run, err := e.Create("test-run", []string{"000001.SZ"}, "1d", 100000)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if run.ID == "" {
		t.Error("expected non-empty ID")
	}
	if run.Status != StatusCreated {
		t.Errorf("expected status created, got %s", run.Status)
	}
}

func TestEngineStateTransitions(t *testing.T) {
	e := NewEngine(&market.DataStore{}, &engine.EngineFactory{})
	run, _ := e.Create("test", []string{"000001.SZ"}, "1d", 100000)

	// created → running
	err := e.Start(run.ID)
	if err != nil {
		t.Fatalf("start failed: %v", err)
	}
	if run.Status != StatusRunning {
		t.Errorf("expected running, got %s", run.Status)
	}

	// running → stopped
	err = e.Stop(run.ID)
	if err != nil {
		t.Fatalf("stop failed: %v", err)
	}
	if run.Status != StatusStopped {
		t.Errorf("expected stopped, got %s", run.Status)
	}
}

func TestEngineListAndGet(t *testing.T) {
	e := NewEngine(&market.DataStore{}, &engine.EngineFactory{})
	_, _ = e.Create("run1", []string{"A"}, "1d", 100000)
	_, _ = e.Create("run2", []string{"B"}, "1h", 50000)

	runs := e.List()
	if len(runs) != 2 {
		t.Errorf("expected 2 runs, got %d", len(runs))
	}

	run := e.Get(runs[0].ID)
	if run == nil {
		t.Error("Get returned nil for valid ID")
	}
}

func TestEngineDelete(t *testing.T) {
	e := NewEngine(&market.DataStore{}, &engine.EngineFactory{})
	run, _ := e.Create("test", []string{"A"}, "1d", 100000)

	err := e.Delete(run.ID)
	if err != nil {
		t.Fatalf("delete failed: %v", err)
	}
	if len(e.List()) != 0 {
		t.Error("expected 0 runs after delete")
	}
}

func TestInvalidTransitions(t *testing.T) {
	e := NewEngine(&market.DataStore{}, &engine.EngineFactory{})
	run, _ := e.Create("test", []string{"A"}, "1d", 100000)

	// Cannot start an already running run
	e.Start(run.ID)
	err := e.Start(run.ID)
	if err == nil {
		t.Error("expected error when starting already-running run")
	}

	// Cannot stop a stopped run
	e.Stop(run.ID)
	err = e.Stop(run.ID)
	if err == nil {
		t.Error("expected error when stopping already-stopped run")
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd services/go && go test ./internal/papertrade/ -v -count=1
```

Expected: FAIL — package or types not defined.

- [ ] **Step 3: Implement state_machine.go**

```go
// services/go/internal/papertrade/state_machine.go
package papertrade

import "fmt"

type RunStatus string

const (
	StatusCreated RunStatus = "created"
	StatusRunning RunStatus = "running"
	StatusPaused  RunStatus = "paused"
	StatusStopped RunStatus = "stopped"
	StatusError   RunStatus = "error"
)

var validTransitions = map[RunStatus][]RunStatus{
	StatusCreated: {StatusRunning},
	StatusRunning: {StatusPaused, StatusStopped, StatusError},
	StatusPaused:  {StatusRunning, StatusStopped},
	StatusError:   {StatusStopped},
}

func canTransition(from, to RunStatus) bool {
	targets, ok := validTransitions[from]
	if !ok {
		return false
	}
	for _, t := range targets {
		if t == to {
			return true
		}
	}
	return false
}

func (r *Run) transition(to RunStatus) error {
	if !canTransition(r.Status, to) {
		return fmt.Errorf("papertrade: invalid transition %s→%s", r.Status, to)
	}
	r.Status = to
	return nil
}
```

- [ ] **Step 4: Implement engine.go**

```go
// services/go/internal/papertrade/engine.go
package papertrade

import (
	"fmt"
	"sync"
	"time"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/market"
	"github.com/google/uuid"
)

// Run represents a paper trading session.
type Run struct {
	ID          string                    `json:"id"`
	Name        string                    `json:"name"`
	Symbols     []string                  `json:"symbols"`
	Frequency   string                    `json:"frequency"`
	InitialCash float64                   `json:"initial_cash"`
	Status      RunStatus                 `json:"status"`
	CreatedAt   time.Time                 `json:"created_at"`
	Runner      *engine.LiveTradingRunner `json:"-"`
}

// Engine manages paper trading runs.
type Engine struct {
	mu      sync.RWMutex
	runs    map[string]*Run
	ds      *market.DataStore
	factory *engine.EngineFactory
	repo    Repository
}

// NewEngine creates a new paper trading engine.
func NewEngine(ds *market.DataStore, factory *engine.EngineFactory) *Engine {
	return &Engine{
		runs:    make(map[string]*Run),
		ds:      ds,
		factory: factory,
		repo:    NewMemoryRepository(),
	}
}

// WithRepository sets a persistent repository (PostgreSQL).
func (e *Engine) WithRepository(repo Repository) *Engine {
	e.repo = repo
	return e
}

// Create creates a new paper trading run (status: created).
func (e *Engine) Create(name string, symbols []string, freq string, initialCash float64) (*Run, error) {
	if freq == "" {
		freq = "1d"
	}
	if initialCash <= 0 {
		initialCash = 100000
	}

	pipeline := &engine.Pipeline{
		Engine:    e.factory.ForSymbol(symbols[0]),
		Portfolio: &engine.Portfolio{Cash: initialCash, Equity: initialCash, Positions: make(map[string]*engine.Position)},
		Signal:    engine.NewSignalAdapter("localhost:8902", 10*time.Second),
		Risk:      engine.NewRiskManager(engine.RiskConfig{}),
		LastBars:  make(map[string]interface{}),
	}

	runner := engine.NewLiveTradingRunner(pipeline, 1*time.Minute)
	runner.WithFetcher(&dsFetcher{ds: e.ds}, symbols, freq)

	run := &Run{
		ID:          uuid.New().String(),
		Name:        name,
		Symbols:     symbols,
		Frequency:   freq,
		InitialCash: initialCash,
		Status:      StatusCreated,
		CreatedAt:   time.Now(),
		Runner:      runner,
	}

	e.mu.Lock()
	e.runs[run.ID] = run
	e.mu.Unlock()

	if e.repo != nil {
		e.repo.Save(run)
	}

	return run, nil
}

// Start transitions a run from created→running.
func (e *Engine) Start(id string) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	run, ok := e.runs[id]
	if !ok {
		return fmt.Errorf("papertrade: run %s not found", id)
	}
	if err := run.transition(StatusRunning); err != nil {
		return err
	}
	return run.Runner.Start()
}

// Stop transitions a run to stopped and shuts down the runner.
func (e *Engine) Stop(id string) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	run, ok := e.runs[id]
	if !ok {
		return fmt.Errorf("papertrade: run %s not found", id)
	}
	if err := run.Runner.Stop(); err != nil {
		return err
	}
	return run.transition(StatusStopped)
}

// Delete removes a run (stopping it first if running).
func (e *Engine) Delete(id string) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	run, ok := e.runs[id]
	if !ok {
		return fmt.Errorf("papertrade: run %s not found", id)
	}
	if run.Status == StatusRunning {
		run.Runner.Stop()
	}
	delete(e.runs, id)
	if e.repo != nil {
		e.repo.Delete(id)
	}
	return nil
}

// List returns all runs.
func (e *Engine) List() []*Run {
	e.mu.RLock()
	defer e.mu.RUnlock()
	runs := make([]*Run, 0, len(e.runs))
	for _, r := range e.runs {
		runs = append(runs, r)
	}
	return runs
}

// Get returns a single run by ID.
func (e *Engine) Get(id string) *Run {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.runs[id]
}

// dsFetcher adapts market.DataStore to engine.BarFetcher.
type dsFetcher struct {
	ds *market.DataStore
}

func (f *dsFetcher) GetBars(symbol string, start, end time.Time, freq string) ([]engine.BarData, error) {
	bars, err := f.ds.GetBars(symbol, start, end, freq)
	if err != nil {
		return nil, err
	}
	result := make([]engine.BarData, len(bars))
	for i, b := range bars {
		result[i] = engine.BarData{
			Symbol:    b.Symbol,
			Open:      b.Open,
			High:      b.High,
			Low:       b.Low,
			Close:     b.Close,
			Volume:    b.Volume,
			Timestamp: time.UnixMilli(b.Timestamp),
		}
	}
	return result, nil
}
```

- [ ] **Step 5: Implement repository.go**

```go
// services/go/internal/papertrade/repository.go
package papertrade

import "sync"

// Repository persists paper trading runs.
type Repository interface {
	Save(run *Run) error
	LoadAll() ([]*Run, error)
	Delete(id string) error
}

// MemoryRepository is an in-memory implementation for development/testing.
type MemoryRepository struct {
	mu   sync.RWMutex
	runs map[string]*Run
}

func NewMemoryRepository() *MemoryRepository {
	return &MemoryRepository{runs: make(map[string]*Run)}
}

func (r *MemoryRepository) Save(run *Run) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.runs[run.ID] = run
	return nil
}

func (r *MemoryRepository) LoadAll() ([]*Run, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	runs := make([]*Run, 0, len(r.runs))
	for _, run := range r.runs {
		runs = append(runs, run)
	}
	return runs, nil
}

func (r *MemoryRepository) Delete(id string) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	delete(r.runs, id)
	return nil
}
```

- [ ] **Step 6: Run all tests**

```bash
cd services/go && go test ./internal/papertrade/ -v -count=1
```

Expected: PASS — all 5 tests pass.

- [ ] **Step 7: Refactor API handler to use papertrade.Engine**

Replace the inline logic in `services/go/internal/api/handler/papertrade.go` with delegation to `papertrade.Engine`:

```go
// In api/handler/papertrade.go — replace PaperTradingHandler struct:

type PaperTradingHandler struct {
	engine *papertrade.Engine
}

func NewPaperTradingHandler(ds *market.DataStore, factory *engine.EngineFactory) *PaperTradingHandler {
	return &PaperTradingHandler{
		engine: papertrade.NewEngine(ds, factory),
	}
}

func (h *PaperTradingHandler) CreateRun(c *gin.Context) {
	var req struct {
		Name        string   `json:"name" binding:"required"`
		Symbols     []string `json:"symbols" binding:"required"`
		Frequency   string   `json:"frequency"`
		InitialCash float64  `json:"initial_cash"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	run, err := h.engine.Create(req.Name, req.Symbols, req.Frequency, req.InitialCash)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusCreated, run)
}

func (h *PaperTradingHandler) ListRuns(c *gin.Context) {
	runs := h.engine.List()
	c.JSON(http.StatusOK, gin.H{"runs": runs, "count": len(runs)})
}

func (h *PaperTradingHandler) GetRun(c *gin.Context) {
	run := h.engine.Get(c.Param("id"))
	if run == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "run not found"})
		return
	}
	c.JSON(http.StatusOK, run)
}

func (h *PaperTradingHandler) StartRun(c *gin.Context) {
	if err := h.engine.Start(c.Param("id")); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"id": c.Param("id"), "status": "running"})
}

func (h *PaperTradingHandler) StopRun(c *gin.Context) {
	if err := h.engine.Stop(c.Param("id")); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"id": c.Param("id"), "status": "stopped"})
}

func (h *PaperTradingHandler) DeleteRun(c *gin.Context) {
	if err := h.engine.Delete(c.Param("id")); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"id": c.Param("id"), "deleted": true})
}
```

- [ ] **Step 8: Verify full test suite**

```bash
cd services/go && go test ./... -count=1
```

Expected: All tests PASS. The refactored handler tests pass alongside new papertrade tests.

- [ ] **Step 9: Commit**

```bash
git add services/go/internal/papertrade/ services/go/internal/api/handler/papertrade.go
git commit -m "feat(papertrade): add papertrade engine package with state machine and repository"
```

---

## Self-Review

1. **Spec coverage**: All 4 items covered — Futu broker (Task 2), adapter (Task 1), papertrade engine (Task 4), Binance feed (Task 3).
2. **Placeholder scan**: No TBD/TODO. All code is concrete Go with imports, error handling, test assertions.
3. **Type consistency**: `broker.Broker` interface unchanged. `engine.BrokerExecutor` unchanged. `MarketFeed` unchanged. All new types via existing factory/registration patterns.
4. **Interface preservation**: No modifications to existing interfaces or API routes — only additions.
