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
	analysisH *handler.AnalysisHandler,
	schedulerH *handler.SchedulerHandler,
	screenerH *handler.ScreenerHandler,
	factorH *handler.FactorHandler,
	workflowH *handler.WorkflowHandler,
	signalH *handler.SignalHandler,
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

		an := v1.Group("/analysis")
		an.POST("/correlation", analysisH.Correlation)
		an.GET("/drawdown", analysisH.Drawdown)
		an.POST("/attribution", analysisH.Attribution)
		an.POST("/stress-test", analysisH.StressTest)

		sc := v1.Group("/scheduler")
		sc.POST("", schedulerH.CreateJob)
		sc.GET("", schedulerH.ListJobs)
		sc.GET("/:id", schedulerH.GetJob)
		sc.POST("/:id/start", schedulerH.StartJob)
		sc.POST("/:id/pause", schedulerH.PauseJob)
		sc.DELETE("/:id", schedulerH.DeleteJob)

		sr := v1.Group("/screener")
		sr.POST("", screenerH.Screen)
		sr.GET("/movers", screenerH.TopMovers)
		sr.GET("/overview", screenerH.MarketOverview)

		// Factor routes
		fc := v1.Group("/factor")
		fc.POST("/compute", factorH.ComputeFactor)
		fc.POST("/gp-mining", factorH.StartGPMining)

		// Workflow routes
		wc := v1.Group("/workflow")
		wc.POST("/execute", workflowH.ExecuteWorkflow)
		wc.GET("/node/:id", workflowH.GetNodeResult)

		// Signal routes
		sg := v1.Group("/signal")
		sg.POST("/generate", signalH.Generate)
	}

	return r
}
