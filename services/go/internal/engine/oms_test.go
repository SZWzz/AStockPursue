package engine

import (
	"testing"
)

func TestOrderLifecycleHappyPath(t *testing.T) {
	om := NewOrderManager()
	order := om.Create("000001.SZ", OrderBuy, OrderMarket, 100, 10.0)

	if order.Status != OrderPending {
		t.Errorf("new order should be pending, got %s", order.Status)
	}

	err := om.Submit(order.ID)
	if err != nil {
		t.Fatalf("submit failed: %v", err)
	}
	if order.Status != OrderSubmitted {
		t.Errorf("submitted order should be submitted, got %s", order.Status)
	}

	err = om.Fill(order.ID, 100, 10.0)
	if err != nil {
		t.Fatalf("fill failed: %v", err)
	}
	if order.Status != OrderFilled {
		t.Errorf("filled order should be filled, got %s", order.Status)
	}
	if order.Filled != 100 {
		t.Errorf("expected filled qty 100, got %f", order.Filled)
	}
}

func TestOrderPartialFill(t *testing.T) {
	om := NewOrderManager()
	order := om.Create("000001.SZ", OrderBuy, OrderMarket, 100, 10.0)
	om.Submit(order.ID)

	err := om.Fill(order.ID, 60, 10.0)
	if err != nil {
		t.Fatalf("partial fill failed: %v", err)
	}
	if order.Status != OrderPartiallyFilled {
		t.Errorf("expected partially_filled, got %s", order.Status)
	}
	if order.Filled != 60 {
		t.Errorf("expected filled qty 60, got %f", order.Filled)
	}

	err = om.Fill(order.ID, 40, 10.0)
	if err != nil {
		t.Fatalf("completing fill failed: %v", err)
	}
	if order.Status != OrderFilled {
		t.Errorf("expected filled after complete fill, got %s", order.Status)
	}
}

func TestOrderCancel(t *testing.T) {
	om := NewOrderManager()
	order := om.Create("000001.SZ", OrderBuy, OrderMarket, 100, 10.0)
	om.Submit(order.ID)

	err := om.Cancel(order.ID)
	if err != nil {
		t.Fatalf("cancel failed: %v", err)
	}
	if order.Status != OrderCancelled {
		t.Errorf("expected cancelled, got %s", order.Status)
	}
}

func TestOrderReject(t *testing.T) {
	om := NewOrderManager()
	order := om.Create("000001.SZ", OrderBuy, OrderMarket, 100, 10.0)

	err := om.Reject(order.ID, "insufficient margin")
	if err != nil {
		t.Fatalf("reject failed: %v", err)
	}
	if order.Status != OrderRejected {
		t.Errorf("expected rejected, got %s", order.Status)
	}
}

func TestCannotFillCancelledOrder(t *testing.T) {
	om := NewOrderManager()
	order := om.Create("000001.SZ", OrderBuy, OrderMarket, 100, 10.0)
	om.Submit(order.ID)
	om.Cancel(order.ID)

	err := om.Fill(order.ID, 100, 10.0)
	if err == nil {
		t.Error("expected error filling cancelled order")
	}
}

func TestCannotCancelFilledOrder(t *testing.T) {
	om := NewOrderManager()
	order := om.Create("000001.SZ", OrderBuy, OrderMarket, 100, 10.0)
	om.Submit(order.ID)
	om.Fill(order.ID, 100, 10.0)

	err := om.Cancel(order.ID)
	if err == nil {
		t.Error("expected error cancelling filled order")
	}
}
