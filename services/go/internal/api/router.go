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
	researchH *handler.ResearchHandler,
	mlH *handler.MLHandler,
	notifH *handler.NotificationHandler,
	strategyH *handler.StrategyHandler,
	wsHub *WSHub,
) *gin.Engine {
	r := gin.Default()

	// Public routes (no auth required)
	auth := r.Group("/api/v1/auth")
	auth.POST("/register", authH.Register)
	auth.POST("/login", authH.Login)

	sys := r.Group("/api/v1/system")
	sys.GET("/status", systemH.Status)
	sys.GET("/ping", systemH.Ping)

	r.GET("/health", health.FullCheck)
	r.GET("/ws", func(c *gin.Context) { wsHub.HandleWebSocket(c.Writer, c.Request) })

	// Protected routes
	v1 := r.Group("/api/v1")
	v1.Use(middleware.Auth())
	{
		bt := v1.Group("/backtest")
		bt.POST("", backtest.Run)
		bt.GET("", backtest.ListResults)
		bt.GET("/:id", backtest.GetResult)
		bt.POST("/:id/promote-to-paper", paperTradeH.PromoteToPaper)

		tr := v1.Group("/trading")
		tr.POST("/start", trading.Start)
		tr.POST("/stop", trading.Stop)
		tr.GET("/status", trading.Status)
		tr.GET("/orders", trading.ListOrders)
		tr.POST("/orders", trading.PlaceOrder)
		tr.DELETE("/orders/:id", trading.CancelOrder)

		mk := v1.Group("/market")
		mk.GET("/bars", marketH.GetBars)
		mk.GET("/symbols", marketH.ListSymbols)

		br := v1.Group("/broker")
		br.GET("/account", brokerH.GetAccount)
		br.GET("/positions", brokerH.GetPositions)
		br.GET("/list", brokerH.GetBrokers)
		br.POST("/connect", brokerH.Connect)
		br.POST("/disconnect", brokerH.Disconnect)
		br.POST("/credentials", brokerH.SaveCredentials)

		v1.GET("/portfolio", portfolioH.GetStatus)

		pt := v1.Group("/paper-trading")
		pt.POST("", paperTradeH.CreateRun)
		pt.GET("", paperTradeH.ListRuns)
		pt.GET("/:id", paperTradeH.GetRun)
		pt.POST("/:id/start", paperTradeH.StartRun)
		pt.POST("/:id/stop", paperTradeH.StopRun)
		pt.POST("/:id/promote-to-live", trading.PromoteToLive)
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
		an.POST("/test-data-source", analysisH.TestDataSource)
		an.POST("/test-llm", analysisH.TestLLM)

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

		// Factor routes (returns 503 if Python gRPC is down)
		fc := v1.Group("/factors")
		fc.GET("", factorH.ListFactors)
		fc.POST("/compute", factorH.ComputeFactor)
		fc.POST("/gp-mining", factorH.StartGPMining)

		// Workflow routes
		wc := v1.Group("/workflow")
		wc.GET("", workflowH.ListWorkflows)
		wc.POST("", workflowH.SaveWorkflow)
		wc.POST("/execute", workflowH.ExecuteWorkflow)
		wc.GET("/node/:id", workflowH.GetNodeResult)
		wc.POST("/:id/run", workflowH.RunWorkflow)

		// Signal routes
		sg := v1.Group("/signals")
		sg.GET("", signalH.ListSignals)
		sg.POST("/generate", signalH.Generate)
		sg.PUT("/:id/ack", signalH.AcknowledgeSignal)
		sg.PUT("/:id/dismiss", signalH.DismissSignal)

		// Research routes
		rsch := v1.Group("/research")
		rsch.GET("/:type", researchH.Analyze)
		rsch.GET("/:type/:symbol/history", researchH.History)

		// ML model routes
		mlg := v1.Group("/ml")
		mlg.GET("/models", mlH.ListModels)
		mlg.POST("/models", mlH.CreateModel)
		mlg.GET("/models/:id", mlH.GetModel)
		mlg.POST("/models/:id/archive", mlH.ArchiveModel)
		mlg.POST("/models/:id/train", mlH.TrainModel)

		// Notification routes
		ng := v1.Group("/notifications")
		ng.GET("", notifH.List)
		ng.POST("", notifH.Send)
		ng.POST("/:id/read", notifH.MarkRead)
		ng.POST("/read-all", notifH.MarkAllRead)
		ng.POST("/test-telegram", notifH.TestTelegram)
		ng.POST("/test-email", notifH.TestEmail)
		// Strategy routes
		stg := v1.Group("/strategy")
		stg.POST("", strategyH.Create)
		stg.GET("", strategyH.List)
		stg.GET("/:id", strategyH.Get)
		stg.PUT("/:id", strategyH.Update)
		stg.DELETE("/:id", strategyH.Delete)
	}

	return r
}
