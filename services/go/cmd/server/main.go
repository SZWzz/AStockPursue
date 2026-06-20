package main

import (
	"context"
	"log"
	"time"

	"github.com/astockpursue/go-core/internal/api"
	"github.com/astockpursue/go-core/internal/api/handler"
	"github.com/astockpursue/go-core/internal/config"
	"github.com/astockpursue/go-core/internal/db"
	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/market"
)

func main() {
	cfg := config.Load()

	factory := engine.NewEngineFactory()
	cache := market.NewMemoryCache(5 * time.Minute)
	ds := market.NewDataStore(nil, cache)

	var repo handler.BacktestRepository
	timescaleDB, err := db.NewTimescaleDB(context.Background(), cfg.DatabaseURL)
	if err != nil {
		log.Printf("DB unavailable, using in-memory backtest store: %v", err)
		repo = handler.NewBacktestStore()
	} else {
		defer timescaleDB.Close()
		if err := timescaleDB.InitSchema(context.Background()); err != nil {
			log.Fatalf("init schema: %v", err)
		}
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
		Signal:   engine.NewNoopSignalAdapter(),
		Risk:     engine.NewRiskManager(engine.RiskConfig{}),
		LastBars: make(map[string]interface{}),
	}
	runner := engine.NewLiveTradingRunner(pipeline, 1*time.Minute)
	trHandler := handler.NewTradingHandler(runner)

	healthH := &handler.HealthHandler{}
	r := api.NewRouter(healthH, btHandler, trHandler)

	log.Printf("Starting go-core on :%s", cfg.Port)
	r.Run(":" + cfg.Port)
}
