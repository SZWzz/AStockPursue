// Package broker provides exchange broker gateways for order execution,
// position tracking, and account management. Implementations include
// Binance, OKX (via REST API), and Futu (via TCP).
package broker

import (
	"context"
	"fmt"
	"time"
)

// ── Data types ────────────────────────────────────────────────────

// OrderSide represents buy or sell direction.
type OrderSide string

const (
	Buy  OrderSide = "buy"
	Sell OrderSide = "sell"
)

// OrderType represents the type of order.
type OrderType string

const (
	Market OrderType = "market"
	Limit  OrderType = "limit"
)

// OrderStatus tracks the lifecycle of an order.
type OrderStatus string

const (
	StatusPending   OrderStatus = "pending"
	StatusSubmitted OrderStatus = "submitted"
	StatusPartial   OrderStatus = "partial"
	StatusFilled    OrderStatus = "filled"
	StatusCancelled OrderStatus = "cancelled"
	StatusRejected  OrderStatus = "rejected"
)

// Order represents a single order on an exchange.
type Order struct {
	OrderID      string      `json:"order_id"`
	Symbol       string      `json:"symbol"`
	Side         OrderSide   `json:"side"`
	Type         OrderType   `json:"type"`
	Price        float64     `json:"price"`
	Quantity     float64     `json:"quantity"`
	FilledQty    float64     `json:"filled_qty"`
	FilledPrice  float64     `json:"filled_price"`
	Status       OrderStatus `json:"status"`
	RejectReason string      `json:"reject_reason,omitempty"`
	CreatedAt    time.Time   `json:"created_at"`
}

// Position represents an open position on an exchange.
type Position struct {
	Symbol        string  `json:"symbol"`
	Quantity      float64 `json:"quantity"`
	AvgPrice      float64 `json:"avg_price"`
	CurrentPrice  float64 `json:"current_price"`
	UnrealizedPnL float64 `json:"unrealized_pnl"`
}

// Balance represents an account's asset balance.
type Balance struct {
	Total     float64 `json:"total"`
	Available float64 `json:"available"`
	Frozen    float64 `json:"frozen"`
	Currency  string  `json:"currency"`
}

// FeeRate returns maker/taker fee rates for a symbol.
type FeeRate struct {
	Maker float64 `json:"maker"`
	Taker float64 `json:"taker"`
}

// ── Broker interface ───────────────────────────────────────────────

// Broker is the unified interface for all exchange gateways.
// Implementations handle authentication, request signing, and error mapping.
type Broker interface {
	// Name returns the broker's identifier (e.g. "binance", "okx").
	Name() string

	// TestConnection verifies the broker connection is healthy.
	TestConnection(ctx context.Context) error

	// ── Order management ──

	// PlaceOrder submits a new order to the exchange.
	PlaceOrder(ctx context.Context, symbol string, side OrderSide, orderType OrderType, quantity float64, price float64) (*Order, error)
	// CancelOrder cancels an existing order by ID.
	CancelOrder(ctx context.Context, orderID string, symbol string) error
	// GetOrder retrieves a single order by ID.
	GetOrder(ctx context.Context, orderID string, symbol string) (*Order, error)
	// GetOpenOrders returns all currently open orders.
	GetOpenOrders(ctx context.Context, symbol string) ([]*Order, error)

	// ── Position & balance ──

	// GetPosition returns the current position for a symbol.
	GetPosition(ctx context.Context, symbol string) (*Position, error)
	// GetPositions returns all open positions.
	GetPositions(ctx context.Context) ([]*Position, error)
	// GetBalance returns the account balance.
	GetBalance(ctx context.Context) (*Balance, error)

	// ── Fees ──

	// GetFeeRate returns maker/taker fee rates.
	GetFeeRate(symbol string) FeeRate
}

// ── Errors ────────────────────────────────────────────────────────

// ErrNotConnected is returned when a broker operation is attempted without
// an active connection.
var ErrNotConnected = fmt.Errorf("broker: not connected")

// ErrUnsupported is returned when a feature is not supported by the broker.
var ErrUnsupported = fmt.Errorf("broker: operation not supported")
