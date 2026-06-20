// services/go/internal/broker/adapter_test.go
package broker

import (
	"context"
	"testing"
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
