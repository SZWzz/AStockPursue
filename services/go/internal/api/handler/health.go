package handler

import (
	"context"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"

	grpcpkg "github.com/astockpursue/go-core/internal/grpc"
)

// Pinger abstracts a service that supports Ping(ctx) for health checks.
type Pinger interface {
	Ping(ctx context.Context) error
}

// HealthHandler performs deep health checks against backend dependencies.
type HealthHandler struct {
	db          *pgxpool.Pool
	connMgr     *grpcpkg.ConnManager
	redisClient Pinger
}

// NewHealthHandler creates a HealthHandler with optional dependencies.
// Pass nil for any dependency that is not configured.
func NewHealthHandler(db *pgxpool.Pool, connMgr *grpcpkg.ConnManager, redisClient Pinger) *HealthHandler {
	return &HealthHandler{db: db, connMgr: connMgr, redisClient: redisClient}
}

// FullCheck probes DB, gRPC, and Redis and returns structured status.
// GET /health
func (h *HealthHandler) FullCheck(c *gin.Context) {
	status := "ok"
	dbStatus := "ok"
	grpcStatus := "ok"
	redisStatus := "ok"

	// Check DB
	if h.db == nil {
		dbStatus = "disconnected"
		status = "degraded"
	} else {
		ctx, cancel := context.WithTimeout(c.Request.Context(), 2*time.Second)
		defer cancel()
		if err := h.db.Ping(ctx); err != nil {
			dbStatus = "error"
			status = "degraded"
		}
	}

	// Check gRPC
	if h.connMgr == nil || h.connMgr.GetConn() == nil {
		grpcStatus = "disconnected"
		status = "degraded"
	}

	// Check Redis
	if h.redisClient == nil {
		redisStatus = "disconnected"
		status = "degraded"
	} else {
		ctx, cancel := context.WithTimeout(c.Request.Context(), 2*time.Second)
		defer cancel()
		if err := h.redisClient.Ping(ctx); err != nil {
			redisStatus = "error"
			status = "degraded"
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"status": status,
		"db":     dbStatus,
		"grpc":   grpcStatus,
		"redis":  redisStatus,
	})
}
