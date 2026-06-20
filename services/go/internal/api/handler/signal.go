package handler

import (
	"context"
	"net/http"
	"time"

	signalv1 "github.com/astockpursue/go-core/internal/gen/signal/v1"
	"github.com/gin-gonic/gin"
)

// SignalHandler proxies signal generation requests to Python SignalService via gRPC.
type SignalHandler struct {
	client signalv1.SignalServiceClient
}

// NewSignalHandler creates a new SignalHandler.
func NewSignalHandler(client signalv1.SignalServiceClient) *SignalHandler {
	return &SignalHandler{client: client}
}

// Generate calls Python SignalService.GenerateSignals and returns target weights.
// POST /api/v1/signal/generate
func (h *SignalHandler) Generate(c *gin.Context) {
	if h.client == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error":   "Python gRPC service is not running",
			"message": "Start the Python research layer: cd services/python && python -m src.grpc.server",
		})
		return
	}
	var req struct {
		StrategyName string            `json:"strategy_name"`
		Symbols      []string          `json:"symbols"`
		StartDate    string            `json:"start_date"`
		EndDate      string            `json:"end_date"`
		Params       map[string]string `json:"params"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if len(req.Symbols) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "symbols required"})
		return
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	pbReq := &signalv1.SignalRequest{
		StrategyName: req.StrategyName,
		Mode:         "batch",
		Params:       req.Params,
	}

	resp, err := h.client.GenerateSignals(ctx, pbReq)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if resp.Error != "" {
		c.JSON(http.StatusInternalServerError, gin.H{"error": resp.Error})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"weights": resp.Weights,
		"count":   len(resp.Weights),
	})
}
