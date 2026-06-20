package main

import (
	"log"

	"github.com/astockpursue/go-core/internal/api"
	"github.com/astockpursue/go-core/internal/api/handler"
	"github.com/astockpursue/go-core/internal/config"
)

func main() {
	cfg := config.Load()
	h := &handler.HealthHandler{}
	r := api.NewRouter(h)
	log.Printf("Starting go-core on :%s", cfg.Port)
	r.Run(":" + cfg.Port)
}
