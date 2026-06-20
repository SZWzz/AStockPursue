package loader

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestEastMoneyFetchBars(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"data":{"klines":[
			"2026-01-02,10.0,11.0,9.5,10.5,1000000"
		]}}`))
	}))
	defer server.Close()

	em := &EastMoneyLoader{client: http.DefaultClient, baseURL: server.URL}
	assert.Equal(t, "eastmoney", em.Name())
	assert.True(t, em.IsAvailable())

	bars, err := em.FetchBars("000001", time.Now().Add(-7*24*time.Hour), time.Now())
	assert.NoError(t, err)
	assert.Equal(t, 1, len(bars))
	assert.Equal(t, "000001", bars[0].Symbol)
	assert.Equal(t, 10.5, bars[0].Close)
}
