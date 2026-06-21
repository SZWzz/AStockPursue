package handler

import (
	"net/http"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/log"
	"github.com/gin-gonic/gin"
)

type TradingHandler struct {
	runner *engine.LiveTradingRunner
	logger *log.Logger
}

func NewTradingHandler(runner *engine.LiveTradingRunner) *TradingHandler {
	return &TradingHandler{runner: runner, logger: log.New()}
}

func (h *TradingHandler) Start(c *gin.Context) {
	if err := h.runner.Start(); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": h.runner.Status()})
}

func (h *TradingHandler) Stop(c *gin.Context) {
	if err := h.runner.Stop(); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": h.runner.Status()})
}

func (h *TradingHandler) ListOrders(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"orders": h.runner.Orders()})
}

// PlaceOrder accepts a JSON order and executes it through the broker.
// POST /api/v1/trading/orders
func (h *TradingHandler) PlaceOrder(c *gin.Context) {
	var req struct {
		Symbol   string  `json:"symbol" binding:"required"`
		Side     string  `json:"side" binding:"required"`
		Type     string  `json:"type" binding:"required"`
		Price    float64 `json:"price"`
		Quantity float64 `json:"quantity" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	order := &engine.Order{
		Symbol:   req.Symbol,
		Side:     engine.OrderSide(req.Side),
		Type:     engine.OrderType(req.Type),
		Price:    req.Price,
		Quantity: req.Quantity,
	}

	result, err := h.runner.ExecuteOrder(c.Request.Context(), order)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{"order": result})
}

// CancelOrder cancels an order by its ID.
// DELETE /api/v1/trading/orders/:id
func (h *TradingHandler) CancelOrder(c *gin.Context) {
	orderID := c.Param("id")
	if err := h.runner.CancelOrder(orderID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "cancelled", "order_id": orderID})
}

func (h *TradingHandler) Status(c *gin.Context) {
	p := h.runner.Portfolio()
	copy := &engine.Portfolio{
		Cash:   p.Cash,
		Equity: p.Equity,
		Positions: make(map[string]*engine.Position),
	}
	for k, v := range p.Positions {
		pos := *v
		copy.Positions[k] = &pos
	}
	c.JSON(http.StatusOK, gin.H{
		"status":    h.runner.Status(),
		"portfolio": copy,
	})
}
