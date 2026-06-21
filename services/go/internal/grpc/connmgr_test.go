package grpc

import (
	"context"
	"testing"
	"time"
)

func TestConnManagerConnectTimeout(t *testing.T) {
	// Use a non-routable address to trigger timeout
	mgr := NewConnManager("127.0.0.1:19999", 1*time.Second)
	ctx := context.Background()
	err := mgr.Connect(ctx)
	if err == nil {
		t.Error("expected connection error for unreachable address")
	}
}

func TestConnManagerGetConnNilWhenDisconnected(t *testing.T) {
	mgr := NewConnManager("127.0.0.1:19999", 100*time.Millisecond)
	mgr.Connect(context.Background()) // will fail silently in test
	if conn := mgr.GetConn(); conn != nil {
		t.Error("expected nil conn when disconnected")
	}
}

func TestConnManagerStartStop(t *testing.T) {
	mgr := NewConnManager("127.0.0.1:19999", 100*time.Millisecond)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	mgr.Connect(ctx) // will fail, but health check loop should not panic
	go mgr.StartHealthCheck(ctx)
	time.Sleep(200 * time.Millisecond)
	cancel()
	// If we get here without panic, test passes
}
