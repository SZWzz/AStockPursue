package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func newTestMonitorHandler() *MonitorHandler {
	monitorEng := engine.NewMonitorEngine()
	return NewMonitorHandler(nil, monitorEng)
}

func TestMonitorHealth_ReturnsHealthStatus(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestMonitorHandler()

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("GET", "/api/v1/monitor/health", nil)

	h.Health(c)

	assert.Equal(t, http.StatusOK, w.Code)

	var resp map[string]interface{}
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	require.NoError(t, err)

	assert.Equal(t, "healthy", resp["status"])
	assert.Equal(t, "connected", resp["market_data"])
	assert.Equal(t, "connected", resp["broker_connection"])
	assert.Equal(t, true, resp["scheduler_running"])
	assert.Equal(t, float64(2), resp["active_strategies"])
}

func TestMonitorDashboard_NilDBReturnsDefault(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestMonitorHandler()

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("GET", "/api/v1/monitor/strategies/1/dashboard", nil)
	c.Params = gin.Params{{Key: "id", Value: "1"}}

	h.Dashboard(c)

	assert.Equal(t, http.StatusOK, w.Code)

	var resp map[string]interface{}
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	require.NoError(t, err)

	assert.Equal(t, "1", resp["strategy_id"])
	assert.Equal(t, float64(0), resp["daily_return_pct"])
	assert.Equal(t, float64(0), resp["cumulative_drift"])
	assert.Equal(t, float64(0), resp["slippage_pct"])
	assert.Equal(t, "normal", resp["status"])
}

func TestMonitorAlerts_NilDBReturnsEmptyArray(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestMonitorHandler()

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("GET", "/api/v1/monitor/strategies/1/alerts", nil)
	c.Params = gin.Params{{Key: "id", Value: "1"}}

	h.Alerts(c)

	assert.Equal(t, http.StatusOK, w.Code)

	var resp map[string]interface{}
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	require.NoError(t, err)

	alerts, ok := resp["alerts"].([]interface{})
	assert.True(t, ok, "alerts should be an array")
	assert.Equal(t, 0, len(alerts))
}

func TestMonitorAllAlerts_ReturnsRecentlyAlerts(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestMonitorHandler()

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("GET", "/api/v1/monitor/alerts", nil)

	h.AllAlerts(c)

	assert.Equal(t, http.StatusOK, w.Code)

	var resp map[string]interface{}
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	require.NoError(t, err)

	alerts, ok := resp["alerts"].([]interface{})
	assert.True(t, ok, "alerts should be an array")
	assert.Equal(t, 3, len(alerts))

	firstAlert := alerts[0].(map[string]interface{})
	assert.Equal(t, "warning", firstAlert["level"])
	assert.Contains(t, firstAlert["message"], "偏离度")
}

func TestMonitorDashboard_DifferentStrategyIDs(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestMonitorHandler()

	testCases := []string{"1", "42", "999"}
	for _, strategyID := range testCases {
		t.Run("strategy_"+strategyID, func(t *testing.T) {
			w := httptest.NewRecorder()
			c, _ := gin.CreateTestContext(w)
			c.Request = httptest.NewRequest("GET", "/api/v1/monitor/strategies/"+strategyID+"/dashboard", nil)
			c.Params = gin.Params{{Key: "id", Value: strategyID}}

			h.Dashboard(c)

			assert.Equal(t, http.StatusOK, w.Code)

			var resp map[string]interface{}
			err := json.Unmarshal(w.Body.Bytes(), &resp)
			require.NoError(t, err)
			assert.Equal(t, strategyID, resp["strategy_id"])
		})
	}
}

func TestMonitorAlerts_DifferentStrategyIDs(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestMonitorHandler()

	testCases := []string{"1", "42", "999"}
	for _, strategyID := range testCases {
		t.Run("strategy_"+strategyID, func(t *testing.T) {
			w := httptest.NewRecorder()
			c, _ := gin.CreateTestContext(w)
			c.Request = httptest.NewRequest("GET", "/api/v1/monitor/strategies/"+strategyID+"/alerts", nil)
			c.Params = gin.Params{{Key: "id", Value: strategyID}}

			h.Alerts(c)

			assert.Equal(t, http.StatusOK, w.Code)

			var resp map[string]interface{}
			err := json.Unmarshal(w.Body.Bytes(), &resp)
			require.NoError(t, err)

			alerts, ok := resp["alerts"].([]interface{})
			assert.True(t, ok, "alerts should be an array")
			assert.Equal(t, 0, len(alerts))
		})
	}
}
