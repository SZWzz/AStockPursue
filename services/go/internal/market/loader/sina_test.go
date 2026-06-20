package loader

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestSinaName(t *testing.T) {
	loader := &SinaLoader{}
	assert.Equal(t, "sina", loader.Name())
}

func TestSinaFetchBarsRealTime(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`var hq_str_sh600000="浦发银行,10.00,9.95,10.50,11.00,9.50,0,0,1000000,50000000,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2026-01-02,15:00:00,0.00"`))
	}))
	defer server.Close()

	loader := &SinaLoader{client: http.DefaultClient, baseURL: server.URL}
	assert.True(t, loader.IsAvailable())

	bars, err := loader.FetchBars("600000", time.Time{}, time.Time{})
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

func TestSinaFetchBarsHistoricalError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`var hq_str_sh600000="..."`))
	}))
	defer server.Close()

	loader := &SinaLoader{client: http.DefaultClient, baseURL: server.URL}
	start := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	end := time.Date(2026, 1, 10, 0, 0, 0, 0, time.UTC)
	bars, err := loader.FetchBars("600000", start, end)

	assert.Error(t, err)
	assert.Nil(t, bars)
	assert.Contains(t, err.Error(), "historical")
}

func TestSinaSZSymbol(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`var hq_str_sz000001="平安银行,10.00,9.95,10.50,11.00,9.50,0,0,1000000,50000000,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2026-01-02,15:00:00,0.00"`))
	}))
	defer server.Close()

	loader := &SinaLoader{client: http.DefaultClient, baseURL: server.URL}
	bars, err := loader.FetchBars("000001", time.Time{}, time.Time{})
	assert.NoError(t, err)
	assert.Equal(t, 1, len(bars))
	assert.Equal(t, "000001", bars[0].Symbol)
}

func TestSinaBJSymbol(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`var hq_str_bj430047="诺思兰德,10.00,9.95,10.50,11.00,9.50,0,0,1000000,50000000,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2026-01-02,15:00:00,0.00"`))
	}))
	defer server.Close()

	loader := &SinaLoader{client: http.DefaultClient, baseURL: server.URL}
	bars, err := loader.FetchBars("430047", time.Time{}, time.Time{})
	assert.NoError(t, err)
	assert.Equal(t, 1, len(bars))
	assert.Equal(t, "430047", bars[0].Symbol)
}

func TestSinaParseEmpty(t *testing.T) {
	loader := &SinaLoader{}
	_, err := loader.parseResponse("", "600000")
	assert.Error(t, err)
}

func TestSinaParseShort(t *testing.T) {
	loader := &SinaLoader{}
	_, err := loader.parseResponse(`var hq_str_sh600000="too,short"`, "600000")
	assert.Error(t, err)
}
