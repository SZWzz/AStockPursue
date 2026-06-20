package main

import (
	"log"
	"time"

	"github.com/astockpursue/go-core/internal/api"
	"github.com/astockpursue/go-core/internal/api/handler"
	"github.com/astockpursue/go-core/internal/config"
	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/market"
)

func main() {
	cfg := config.Load()

	factory := engine.NewEngineFactory()
	cache := market.NewMemoryCache(5 * time.Minute)
	ds := market.NewDataStore(nil, cache)

	backtestStore := handler.NewBacktestStore()
	btHandler := handler.NewBacktestHandler(backtestStore, ds, factory)

	pipeline := &engine.Pipeline{
		Engine:   factory.ForSymbol("000001"),
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
