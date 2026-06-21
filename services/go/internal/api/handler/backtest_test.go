package handler

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	"github.com/astockpursue/go-core/internal/engine"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
)

type mockBarLoader struct {
	bars map[string][]*commonv1.Bar
}

func (m *mockBarLoader) GetBars(symbol string, start, end time.Time, freq string) ([]*commonv1.Bar, error) {
	return m.bars[symbol], nil
}

func TestBacktestHandlerRun(t *testing.T) {
	store := NewBacktestStore()
	loader := &mockBarLoader{
		bars: map[string][]*commonv1.Bar{
			"000001": {
				{Symbol: "000001", Open: 10, Close: 10, Volume: 1000, Timestamp: time.Date(2026, 1, 2, 9, 30, 0, 0, time.UTC).UnixMilli()},
			},
		},
	}
	factory := engine.NewEngineFactory()
	h := NewBacktestHandler(store, loader, factory, nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	body := `{"symbols":["000001"],"start_date":"2026-01-01","end_date":"2026-01-10","frequency":"1d","initial_cash":100000}`
	c.Request, _ = http.NewRequest("POST", "/api/v1/backtest", strings.NewReader(body))
	c.Request.Header.Set("Content-Type", "application/json")

	h.Run(c)
	assert.Equal(t, 200, w.Code)

	var resp struct {
		ID     string                `json:"id"`
		Result *engine.BacktestResult `json:"result"`
	}
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.NotEmpty(t, resp.ID)
	assert.NotNil(t, resp.Result)
	assert.Equal(t, 100000.0, resp.Result.InitialCash)
}

func TestBacktestHandlerGetResult(t *testing.T) {
	store := NewBacktestStore()
	loader := &mockBarLoader{bars: make(map[string][]*commonv1.Bar)}
	factory := engine.NewEngineFactory()
	h := NewBacktestHandler(store, loader, factory, nil)

	result := &engine.BacktestResult{
		InitialCash: 100000, FinalEquity: 110000, TotalReturn: 0.1,
		EquityCurve: []engine.EquityPoint{
			{Timestamp: time.Now(), Equity: 100000, Cash: 100000},
		},
		Trades: []engine.TradeRecord{
			{Symbol: "000001", Side: "buy", Quantity: 100, Price: 10},
		},
	}
	id, err := store.Save(context.Background(), result)
	assert.NoError(t, err)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request, _ = http.NewRequest("GET", "/api/v1/backtest/"+id, nil)
	c.Params = []gin.Param{{Key: "id", Value: id}}

	h.GetResult(c)
	assert.Equal(t, 200, w.Code)
	assert.True(t, strings.Contains(w.Body.String(), `"total_return":0.1`))
}

func TestBacktestHandlerGetNotFound(t *testing.T) {
	store := NewBacktestStore()
	loader := &mockBarLoader{bars: make(map[string][]*commonv1.Bar)}
	factory := engine.NewEngineFactory()
	h := NewBacktestHandler(store, loader, factory, nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request, _ = http.NewRequest("GET", "/api/v1/backtest/nonexistent", nil)
	c.Params = []gin.Param{{Key: "id", Value: "nonexistent"}}

	h.GetResult(c)
	assert.Equal(t, 404, w.Code)
}
