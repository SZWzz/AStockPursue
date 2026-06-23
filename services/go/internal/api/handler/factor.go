package handler

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"time"

	factorv1 "github.com/astockpursue/go-core/internal/gen/factor/v1"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
)

// FactorHandler proxies factor computation and GP mining to Python FactorService via gRPC.
type FactorHandler struct {
	client factorv1.FactorServiceClient
	db     *pgxpool.Pool
}

// NewFactorHandler creates a new FactorHandler.
func NewFactorHandler(client factorv1.FactorServiceClient, db *pgxpool.Pool) *FactorHandler {
	return &FactorHandler{client: client, db: db}
}

func (h *FactorHandler) grpcUnavailable(c *gin.Context) {
	c.JSON(http.StatusServiceUnavailable, gin.H{
		"error":   "Python gRPC service is not running",
		"message": "Start the Python research layer: cd services/python && python -m src.grpc.server",
	})
}

// ListFactors returns available factors. Tries gRPC first, falls back to PostgreSQL,
// then falls back to hardcoded list.
// GET /api/v1/factor
func (h *FactorHandler) ListFactors(c *gin.Context) {
	// Try gRPC first — use ComputeFactor with a no-op formula as health check
	// TODO: add ListFactors to the factor proto when Python service supports it
	if h.client != nil {
		ctx, cancel := context.WithTimeout(c.Request.Context(), 3*time.Second)
		defer cancel()
		// Quick health check via ComputeFactor
		_, err := h.client.ComputeFactor(ctx, &factorv1.FactorRequest{
			Formula: "1", Symbols: []string{"000001"}, StartDate: "2026-01-01", EndDate: "2026-01-02",
		})
		if err == nil {
			// gRPC is alive; ideally we'd call ListFactors here
			// For now, fall through to DB to get factor names
		}
	}

	// Try PostgreSQL
	if h.db != nil {
		rows, err := h.db.Query(c.Request.Context(),
			`SELECT DISTINCT factor_name FROM factor_results ORDER BY factor_name`)
		if err == nil {
			defer rows.Close()
			factors := make([]map[string]any, 0)
			for rows.Next() {
				var name string
				if err := rows.Scan(&name); err == nil {
					factors = append(factors, map[string]any{
						"name": name, "status": "production",
					})
				}
			}
			if len(factors) > 0 {
				c.JSON(http.StatusOK, gin.H{"factors": factors, "source": "db"})
				return
			}
		}
	}

	// Fallback to hardcoded list
	factors := []map[string]any{
		{"name": "momentum_20", "formula": "close / close_20 - 1", "ic": 0.035, "sharpe": 1.2, "status": "production"},
		{"name": "volatility_20", "formula": "std(returns, 20)", "ic": 0.028, "sharpe": 0.9, "status": "production"},
	}
	c.JSON(http.StatusOK, gin.H{"factors": factors, "source": "fallback"})
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
