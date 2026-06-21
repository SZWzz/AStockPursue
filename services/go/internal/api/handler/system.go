package handler

import (
	"net/http"
	"runtime"
	"time"

	"github.com/gin-gonic/gin"
)

// Version is set at build time via -ldflags:
//
//	go build -ldflags "-X github.com/astockpursue/go-core/internal/api/handler.Version=$(cat VERSION)"
var Version = "0.1.0"

// SystemHandler provides server status and diagnostics.
type SystemHandler struct {
	startTime time.Time
}

func NewSystemHandler() *SystemHandler {
	return &SystemHandler{startTime: time.Now()}
}

// Status returns server health, version, uptime and resource info.
// GET /api/v1/system/status
func (h *SystemHandler) Status(c *gin.Context) {
	var mem runtime.MemStats
	runtime.ReadMemStats(&mem)

	c.JSON(http.StatusOK, gin.H{
		"status":    "ok",
		"version":   Version,
		"go_version": runtime.Version(),
		"uptime_seconds": int(time.Since(h.startTime).Seconds()),
		"goroutines": runtime.NumGoroutine(),
		"memory_mb":  int(mem.Alloc / 1024 / 1024),
		"num_cpu":    runtime.NumCPU(),
	})
}

// Ping is a lightweight health check (no allocations).
// GET /api/v1/system/ping
func (h *SystemHandler) Ping(c *gin.Context) {
	c.String(http.StatusOK, "pong")
}
