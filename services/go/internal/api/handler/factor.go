package handler

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"time"

	factorv1 "github.com/astockpursue/go-core/internal/gen/factor/v1"
	"github.com/gin-gonic/gin"
)

// FactorHandler proxies factor computation and GP mining to Python FactorService via gRPC.
type FactorHandler struct {
	client factorv1.FactorServiceClient
}

// NewFactorHandler creates a new FactorHandler.
func NewFactorHandler(client factorv1.FactorServiceClient) *FactorHandler {
	return &FactorHandler{client: client}
}

func (h *FactorHandler) grpcUnavailable(c *gin.Context) {
	c.JSON(http.StatusServiceUnavailable, gin.H{
		"error":   "Python gRPC service is not running",
		"message": "Start the Python research layer: cd services/python && python -m src.grpc.server",
	})
}

// ComputeFactor evaluates a factor formula on the given symbols.
// POST /api/v1/factor/compute
func (h *FactorHandler) ComputeFactor(c *gin.Context) {
	if h.client == nil {
		h.grpcUnavailable(c)
		return
	}
	var req struct {
		Formula   string   `json:"formula" binding:"required"`
		Symbols   []string `json:"symbols" binding:"required"`
		StartDate string   `json:"start_date"`
		EndDate   string   `json:"end_date"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), 30*time.Second)
	defer cancel()

	pbReq := &factorv1.FactorRequest{
		Formula:   req.Formula,
		Symbols:   req.Symbols,
		StartDate: req.StartDate,
		EndDate:   req.EndDate,
	}

	resp, err := h.client.ComputeFactor(ctx, pbReq)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if resp.Error != "" {
		c.JSON(http.StatusInternalServerError, gin.H{"error": resp.Error})
		return
	}

	c.JSON(http.StatusOK, gin.H{"values": resp.Values, "count": len(resp.Values)})
}

// StartGPMining starts a GP evolution run and streams results via SSE.
// POST /api/v1/factor/gp-mining
func (h *FactorHandler) StartGPMining(c *gin.Context) {
	if h.client == nil {
		h.grpcUnavailable(c)
		return
	}
	var req struct {
		Pool           string `json:"pool"`
		Generations    int32  `json:"generations"`
		PopulationSize int32  `json:"population_size"`
		FitnessMetric  string `json:"fitness_metric"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if req.Pool == "" {
		req.Pool = "a_share"
	}
	if req.Generations == 0 {
		req.Generations = 20
	}
	if req.PopulationSize == 0 {
		req.PopulationSize = 200
	}
	if req.FitnessMetric == "" {
		req.FitnessMetric = "composite"
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), 10*time.Minute)
	defer cancel()

	pbReq := &factorv1.GPRequest{
		Pool:           req.Pool,
		Generations:    req.Generations,
		PopulationSize: req.PopulationSize,
		FitnessMetric:  req.FitnessMetric,
	}

	stream, err := h.client.StartGPMining(ctx, pbReq)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.Header("Content-Type", "text/event-stream")
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")

	c.Stream(func(w io.Writer) bool {
		resp, err := stream.Recv()
		if err == io.EOF {
			return false
		}
		if err != nil {
			c.SSEvent("error", gin.H{"error": err.Error()})
			return false
		}
		data, _ := json.Marshal(gin.H{
			"formula":    resp.Formula,
			"ic":         resp.Ic,
			"sharpe":     resp.Sharpe,
			"generation": resp.Generation,
		})
		c.SSEvent("gp-result", string(data))
		return true
	})
}
