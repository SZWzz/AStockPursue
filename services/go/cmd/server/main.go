package main

import (
	"context"
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
	"github.com/astockpursue/go-core/internal/market"
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

	pipeline := &engine.Pipeline{
		Engine:    factory.ForSymbol("000001"),
		Portfolio: &engine.Portfolio{
			Cash:      100000,
			Equity:    100000,
			Positions: make(map[string]*engine.Position),
		},
		Signal:   engine.NewSignalAdapter("localhost:8902", 10*time.Second),
		Risk:     engine.NewRiskManager(engine.RiskConfig{}),
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

	healthH := &handler.HealthHandler{}
	r := api.NewRouter(healthH, btHandler, trHandler, marketH, brokerH, portfolioH, authH, paperTradeH, settingsH, systemH)

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
