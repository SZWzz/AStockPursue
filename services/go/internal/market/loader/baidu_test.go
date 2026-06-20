package loader

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestBaiduName(t *testing.T) {
	loader := &BaiduLoader{}
	assert.Equal(t, "baidu", loader.Name())
}

func TestBaiduFetchBarsHistory(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":0,"data":[{"date":"2026-01-02","open":10.0,"close":10.5,"high":11.0,"low":9.5,"volume":1000000}]}`))
	}))
	defer server.Close()

	loader := &BaiduLoader{client: http.DefaultClient, baseURL: server.URL}
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

func TestBaiduSZSymbol(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":0,"data":[{"date":"2026-01-02","open":10.0,"close":10.5,"high":11.0,"low":9.5,"volume":500000}]}`))
	}))
	defer server.Close()

	loader := &BaiduLoader{client: http.DefaultClient, baseURL: server.URL}
	bars, err := loader.FetchBars("000001", time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC), time.Date(2026, 1, 10, 0, 0, 0, 0, time.UTC))
	assert.NoError(t, err)
	assert.Equal(t, 1, len(bars))
	assert.Equal(t, "000001", bars[0].Symbol)
}

func TestBaiduBJSymbol(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":0,"data":[{"date":"2026-01-02","open":5.0,"close":5.5,"high":6.0,"low":4.5,"volume":200000}]}`))
	}))
	defer server.Close()

	loader := &BaiduLoader{client: http.DefaultClient, baseURL: server.URL}
	bars, err := loader.FetchBars("430047", time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC), time.Date(2026, 1, 10, 0, 0, 0, 0, time.UTC))
	assert.NoError(t, err)
	assert.Equal(t, 1, len(bars))
	assert.Equal(t, "430047", bars[0].Symbol)
}

func TestBaiduErrorStatus(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":1,"data":null}`))
	}))
	defer server.Close()

	loader := &BaiduLoader{client: http.DefaultClient, baseURL: server.URL}
	bars, err := loader.FetchBars("600000", time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC), time.Date(2026, 1, 10, 0, 0, 0, 0, time.UTC))
	assert.Error(t, err)
	assert.Nil(t, bars)
}

func TestBaiduEmptyData(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":0,"data":[]}`))
	}))
	defer server.Close()

	loader := &BaiduLoader{client: http.DefaultClient, baseURL: server.URL}
	bars, err := loader.FetchBars("600000", time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC), time.Date(2026, 1, 10, 0, 0, 0, 0, time.UTC))
	assert.NoError(t, err)
	assert.Equal(t, 0, len(bars))
}
