package loader

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestCoinGeckoName(t *testing.T) {
	loader := &CoinGeckoLoader{}
	assert.Equal(t, "coingecko", loader.Name())
}

func TestCoinGeckoFetchBars(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"prices":[[1704153600000,45000.5],[1704240000000,46000.8]],"total_volumes":[[1704153600000,12000000000],[1704240000000,13000000000]]}`))
	}))
	defer server.Close()

	loader := &CoinGeckoLoader{client: http.DefaultClient, baseURL: server.URL}
	assert.True(t, loader.IsAvailable())

	bars, err := loader.FetchBars("bitcoin", time.Now().Add(-7*24*time.Hour), time.Now())
	assert.NoError(t, err)
	assert.Equal(t, 2, len(bars))
	assert.Equal(t, "bitcoin", bars[0].Symbol)
	assert.InDelta(t, 45000.5, bars[0].Open, 0.01)
	assert.InDelta(t, 45000.5, bars[0].Close, 0.01) // OHLC same for crypto (only price available)
	assert.Equal(t, "1d", bars[0].Frequency)
}

func TestCoinGeckoEmptyResponse(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"prices":[]}`))
	}))
	defer server.Close()

	loader := &CoinGeckoLoader{client: http.DefaultClient, baseURL: server.URL}
	bars, err := loader.FetchBars("invalidcoin", time.Now().Add(-7*24*time.Hour), time.Now())
	assert.NoError(t, err)
	assert.Equal(t, 0, len(bars))
}
