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
