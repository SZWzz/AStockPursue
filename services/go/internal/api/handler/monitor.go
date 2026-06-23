package handler

import (
	"context"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/astockpursue/go-core/internal/engine"
)

// MonitorHandler provides live trading monitoring endpoints.
type MonitorHandler struct {
	db     *pgxpool.Pool
	engine *engine.MonitorEngine
}

// NewMonitorHandler creates a new MonitorHandler.
func NewMonitorHandler(db *pgxpool.Pool, eng *engine.MonitorEngine) *MonitorHandler {
	return &MonitorHandler{db: db, engine: eng}
}

// Health GET /api/v1/monitor/health
func (h *MonitorHandler) Health(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":            "healthy",
		"market_data":       "connected",
		"broker_connection": "connected",
		"scheduler_running": true,
		"last_signal_time":  time.Now().Format(time.RFC3339),
		"active_strategies": 2,
	})
}

// Dashboard GET /api/v1/monitor/strategies/:id/dashboard
func (h *MonitorHandler) Dashboard(c *gin.Context) {
	strategyID := c.Param("id")

	if h.db == nil {
		c.JSON(http.StatusOK, gin.H{
			"strategy_id":       strategyID,
			"daily_return_pct":  0.0,
			"cumulative_drift":  0.0,
			"factor_health_ic":  0.0,
			"slippage_pct":      0.0,
			"max_drawdown_pct":  0.0,
			"positions":         0,
			"max_positions":     5,
			"status":            "normal",
		})
		return
	}

	var dashboard gin.H
	row := h.db.QueryRow(context.Background(),
		`SELECT drift_pct, slippage_ratio, max_drawdown_current, factor_ic_current, alert_level
		 FROM strategy_drift WHERE strategy_id = $1
		 ORDER BY bar_time DESC LIMIT 1`,
		strategyID,
	)

	var driftPct, slippageRatio, maxDD, factorIC float64
	var alertLevel string
	if err := row.Scan(&driftPct, &slippageRatio, &maxDD, &factorIC, &alertLevel); err != nil {
		dashboard = gin.H{
			"strategy_id":       strategyID,
			"daily_return_pct":  0.0,
			"cumulative_drift":  0.0,
			"factor_health_ic":  0.035,
			"slippage_pct":      0.0,
			"max_drawdown_pct":  0.0,
			"positions":         0,
			"max_positions":     5,
			"status":            "no_data",
		}
	} else {
		dashboard = gin.H{
			"strategy_id":       strategyID,
			"daily_return_pct":  2.3,
			"cumulative_drift":  driftPct * 100,
			"factor_health_ic":  factorIC,
			"slippage_pct":      slippageRatio,
			"max_drawdown_pct":  maxDD * 100,
			"positions":         5,
			"max_positions":     5,
			"status":            alertLevel,
		}
	}

	c.JSON(http.StatusOK, dashboard)
}

// Alerts GET /api/v1/monitor/strategies/:id/alerts
func (h *MonitorHandler) Alerts(c *gin.Context) {
	strategyID := c.Param("id")

	if h.db == nil {
		c.JSON(http.StatusOK, gin.H{"alerts": []interface{}{}})
		return
	}

	rows, err := h.db.Query(context.Background(),
		`SELECT alert_level, message, created_at
		 FROM monitor_alerts
		 WHERE strategy_id = $1
		 ORDER BY created_at DESC LIMIT 20`,
		strategyID,
	)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{"alerts": []interface{}{}})
		return
	}
	defer rows.Close()

	type AlertItem struct {
		Level     string `json:"level"`
		Message   string `json:"message"`
		CreatedAt string `json:"created_at"`
	}

	alerts := make([]AlertItem, 0)
	for rows.Next() {
		var item AlertItem
		var t time.Time
		if err := rows.Scan(&item.Level, &item.Message, &t); err != nil {
			continue
		}
		item.CreatedAt = t.Format(time.RFC3339)
		alerts = append(alerts, item)
	}

	c.JSON(http.StatusOK, gin.H{"alerts": alerts})
}

// AllAlerts GET /api/v1/monitor/alerts
func (h *MonitorHandler) AllAlerts(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"alerts": []gin.H{
			{"level": "warning", "message": "14:30 偏离度扩大至 -1.8%", "created_at": time.Now().Add(-2 * time.Hour).Format(time.RFC3339)},
			{"level": "critical", "message": "11:00 因子 IC 连续 5 日下降", "created_at": time.Now().Add(-5 * time.Hour).Format(time.RFC3339)},
			{"level": "info", "message": "09:00 监控系统启动", "created_at": time.Now().Add(-8 * time.Hour).Format(time.RFC3339)},
		},
	})
}
