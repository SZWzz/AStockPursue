package engine

import (
	"fmt"
	"time"
)

type OrderSide string

const (
	Buy  OrderSide = "buy"
	Sell OrderSide = "sell"
)

type OrderType string

const (
	Market OrderType = "market"
	Limit  OrderType = "limit"
)

type OrderStatus string

const (
	OrderPending          OrderStatus = "pending"
	OrderSubmitted        OrderStatus = "submitted"
	OrderPartiallyFilled  OrderStatus = "partially_filled"
	OrderFilled           OrderStatus = "filled"
	OrderCancelled        OrderStatus = "cancelled"
	OrderRejected         OrderStatus = "rejected"
)

type Order struct {
	ID           string      `json:"id"`
	Symbol       string      `json:"symbol"`
	Side         OrderSide   `json:"side"`
	Type         OrderType   `json:"type"`
	Price        float64     `json:"price,omitempty"`
	LimitPrice   float64     `json:"limit_price,omitempty"`
	Quantity     float64     `json:"quantity"`
	Filled       float64     `json:"filled"`
	FillPrice    float64     `json:"fill_price,omitempty"`
	Status       OrderStatus `json:"status"`
	RejectReason string      `json:"reject_reason,omitempty"`
	CreatedAt    time.Time   `json:"created_at"`
	UpdatedAt    time.Time   `json:"updated_at"`
}

func (o *Order) Validate() error {
	if o.Side != Buy && o.Side != Sell {
		return fmt.Errorf("invalid side: %s", o.Side)
	}
	if o.Type != Market && o.Type != Limit {
		return fmt.Errorf("invalid type: %s", o.Type)
	}
	if o.Quantity <= 0 {
		return fmt.Errorf("quantity must be positive")
	}
	return nil
}

type Position struct {
	Symbol       string  `json:"symbol"`
	Size         float64 `json:"size"`
	EntryPrice   float64 `json:"entry_price"`
	CurrentPrice float64 `json:"current_price"`
}

func (p *Position) Side() string {
	if p.Size == 0 {
		return ""
	}
	if p.Size > 0 {
		return "long"
	}
	return "short"
}

func (p *Position) UnrealizedPnL() float64 {
	return p.Size * (p.CurrentPrice - p.EntryPrice)
}

type Bar struct {
	Symbol string
	Open, High, Low, Close float64
	Volume int64
}

type Portfolio struct {
	Positions     map[string]*Position `json:"positions"`
	Cash          float64              `json:"cash"`
	Equity        float64              `json:"equity"`
	InitialEquity float64              `json:"initial_equity"`
}

func (pf *Portfolio) Snapshot() *Portfolio {
	positions := make(map[string]*Position, len(pf.Positions))
	for k, v := range pf.Positions {
		copy := *v
		positions[k] = &copy
	}
	return &Portfolio{
		Cash:          pf.Cash,
		Equity:        pf.Equity,
		InitialEquity: pf.InitialEquity,
		Positions:     positions,
	}
}
