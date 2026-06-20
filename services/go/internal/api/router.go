package api

import (
	"github.com/astockpursue/go-core/internal/api/handler"
	"github.com/gin-gonic/gin"
)

func NewRouter(
	health *handler.HealthHandler,
	backtest *handler.BacktestHandler,
	trading *handler.TradingHandler,
) *gin.Engine {
	r := gin.Default()

	r.GET("/health", health.Health)

	v1 := r.Group("/api/v1")
	{
		bt := v1.Group("/backtest")
		bt.POST("", backtest.Run)
		bt.GET("", backtest.ListResults)
		bt.GET("/:id", backtest.GetResult)

		tr := v1.Group("/trading")
		tr.POST("/start", trading.Start)
		tr.POST("/stop", trading.Stop)
		tr.GET("/status", trading.Status)
	}

	return r
}
