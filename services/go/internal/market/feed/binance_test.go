package feed

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestBinanceFeedConstruction(t *testing.T) {
	f := NewBinanceFeed()
	assert.Equal(t, "binance", f.Name())
}

func TestBinanceFeedInterval(t *testing.T) {
	f := NewBinanceFeed("1m")
	assert.Equal(t, "1m", f.interval)
}

func TestBinanceFeedDefaultInterval(t *testing.T) {
	f := NewBinanceFeed()
	assert.Equal(t, "1m", f.interval)
}

func TestBinanceFeedHandlers(t *testing.T) {
	f := NewBinanceFeed()
	received := false
	f.OnBar(func(bar Bar) { received = true })
	f.OnError(func(symbol string, err error) {})
	assert.NotNil(t, f.barCb, "OnBar handler not registered")
	// Verify callback is callable
	f.barCb(Bar{Symbol: "BTCUSDT", Close: 50000})
	assert.True(t, received, "OnBar callback should have been called")
	assert.NotNil(t, f.errCb, "OnError handler not registered")
}

func TestBinanceStreamName(t *testing.T) {
	tests := []struct {
		symbol   string
		interval string
		expected string
	}{
		{"btcusdt", "1m", "btcusdt@kline_1m"},
		{"ethusdt", "5m", "ethusdt@kline_5m"},
		{"BTC-USDT", "1h", "btcusdt@kline_1h"},
	}
	for _, tc := range tests {
		result := binanceStreamName(tc.symbol, tc.interval)
		assert.Equal(t, tc.expected, result,
			"binanceStreamName(%q, %q) = %q, want %q", tc.symbol, tc.interval, result, tc.expected)
	}
}
