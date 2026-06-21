package engine

import (
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
)

// OMS API constant aliases (tests and external callers use these names)
const (
	OrderBuy    = Buy
	OrderSell   = Sell
	OrderMarket = Market
	OrderLimit  = Limit
)

type OrderManager struct {
	orders map[string]*Order
	mu     sync.RWMutex
}

func NewOrderManager() *OrderManager {
	return &OrderManager{
		orders: make(map[string]*Order),
	}
}

func (om *OrderManager) Create(symbol string, side OrderSide, orderType OrderType, qty, price float64) *Order {
	now := time.Now()
	order := &Order{
		ID:        uuid.New().String(),
		Symbol:    symbol,
		Side:      side,
		Type:      orderType,
		Quantity:  qty,
		Price:     price,
		Status:    OrderPending,
		CreatedAt: now,
		UpdatedAt: now,
	}
	om.mu.Lock()
	om.orders[order.ID] = order
	om.mu.Unlock()
	return order
}

func (om *OrderManager) Submit(orderID string) error {
	om.mu.Lock()
	defer om.mu.Unlock()
	order, ok := om.orders[orderID]
	if !ok {
		return fmt.Errorf("order %s not found", orderID)
	}
	if order.Status != OrderPending {
		return fmt.Errorf("order %s cannot be submitted from status %s", orderID, order.Status)
	}
	order.Status = OrderSubmitted
	order.UpdatedAt = time.Now()
	return nil
}

func (om *OrderManager) Fill(orderID string, fillQty, fillPrice float64) error {
	om.mu.Lock()
	defer om.mu.Unlock()
	order, ok := om.orders[orderID]
	if !ok {
		return fmt.Errorf("order %s not found", orderID)
	}
	if order.Status != OrderSubmitted && order.Status != OrderPartiallyFilled {
		return fmt.Errorf("order %s cannot be filled from status %s", orderID, order.Status)
	}
	if order.Filled+fillQty > order.Quantity {
		return fmt.Errorf("fill qty %f exceeds remaining %f", fillQty, order.Quantity-order.Filled)
	}
	// VWAP update
	if order.Filled > 0 {
		order.FillPrice = (order.FillPrice*order.Filled + fillPrice*fillQty) / (order.Filled + fillQty)
	} else {
		order.FillPrice = fillPrice
	}
	order.Filled += fillQty
	if order.Filled >= order.Quantity {
		order.Status = OrderFilled
	} else {
		order.Status = OrderPartiallyFilled
	}
	order.UpdatedAt = time.Now()
	return nil
}

func (om *OrderManager) Cancel(orderID string) error {
	om.mu.Lock()
	defer om.mu.Unlock()
	order, ok := om.orders[orderID]
	if !ok {
		return fmt.Errorf("order %s not found", orderID)
	}
	if order.Status != OrderSubmitted && order.Status != OrderPartiallyFilled {
		return fmt.Errorf("order %s cannot be cancelled from status %s", orderID, order.Status)
	}
	order.Status = OrderCancelled
	order.UpdatedAt = time.Now()
	return nil
}

func (om *OrderManager) Reject(orderID string, reason string) error {
	om.mu.Lock()
	defer om.mu.Unlock()
	order, ok := om.orders[orderID]
	if !ok {
		return fmt.Errorf("order %s not found", orderID)
	}
	if order.Status != OrderPending && order.Status != OrderSubmitted {
		return fmt.Errorf("order %s cannot be rejected from status %s", orderID, order.Status)
	}
	order.Status = OrderRejected
	order.RejectReason = reason
	order.UpdatedAt = time.Now()
	return nil
}

func (om *OrderManager) Get(orderID string) (*Order, error) {
	om.mu.RLock()
	defer om.mu.RUnlock()
	order, ok := om.orders[orderID]
	if !ok {
		return nil, fmt.Errorf("order %s not found", orderID)
	}
	return order, nil
}
