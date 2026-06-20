package api

import (
	"github.com/gin-gonic/gin"
	"github.com/astockpursue/go-core/internal/api/handler"
)

func NewRouter(h *handler.HealthHandler) *gin.Engine {
	r := gin.Default()
	r.GET("/health", h.Health)
	return r
}
