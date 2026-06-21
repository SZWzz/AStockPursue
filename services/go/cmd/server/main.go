package main

import (
	"context"
	"database/sql"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/astockpursue/go-core/internal/api"
	"github.com/astockpursue/go-core/internal/api/handler"
	"github.com/astockpursue/go-core/internal/broker"
	"github.com/astockpursue/go-core/internal/config"
	"github.com/astockpursue/go-core/internal/db"
	"github.com/astockpursue/go-core/internal/engine"
	factorv1 "github.com/astockpursue/go-core/internal/gen/factor/v1"
	signalv1 "github.com/astockpursue/go-core/internal/gen/signal/v1"
	workflowv1 "github.com/astockpursue/go-core/internal/gen/workflow/v1"
	grpcpkg "github.com/astockpursue/go-core/internal/grpc"
	"github.com/astockpursue/go-core/internal/market"
	"github.com/astockpursue/go-core/internal/ml"
	"github.com/astockpursue/go-core/internal/notify"
	"github.com/astockpursue/go-core/internal/research"
	_ "modernc.org/sqlite"
)

func main() {
	cfg := config.Load()

	factory := engine.NewEngineFactory()
	cache := market.NewMemoryCache(5*time.Minute, 10000)
	localStore := market.NewLocalStore(cfg.DataDir + "/bars")
	ds := market.NewDataStore(nil, cache).WithLocalStore(localStore)

	// Backtest repository: try PostgreSQL, fall back to in-memory
	var repo handler.BacktestRepository
	timescaleDB, err := db.NewTimescaleDB(context.Background(), cfg.DatabaseURL)
	if err != nil {
		log.Printf("DB unavailable, using in-memory backtest store: %v", err)
		repo = handler.NewBacktestStore()
	} else if err := timescaleDB.InitSchema(context.Background()); err != nil {
		log.Printf("init schema failed, using in-memory backtest store: %v", err)
		timescaleDB.Close()
		repo = handler.NewBacktestStore()
	} else {
		defer timescaleDB.Close()
		repo = db.NewPostgresBacktestStore(timescaleDB)
		log.Print("DB connected, using PostgreSQL backtest store")
	}

	btHandler := handler.NewBacktestHandler(repo, ds, factory)

	// gRPC connection to Python research layer
	connMgr := grpcpkg.NewConnManager("localhost:8902", 30*time.Second)
	if err := connMgr.Connect(context.Background()); err != nil {
		log.Printf("gRPC: python research layer unavailable, retrying in background...")
	}
	go connMgr.StartHealthCheck(context.Background())

	pipeline := &engine.Pipeline{
		Engine:    factory.ForSymbol("000001"),
		Portfolio: &engine.Portfolio{
			Cash:      100000,
			Equity:    100000,
			Positions: make(map[string]*engine.Position),
		},
		Signal:   engine.NewSignalAdapterFromConnMgr(connMgr, 10*time.Second),
		Risk:     engine.NewRiskManager(engine.RiskConfig{}),
		OM:       engine.NewOrderManager(),
		LastBars: make(map[string]interface{}),
	}
	runner := engine.NewLiveTradingRunner(pipeline, 1*time.Minute)
	trHandler := handler.NewTradingHandler(runner)

	marketH := handler.NewMarketHandler(ds)

	// Try to connect brokers (optional — API keys from env)
	var binanceBroker, okxBroker broker.Broker
	if key := os.Getenv("BINANCE_API_KEY"); key != "" {
		if b, err := broker.New("binance", broker.BrokerConfig{
			APIKey: key, Secret: os.Getenv("BINANCE_SECRET"),
			Testnet: os.Getenv("BINANCE_TESTNET") == "true",
		}); err == nil {
			binanceBroker = b
			log.Print("Binance broker connected")
		}
	}
	if key := os.Getenv("OKX_API_KEY"); key != "" {
		if b, err := broker.New("okx", broker.BrokerConfig{
			APIKey: key, Secret: os.Getenv("OKX_SECRET"), Passphrase: os.Getenv("OKX_PASSPHRASE"),
		}); err == nil {
			okxBroker = b
			log.Print("OKX broker connected")
		}
	}
	brokerH := handler.NewBrokerHandler(binanceBroker, okxBroker)

	portfolioH := handler.NewPortfolioHandler(runner)
	authH := handler.NewAuthHandler()
	paperTradeH := handler.NewPaperTradingHandler(ds, factory)
	settingsH := handler.NewSettingsHandler()
	systemH := handler.NewSystemHandler()
	analysisH := handler.NewAnalysisHandler(ds)
	schedulerH := handler.NewSchedulerHandler(ds, factory, repo)
	screenerH := handler.NewScreenerHandler(ds)

	var factorClient factorv1.FactorServiceClient
	var workflowClient workflowv1.WorkflowServiceClient
	var signalClient signalv1.SignalServiceClient
	if conn := connMgr.GetConn(); conn != nil {
		factorClient = factorv1.NewFactorServiceClient(conn)
		workflowClient = workflowv1.NewWorkflowServiceClient(conn)
		signalClient = signalv1.NewSignalServiceClient(conn)
	}
	factorH := handler.NewFactorHandler(factorClient)
	workflowH := handler.NewWorkflowHandler(workflowClient)
	signalH := handler.NewSignalHandler(signalClient)

	// ── Research services (in-memory only, no DB persistence) ──────────
	researchServices := map[string]research.Service{
		"financials":  research.NewFinancialsService(nil, nil),
		"geopolitics": research.NewGeopoliticsService(nil, nil),
		"northbound":  research.NewNorthboundService(nil, nil),
		"news":        research.NewNewsService(nil, nil),
	}
	researchH := handler.NewResearchHandler(researchServices)

	// ── ML model registry (in-memory SQLite) ───────────────────────────
	mlDB, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		log.Fatalf("ml sqlite: %v", err)
	}
	mlRegistry := ml.NewModelRegistry(mlDB)
	if err := mlRegistry.Init(); err != nil {
		log.Fatalf("ml init: %v", err)
	}
	mlH := handler.NewMLHandler(mlRegistry)

	// ── Notification manager (in-memory SQLite) ────────────────────────
	notifDB, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		log.Fatalf("notify sqlite: %v", err)
	}
	notifManager := notify.NewManager(notifDB)
	notifH := handler.NewNotificationHandler(notifManager)

	healthH := &handler.HealthHandler{}
	wsHub := api.NewWSHub()
	r := api.NewRouter(healthH, btHandler, trHandler, marketH, brokerH, portfolioH, authH, paperTradeH, settingsH, systemH, analysisH, schedulerH, screenerH, factorH, workflowH, signalH, researchH, mlH, notifH, wsHub)

	// Preload seed data + simulated ticker feed
	go func() {
		time.Sleep(5 * time.Second)
		seedSymbols := []string{
			"000001.SZ", "600519.SH", "000300.SH", "600036.SH", "000858.SZ",
			"600000.SH", "601318.SH", "000002.SZ", "601166.SH", "600276.SH",
			"002415.SZ", "601012.SH",
		}
		end := time.Now()
		start := end.AddDate(0, 0, -30)
		loaded := 0
		for _, sym := range seedSymbols {
			if _, err := ds.GetBars(sym, start, end, "daily"); err == nil {
				loaded++
			}
		}
		log.Printf("seed data: %d/%d symbols preloaded", loaded, len(seedSymbols))
	}()

	go func() {
		prices := map[string]float64{"000001.SZ": 12.50, "600519.SH": 1680.00, "000300.SH": 3850.00}
		for range time.NewTicker(3 * time.Second).C {
			for sym, price := range prices {
				change := (float64(time.Now().UnixNano()%200) - 100) / 10000
				prices[sym] = price * (1 + change)
				wsHub.TickerFeed(sym, prices[sym], change)
			}
		}
	}()

	srv := &http.Server{
		Addr:    ":" + cfg.Port,
		Handler: r,
	}

	go func() {
		log.Printf("Starting go-core on :%s", cfg.Port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %v", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("shutting down server...")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Fatalf("server forced to shutdown: %v", err)
	}
}
