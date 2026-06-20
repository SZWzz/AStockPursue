package handler

import (
	"net/http"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/gin-gonic/gin"
)

type TradingHandler struct {
	runner *engine.LiveTradingRunner
}

func NewTradingHandler(runner *engine.LiveTradingRunner) *TradingHandler {
	return &TradingHandler{runner: runner}
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
