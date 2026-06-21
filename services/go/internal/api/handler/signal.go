package handler

import (
	"context"
	"net/http"
	"strconv"
	"time"

	signalv1 "github.com/astockpursue/go-core/internal/gen/signal/v1"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
)

// SignalRecord represents a stored signal from PostgreSQL.
type SignalRecord struct {
	ID        int     `json:"id"`
	Type      string  `json:"type"`
	Symbol    string  `json:"symbol"`
	Direction string  `json:"direction"`
	Strength  float64 `json:"strength"`
	Source    string  `json:"source"`
	Status    string  `json:"status"`
	CreatedAt string  `json:"created_at"`
}

// SignalHandler proxies signal generation requests to Python SignalService via gRPC.
type SignalHandler struct {
	client signalv1.SignalServiceClient
	db     *pgxpool.Pool
}

// NewSignalHandler creates a new SignalHandler.
func NewSignalHandler(client signalv1.SignalServiceClient, db *pgxpool.Pool) *SignalHandler {
	return &SignalHandler{client: client, db: db}
}

// Generate calls Python SignalService.GenerateSignals and persists results to PostgreSQL.
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

	ctx, cancel := context.WithTimeout(c.Request.Context(), 30*time.Second)
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

	// Persist each generated signal to PostgreSQL
	if h.db != nil {
		for symbol, weight := range resp.Weights {
			direction := "long"
			if weight < 0 {
				direction = "short"
				weight = -weight
			}
			_, err := h.db.Exec(ctx,
				`INSERT INTO signals (type, symbol, direction, strength, source, status)
				 VALUES ($1, $2, $3, $4, $5, $6)`,
				req.StrategyName, symbol, direction, weight, "gRPC", "pending",
			)
			if err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to persist signal: " + err.Error()})
				return
			}
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"weights": resp.Weights,
		"count":   len(resp.Weights),
	})
}

// ListSignals returns all recorded signals from PostgreSQL.
// GET /api/v1/signal
func (h *SignalHandler) ListSignals(c *gin.Context) {
	if h.db == nil {
		c.JSON(http.StatusOK, gin.H{"signals": []SignalRecord{}})
		return
	}

	rows, err := h.db.Query(c.Request.Context(),
		`SELECT id, type, symbol, direction, strength, source, status, created_at
		 FROM signals ORDER BY created_at DESC LIMIT 100`)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer rows.Close()

	var signals []SignalRecord
	for rows.Next() {
		var s SignalRecord
		var createdAt time.Time
		if err := rows.Scan(&s.ID, &s.Type, &s.Symbol, &s.Direction, &s.Strength, &s.Source, &s.Status, &createdAt); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		s.CreatedAt = createdAt.Format(time.RFC3339)
		signals = append(signals, s)
	}

	c.JSON(http.StatusOK, gin.H{"signals": signals})
}

// AcknowledgeSignal marks a signal as acknowledged.
// PUT /api/v1/signal/:id/ack
func (h *SignalHandler) AcknowledgeSignal(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid signal id"})
		return
	}

	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "database not available"})
		return
	}

	tag, err := h.db.Exec(c.Request.Context(),
		`UPDATE signals SET status = $1 WHERE id = $2`, "acknowledged", id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if tag.RowsAffected() == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "signal not found: " + idStr})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "acknowledged", "id": id})
}

// DismissSignal marks a signal as dismissed.
// PUT /api/v1/signal/:id/dismiss
func (h *SignalHandler) DismissSignal(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid signal id"})
		return
	}

	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "database not available"})
		return
	}

	tag, err := h.db.Exec(c.Request.Context(),
		`UPDATE signals SET status = $1 WHERE id = $2`, "dismissed", id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if tag.RowsAffected() == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "signal not found: " + idStr})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "dismissed", "id": id})
}
