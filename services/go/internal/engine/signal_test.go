package engine

import (
	"testing"
	"time"

	grpcpkg "github.com/astockpursue/go-core/internal/grpc"
)

func TestNewSignalAdapter(t *testing.T) {
	adapter := NewSignalAdapter("127.0.0.1:19999", 100*time.Millisecond)
	if adapter.address != "127.0.0.1:19999" {
		t.Errorf("expected address 127.0.0.1:19999, got %s", adapter.address)
	}
	if adapter.timeout != 100*time.Millisecond {
		t.Errorf("expected timeout 100ms, got %v", adapter.timeout)
	}
	if adapter.connMgr != nil {
		t.Error("expected nil connMgr when using NewSignalAdapter")
	}
}

func TestNewSignalAdapterFromConnMgr(t *testing.T) {
	mgr := new(grpcpkg.ConnManager)
	adapter := NewSignalAdapterFromConnMgr(mgr, 200*time.Millisecond)
	if adapter.connMgr != mgr {
		t.Error("expected connMgr to be set from constructor")
	}
	if adapter.timeout != 200*time.Millisecond {
		t.Errorf("expected timeout 200ms, got %v", adapter.timeout)
	}
}

func TestSignalAdapterConnMgrNilConnection(t *testing.T) {
	// ConnManager with nil connection should return error
	mgr := new(grpcpkg.ConnManager)
	adapter := NewSignalAdapterFromConnMgr(mgr, 100*time.Millisecond)
	bars := []interface{}{&Bar{Symbol: "000001.SZ", Open: 10, High: 11, Low: 9, Close: 10.5, Volume: 1000000}}
	sig, err := adapter.Generate(bars, time.Now())
	if err == nil {
		t.Error("expected error when ConnManager has no active connection")
	}
	if sig != nil {
		t.Error("expected nil signals on error")
	}
}

func TestSignalAdapterTimeout(t *testing.T) {
	// Use non-routable address with short timeout to force timeout
	adapter := NewSignalAdapter("127.0.0.1:19999", 50*time.Millisecond)
	bars := []interface{}{&Bar{Symbol: "000001.SZ", Open: 10, High: 11, Low: 9, Close: 10.5, Volume: 1000000}}
	sig, err := adapter.Generate(bars, time.Now())
	if err == nil {
		t.Error("expected timeout error for unreachable gRPC server")
	}
	if sig != nil {
		t.Error("expected nil signals on error")
	}
}
