package broker

import (
	"context"
	"sync"
	"testing"

	"github.com/stretchr/testify/assert"
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
	assert.True(t, found, "futu broker should be registered after init()")
}

func TestFutuBrokerRequiresHost(t *testing.T) {
	// Creating a Futu broker without a valid host should still succeed at
	// construction time (lazy connect). TestConnection should fail.
	cfg := BrokerConfig{Name: "futu", Host: "localhost", Port: 11111}
	b, err := New("futu", cfg)
	assert.NoError(t, err, "unexpected construction error")
	assert.Equal(t, "futu", b.Name())

	// TestConnection will fail without a real FutuOpenD running — that's expected
	err = b.TestConnection(context.Background())
	if err == nil {
		t.Log("FutuOpenD appears to be running — connection test passed")
	} else {
		t.Logf("FutuOpenD not available (expected): %v", err)
	}
}

func TestFutuBrokerDefaultHostPort(t *testing.T) {
	cfg := BrokerConfig{Name: "futu"}
	b, err := New("futu", cfg)
	assert.NoError(t, err)
	assert.Equal(t, "futu", b.Name())

	// Verify we can call methods that don't require a connection
	fee := b.GetFeeRate("000001.SZ")
	assert.Equal(t, 0.0003, fee.Maker)
	assert.Equal(t, 0.0003, fee.Taker)
}

func TestFutuBroker_EnsureConnected_Concurrent(t *testing.T) {
	// This test verifies that concurrent calls to ensureConnected()
	// do not cause race conditions or multiple connections.
	b := &FutuBroker{
		cfg: BrokerConfig{Host: "127.0.0.1", Port: 11111}, // deliberately unreachable
	}

	var wg sync.WaitGroup
	errs := make(chan error, 10)

	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			errs <- b.ensureConnected()
		}()
	}
	wg.Wait()
	close(errs)

	// All should return an error (connection refused), not panic
	for err := range errs {
		if err == nil {
			t.Error("expected error for unreachable host")
		}
	}
}
