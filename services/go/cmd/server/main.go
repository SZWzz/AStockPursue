package main

import (
	"context"
	"database/sql"
	"fmt"
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
	"github.com/astockpursue/go-core/internal/crypto"
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
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
	_ "modernc.org/sqlite"
)

// Server holds all runtime dependencies for the AStockPursue backend.
type Server struct {
	cfg       *config.Config
	router    *gin.Engine
	srv       *http.Server
	db        *pgxpool.Pool
	grpcConn  *grpcpkg.ConnManager
	wsHub     *api.WSHub
	shutdowns []func()
}

// NewServer initializes all components. Returns the server ready to Start.
func NewServer(cfg *config.Config) (*Server, error) {
	s := &Server{cfg: cfg}

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
	} else if err := db.RunMigrations(cfg.DatabaseURL); err != nil {
		log.Printf("migrations failed, using in-memory backtest store: %v", err)
		timescaleDB.Close()
		timescaleDB = nil
		repo = handler.NewBacktestStore()
	} else if err := timescaleDB.InitSchema(context.Background()); err != nil {
		log.Printf("init schema failed, using in-memory backtest store: %v", err)
		timescaleDB.Close()
		timescaleDB = nil
		repo = handler.NewBacktestStore()
	} else {
		s.shutdowns = append(s.shutdowns, func() { timescaleDB.Close() })
		repo = db.NewPGBacktestStore(timescaleDB.Pool())
		log.Print("DB connected, using PostgreSQL backtest store")
	}

	// Extract dbPool early for all handlers
	var dbPool *pgxpool.Pool
	if timescaleDB != nil {
		dbPool = timescaleDB.Pool()
	}

	// gRPC connection to Python research layer
	s.grpcConn = grpcpkg.NewConnManager("localhost:8902", 30*time.Second)
	if err := s.grpcConn.Connect(context.Background()); err != nil {
		log.Printf("gRPC: python research layer unavailable, retrying in background...")
	}
	go s.grpcConn.StartHealthCheck(context.Background())

	signalAdapter := engine.NewSignalAdapterFromConnMgr(s.grpcConn, 10*time.Second)
	btHandler := handler.NewBacktestHandler(repo, ds, factory, signalAdapter)

	pipeline := engine.NewPipeline(
		factory.ForSymbol("000001"),
		&engine.Portfolio{
			Cash:          100000,
			Equity:        100000,
			InitialEquity: 100000,
			Positions:     make(map[string]*engine.Position),
		},
		signalAdapter,
		engine.NewRiskManager(engine.RiskConfig{}),
		engine.NewOrderManager(),
	)
	runner := engine.NewLiveTradingRunner(pipeline, 1*time.Minute)
	trHandler := handler.NewTradingHandler(runner)

	marketH := handler.NewMarketHandler(ds)

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
	brokerH := handler.NewBrokerHandler(binanceBroker, okxBroker, dbPool)

	portfolioH := handler.NewPortfolioHandler(runner)
	paperTradeH := handler.NewPaperTradingHandler(ds, factory, dbPool)
	// Wire up promotion context for backtest→paper→live chain
	paperTradeH.SetBacktestRepo(repo)
	trHandler.SetPromotionContext(paperTradeH.Engine(), factory, ds)
	settingsH := handler.NewSettingsHandler(dbPool)
	systemH := handler.NewSystemHandler()
	analysisH := handler.NewAnalysisHandler(ds).WithTradingRunner(runner)
	schedulerH := handler.NewSchedulerHandler(ds, factory, repo, dbPool)
	screenerH := handler.NewScreenerHandler(ds)

	var factorClient factorv1.FactorServiceClient
	var workflowClient workflowv1.WorkflowServiceClient
	var signalClient signalv1.SignalServiceClient
	if conn := s.grpcConn.GetConn(); conn != nil {
		factorClient = factorv1.NewFactorServiceClient(conn)
		workflowClient = workflowv1.NewWorkflowServiceClient(conn)
		signalClient = signalv1.NewSignalServiceClient(conn)
	}
	factorH := handler.NewFactorHandler(factorClient, dbPool)
	workflowH := handler.NewWorkflowHandler(workflowClient, dbPool)
	signalH := handler.NewSignalHandler(signalClient, dbPool)

	researchServices := map[string]research.Service{
		"financials":  research.NewFinancialsService(nil, nil),
		"geopolitics": research.NewGeopoliticsService(nil, nil),
		"northbound":  research.NewNorthboundService(nil, nil),
		"news":        research.NewNewsRealService(&http.Client{Timeout: 10 * time.Second}, nil),
	}
	researchH := handler.NewResearchHandler(researchServices)

	var mlDB, notifDB *sql.DB
	if timescaleDB != nil {
		mlDB = timescaleDB.DB()
		notifDB = timescaleDB.DB()
		log.Print("ML and Notifications using PostgreSQL")
	} else {
		var err error
		mlDB, err = sql.Open("sqlite", ":memory:")
		if err != nil {
			return nil, fmt.Errorf("ml sqlite: %w", err)
		}
		notifDB, err = sql.Open("sqlite", ":memory:")
		if err != nil {
			return nil, fmt.Errorf("notify sqlite: %w", err)
		}
		log.Print("ML and Notifications using in-memory SQLite (DB unavailable)")
	}
	mlRegistry := ml.NewModelRegistry(mlDB)
	if err := mlRegistry.Init(); err != nil {
		return nil, fmt.Errorf("ml init: %w", err)
	}
	mlH := handler.NewMLHandler(mlRegistry)

	notifManager := notify.NewManager(notifDB)
	notifH := handler.NewNotificationHandler(notifManager)

	strategyH := handler.NewStrategyHandler(dbPool)

	s.db = dbPool

	userRepo := handler.NewUserRepository(dbPool)
	authH := handler.NewAuthHandler(userRepo)

	healthH := handler.NewHealthHandler(dbPool, s.grpcConn, nil)
	s.wsHub = api.NewWSHub()
	s.router = api.NewRouter(healthH, btHandler, trHandler, marketH, brokerH, portfolioH, authH, paperTradeH, settingsH, systemH, analysisH, schedulerH, screenerH, factorH, workflowH, signalH, researchH, mlH, notifH, strategyH, s.wsHub)

	// Preload seed data in background
	go func() {
		<-time.After(5 * time.Second)
		seedSymbols := cfg.SeedSymbols
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

	return s, nil
}

// Start runs the server and optional dev-mode ticker feed.
func (s *Server) Start() error {
	bgCtx, bgCancel := context.WithCancel(context.Background())
	s.shutdowns = append(s.shutdowns, bgCancel)

	// Mock ticker feed (development only)
	if s.cfg.DevMode {
		go func() {
			prices := map[string]float64{"000001.SZ": 12.50, "600519.SH": 1680.00, "000300.SH": 3850.00}
			ticker := time.NewTicker(3 * time.Second)
			defer ticker.Stop()
			for {
				select {
				case <-ticker.C:
					for sym, price := range prices {
						change := (float64(time.Now().UnixNano()%200) - 100) / 10000
						prices[sym] = price * (1 + change)
						s.wsHub.TickerFeed(sym, prices[sym], change)
					}
				case <-bgCtx.Done():
					return
				}
			}
		}()
	}

	s.srv = &http.Server{
		Addr:    ":" + s.cfg.Port,
		Handler: s.router,
	}

	go func() {
		log.Printf("Starting go-core on :%s", s.cfg.Port)
		if err := s.srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %v", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("shutting down server...")

	return s.Shutdown(context.Background())
}

// Shutdown gracefully stops the server.
func (s *Server) Shutdown(ctx context.Context) error {
	shutdownCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	if s.srv != nil {
		if err := s.srv.Shutdown(shutdownCtx); err != nil {
			log.Printf("server forced to shutdown: %v", err)
		}
	}
	for i := len(s.shutdowns) - 1; i >= 0; i-- {
		s.shutdowns[i]()
	}
	return nil
}

func main() {
	cfg := config.Load()

	if err := crypto.Init(cfg.EncryptionKey); err != nil {
		log.Fatalf("Failed to initialize crypto: %v", err)
	}

	srv, err := NewServer(cfg)
	if err != nil {
		log.Fatalf("failed to create server: %v", err)
	}

	if err := srv.Start(); err != nil {
		log.Fatalf("server error: %v", err)
	}

	log.Println("server stopped")
}
