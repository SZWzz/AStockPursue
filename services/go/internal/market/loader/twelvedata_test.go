package loader

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestTwelveDataName(t *testing.T) {
	loader := &TwelveDataLoader{}
	assert.Equal(t, "twelvedata", loader.Name())
}

func TestTwelveDataFetchBars(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"meta":{"symbol":"600000.SHH"},"values":[
			{"datetime":"2026-01-02","open":"10.00","high":"11.00","low":"9.50","close":"10.50","volume":"1000000"}
		],"status":"ok"}`))
	}))
	defer server.Close()

	loader := &TwelveDataLoader{client: http.DefaultClient, baseURL: server.URL}
	assert.True(t, loader.IsAvailable())

	start := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	end := time.Date(2026, 1, 10, 0, 0, 0, 0, time.UTC)
	bars, err := loader.FetchBars("600000", start, end)

	assert.NoError(t, err)
	assert.Equal(t, 1, len(bars))
	assert.Equal(t, "600000", bars[0].Symbol)
	assert.InDelta(t, 10.0, bars[0].Open, 0.01)
	assert.InDelta(t, 10.5, bars[0].Close, 0.01)
	assert.InDelta(t, 11.0, bars[0].High, 0.01)
	assert.InDelta(t, 9.5, bars[0].Low, 0.01)
	assert.Equal(t, int64(1000000), bars[0].Volume)
	assert.Equal(t, "1d", bars[0].Frequency)
}

func TestTwelveDataSZSymbol(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"values":[{"datetime":"2026-01-02","open":"5.00","high":"5.50","low":"4.50","close":"5.25","volume":"500000"}],"status":"ok"}`))
	}))
	defer server.Close()

	loader := &TwelveDataLoader{client: http.DefaultClient, baseURL: server.URL}
	bars, err := loader.FetchBars("000001", time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC), time.Date(2026, 1, 10, 0, 0, 0, 0, time.UTC))
	assert.NoError(t, err)
	assert.Equal(t, 1, len(bars))
	assert.Equal(t, "000001", bars[0].Symbol)
}

func TestTwelveDataBJSymbol(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"values":[{"datetime":"2026-01-02","open":"5.00","high":"6.00","low":"4.50","close":"5.50","volume":"200000"}],"status":"ok"}`))
	}))
	defer server.Close()

	loader := &TwelveDataLoader{client: http.DefaultClient, baseURL: server.URL}
	bars, err := loader.FetchBars("430047", time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC), time.Date(2026, 1, 10, 0, 0, 0, 0, time.UTC))
	assert.NoError(t, err)
	assert.Equal(t, 1, len(bars))
	assert.Equal(t, "430047", bars[0].Symbol)
}

func TestTwelveDataErrorStatus(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"error","message":"Invalid API key"}`))
	}))
	defer server.Close()

	loader := &TwelveDataLoader{client: http.DefaultClient, baseURL: server.URL}
	bars, err := loader.FetchBars("600000", time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC), time.Date(2026, 1, 10, 0, 0, 0, 0, time.UTC))
	assert.Error(t, err)
	assert.Nil(t, bars)
}

func TestTwelveDataStringParsing(t *testing.T) {
	// Verify fractional string values parse correctly
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"values":[
			{"datetime":"2026-01-02","open":"123.456","high":"130.789","low":"120.123","close":"128.500","volume":"999888777"}
		],"status":"ok"}`))
	}))
	defer server.Close()

	loader := &TwelveDataLoader{client: http.DefaultClient, baseURL: server.URL}
	bars, err := loader.FetchBars("600000", time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC), time.Date(2026, 1, 10, 0, 0, 0, 0, time.UTC))
	assert.NoError(t, err)
	assert.Equal(t, 1, len(bars))
	assert.InDelta(t, 123.456, bars[0].Open, 0.001)
	assert.InDelta(t, 128.500, bars[0].Close, 0.001)
	assert.InDelta(t, 130.789, bars[0].High, 0.001)
	assert.InDelta(t, 120.123, bars[0].Low, 0.001)
	assert.Equal(t, int64(999888777), bars[0].Volume)
}
