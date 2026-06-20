package api

import (
	"github.com/astockpursue/go-core/internal/api/handler"
	"github.com/astockpursue/go-core/internal/api/middleware"
	"github.com/gin-gonic/gin"
)

func NewRouter(
	health *handler.HealthHandler,
	backtest *handler.BacktestHandler,
	trading *handler.TradingHandler,
	marketH *handler.MarketHandler,
	brokerH *handler.BrokerHandler,
	portfolioH *handler.PortfolioHandler,
) *gin.Engine {
	r := gin.Default()
	r.Use(middleware.Auth())

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

		mk := v1.Group("/market")
		mk.GET("/bars", marketH.GetBars)
		mk.GET("/symbols", marketH.ListSymbols)

		br := v1.Group("/broker")
		br.GET("/account", brokerH.GetAccount)
		br.GET("/positions", brokerH.GetPositions)
		br.GET("/list", brokerH.GetBrokers)

		v1.GET("/portfolio", portfolioH.GetStatus)
	}

	return r
}
