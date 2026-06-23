package broker

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	slog "github.com/astockpursue/go-core/internal/log"
	"net"
	"strconv"
	"sync"
	"time"
)

func init() {
	Register("futu", NewFutuBroker)
}

// FutuBroker implements Broker for FutuOpenD gateway via TCP.
// FutuOpenD must be running locally. Default: localhost:11111.
type FutuBroker struct {
	cfg            BrokerConfig
	conn           net.Conn
	mu             sync.Mutex
	reader         *bufio.Reader
	reconnAttempts int
	reconnecting   bool
}

// NewFutuBroker creates a new Futu broker instance.
// Connection is established lazily on first operation.
// Host/port default to "localhost:11111"; set FUTU_HOST and FUTU_PORT env vars
// via config.Load() to override.
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

// ── Order management ──────────────────────────────────────────────

func (b *FutuBroker) PlaceOrder(ctx context.Context, symbol string, side OrderSide, orderType OrderType, quantity, price float64) (*Order, error) {
	if err := b.ensureConnected(); err != nil {
		return nil, err
	}
	req := map[string]any{
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
	oid, _ := resp["order_id"].(string)
	return &Order{
		OrderID:   oid,
		Symbol:    symbol,
		Side:      side,
		Type:      orderType,
		Price:     price,
		Quantity:  quantity,
		Status:    StatusSubmitted,
		CreatedAt: time.Now(),
	}, nil
}

func (b *FutuBroker) CancelOrder(ctx context.Context, orderID, symbol string) error {
	if err := b.ensureConnected(); err != nil {
		return err
	}
	_, err := b.send(map[string]any{"cmd": "cancel_order", "order_id": orderID})
	return err
}

func (b *FutuBroker) GetOrder(ctx context.Context, orderID, symbol string) (*Order, error) {
	if err := b.ensureConnected(); err != nil {
		return nil, err
	}
	resp, err := b.send(map[string]any{"cmd": "get_order", "order_id": orderID})
	if err != nil {
		return nil, err
	}
	return parseOrder(resp), nil
}

func (b *FutuBroker) GetOpenOrders(ctx context.Context, symbol string) ([]*Order, error) {
	if err := b.ensureConnected(); err != nil {
		return nil, err
	}
	req := map[string]any{"cmd": "get_open_orders"}
	if symbol != "" {
		req["symbol"] = symbol
	}
	resp, err := b.send(req)
	if err != nil {
		return nil, err
	}
	orders := make([]*Order, 0)
	if list, ok := resp["orders"].([]any); ok {
		for _, item := range list {
			if m, ok := item.(map[string]any); ok {
				orders = append(orders, parseOrder(m))
			}
		}
	}
	return orders, nil
}

// ── Position & balance ────────────────────────────────────────────

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
	resp, err := b.send(map[string]any{"cmd": "get_positions"})
	if err != nil {
		return nil, err
	}
	positions := make([]*Position, 0)
	if list, ok := resp["positions"].([]any); ok {
		for _, item := range list {
			if m, ok := item.(map[string]any); ok {
				qty, err := getFloat(m, "quantity")
				if err != nil {
					slog.Errorf("futu: GetPositions quantity: %v", err)
				}
				avgPx, err := getFloat(m, "avg_price")
				if err != nil {
					slog.Errorf("futu: GetPositions avg_price: %v", err)
				}
				curPx, err := getFloat(m, "current_price")
				if err != nil {
					slog.Errorf("futu: GetPositions current_price: %v", err)
				}
				upnl, err := getFloat(m, "unrealized_pnl")
				if err != nil {
					slog.Errorf("futu: GetPositions unrealized_pnl: %v", err)
				}
				sym, _ := m["symbol"].(string)
				positions = append(positions, &Position{
					Symbol:        sym,
					Quantity:      qty,
					AvgPrice:      avgPx,
					CurrentPrice:  curPx,
					UnrealizedPnL: upnl,
				})
			}
		}
	}
	return positions, nil
}

func (b *FutuBroker) GetBalance(ctx context.Context) (*Balance, error) {
	if err := b.ensureConnected(); err != nil {
		return nil, err
	}
	resp, err := b.send(map[string]any{"cmd": "get_balance"})
	if err != nil {
		return nil, err
	}
	total, err := getFloat(resp, "total")
	if err != nil {
		slog.Errorf("futu: GetBalance total: %v", err)
	}
	avail, err := getFloat(resp, "available")
	if err != nil {
		slog.Errorf("futu: GetBalance available: %v", err)
	}
	frozen, err := getFloat(resp, "frozen")
	if err != nil {
		slog.Errorf("futu: GetBalance frozen: %v", err)
	}
	ccy, _ := resp["currency"].(string)
	return &Balance{
		Total:     total,
		Available: avail,
		Frozen:    frozen,
		Currency:  ccy,
	}, nil
}

func (b *FutuBroker) GetFeeRate(symbol string) FeeRate {
	// Futu A-share: 0.03% per side; HK: 0.10%; US: $0.005/share
	// Default to A-share rate
	return FeeRate{Maker: 0.0003, Taker: 0.0003}
}

// ── Connection management ─────────────────────────────────────────

func (b *FutuBroker) dial() (net.Conn, error) {
	addr := net.JoinHostPort(b.cfg.Host, strconv.Itoa(b.cfg.Port))
	return net.DialTimeout("tcp", addr, 5*time.Second)
}

func (b *FutuBroker) ensureConnected() error {
	b.mu.Lock()
	if b.conn != nil {
		b.mu.Unlock()
		return nil
	}
	if b.reconnecting {
		b.mu.Unlock()
		time.Sleep(10 * time.Millisecond)
		return b.ensureConnected()
	}
	b.reconnecting = true
	err := b.reconnectLocked()
	b.reconnecting = false
	b.mu.Unlock()
	return err
}

// reconnectLocked performs reconnection while the caller holds b.mu.
// It is called by ensureConnected() under the lock.
func (b *FutuBroker) reconnectLocked() error {
	delays := []time.Duration{2 * time.Second, 5 * time.Second, 10 * time.Second}
	for i, d := range delays {
		b.mu.Unlock() // release lock during I/O
		conn, err := b.dial()
		b.mu.Lock() // reacquire before reading/writing state
		if err == nil {
			b.conn = conn
			b.reader = bufio.NewReader(conn)
			b.reconnAttempts = 0
			return nil
		}
		slog.Errorf("futu: reconnect attempt %d failed: %v", i+1, err)
		if i < len(delays)-1 {
			b.mu.Unlock()
			time.Sleep(d)
			b.mu.Lock()
		}
	}
	return ErrNotConnected
}

// reconnect performs reconnection from outside the lock.
// Used by callers that do not already hold b.mu.
func (b *FutuBroker) reconnect() error {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.reconnectLocked()
}

func (b *FutuBroker) send(req map[string]any) (map[string]any, error) {
	data, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}
	data = append(data, '\n')

	b.mu.Lock()
	defer b.mu.Unlock()

	if b.conn == nil {
		return nil, ErrNotConnected
	}
	if _, err := b.conn.Write(data); err != nil {
		b.conn = nil
		return nil, ErrNotConnected
	}
	line, err := b.reader.ReadString('\n')
	if err != nil {
		b.conn = nil
		return nil, ErrNotConnected
	}
	var resp map[string]any
	if err := json.Unmarshal([]byte(line), &resp); err != nil {
		return nil, fmt.Errorf("futu: parse error: %w", err)
	}
	if errMsg, ok := resp["error"]; ok && errMsg != nil {
		if s, ok := errMsg.(string); ok && s != "" {
			return nil, fmt.Errorf("futu: %s", s)
		}
	}
	return resp, nil
}

// ── Helpers ───────────────────────────────────────────────────────

func parseOrder(m map[string]any) *Order {
	oid, _ := m["order_id"].(string)
	sym, _ := m["symbol"].(string)
	sd, _ := m["side"].(string)
	ot, _ := m["type"].(string)
	price, err := getFloat(m, "price")
	if err != nil {
		slog.Errorf("futu: parseOrder price: %v", err)
	}
	qty, err := getFloat(m, "quantity")
	if err != nil {
		slog.Errorf("futu: parseOrder quantity: %v", err)
	}
	filledQty, err := getFloat(m, "filled_qty")
	if err != nil {
		slog.Errorf("futu: parseOrder filled_qty: %v", err)
	}
	filledPrice, err := getFloat(m, "filled_price")
	if err != nil {
		slog.Errorf("futu: parseOrder filled_price: %v", err)
	}
	status, _ := m["status"].(string)

	return &Order{
		OrderID:     oid,
		Symbol:      sym,
		Side:        OrderSide(sd),
		Type:        OrderType(ot),
		Price:       price,
		Quantity:    qty,
		FilledQty:   filledQty,
		FilledPrice: filledPrice,
		Status:      OrderStatus(status),
		CreatedAt:   time.Now(),
	}
}

// getFloat safely extracts a float64 value from a map.
func getFloat(m map[string]any, key string) (float64, error) {
	v, ok := m[key]
	if !ok {
		return 0, fmt.Errorf("futu: key %q not found in response", key)
	}
	switch n := v.(type) {
	case float64:
		return n, nil
	case float32:
		return float64(n), nil
	case int:
		return float64(n), nil
	case int64:
		return float64(n), nil
	case json.Number:
		f, err := n.Float64()
		if err != nil {
			return 0, fmt.Errorf("futu: key %q parse float64: %w", key, err)
		}
		return f, nil
	}
	return 0, fmt.Errorf("futu: key %q unexpected type %T", key, v)
}
