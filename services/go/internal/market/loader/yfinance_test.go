package loader

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestYFinanceName(t *testing.T) {
	loader := &YFinanceLoader{}
	assert.Equal(t, "yfinance", loader.Name())
}

func TestYFinanceFetchBars(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"chart":{"result":[{"timestamp":[1704153600,1704240000],"indicators":{"quote":[{"open":[150.0,151.0],"high":[152.0,153.0],"low":[149.0,150.0],"close":[151.5,152.5],"volume":[50000000,60000000]}]}}]}}`))
	}))
	defer server.Close()

	loader := &YFinanceLoader{client: http.DefaultClient, baseURL: server.URL}
	assert.True(t, loader.IsAvailable())

	bars, err := loader.FetchBars("AAPL", time.Now().Add(-7*24*time.Hour), time.Now())
	assert.NoError(t, err)
	assert.Equal(t, 2, len(bars))
	assert.Equal(t, "AAPL", bars[0].Symbol)
	assert.InDelta(t, 150.0, bars[0].Open, 0.01)
	assert.InDelta(t, 151.5, bars[0].Close, 0.01)
	assert.Equal(t, int64(50000000), bars[0].Volume)
	assert.Equal(t, "1d", bars[0].Frequency)
}

func TestYFinanceErrorResponse(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"chart":{"error":{"code":"Not Found","description":"No data found"}}}`))
	}))
	defer server.Close()

	loader := &YFinanceLoader{client: http.DefaultClient, baseURL: server.URL}
	bars, err := loader.FetchBars("INVALID", time.Now().Add(-7*24*time.Hour), time.Now())
	assert.Error(t, err)
	assert.Nil(t, bars)
}
