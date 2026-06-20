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
	authH *handler.AuthHandler,
	paperTradeH *handler.PaperTradingHandler,
	settingsH *handler.SettingsHandler,
	systemH *handler.SystemHandler,
) *gin.Engine {
	r := gin.Default()

	// Public routes (no auth required)
	auth := r.Group("/api/v1/auth")
	auth.POST("/register", authH.Register)
	auth.POST("/login", authH.Login)

	sys := r.Group("/api/v1/system")
	sys.GET("/status", systemH.Status)
	sys.GET("/ping", systemH.Ping)

	r.GET("/health", health.Health)

	// Protected routes
	v1 := r.Group("/api/v1")
	v1.Use(middleware.Auth())
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

		pt := v1.Group("/paper-trading")
		pt.POST("", paperTradeH.CreateRun)
		pt.GET("", paperTradeH.ListRuns)
		pt.GET("/:id", paperTradeH.GetRun)
		pt.POST("/:id/start", paperTradeH.StartRun)
		pt.POST("/:id/stop", paperTradeH.StopRun)
		pt.DELETE("/:id", paperTradeH.DeleteRun)

		st := v1.Group("/settings")
		st.GET("", settingsH.Get)
		st.PUT("", settingsH.Update)
		st.DELETE("", settingsH.Reset)
	}

	return r
}
