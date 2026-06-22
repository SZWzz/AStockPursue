package handler

import (
	"net/http"
	"time"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/log"
	"github.com/astockpursue/go-core/internal/market"
	"github.com/astockpursue/go-core/internal/papertrade"
	"github.com/gin-gonic/gin"
)

type TradingHandler struct {
	runner      *engine.LiveTradingRunner
	paperEngine *papertrade.Engine
	factory     *engine.EngineFactory
	ds          *market.DataStore
	logger      *log.Logger
}

func NewTradingHandler(runner *engine.LiveTradingRunner) *TradingHandler {
	return &TradingHandler{runner: runner, logger: log.New()}
}

// SetPromotionContext provides the context for paper→live promotion.
func (h *TradingHandler) SetPromotionContext(paperEngine *papertrade.Engine, factory *engine.EngineFactory, ds *market.DataStore) {
	h.paperEngine = paperEngine
	h.factory = factory
	h.ds = ds
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

// PromoteToLive deploys a paper trading run to the live runner.
// POST /api/v1/paper-trading/:id/promote-to-live
func (h *TradingHandler) PromoteToLive(c *gin.Context) {
	id := c.Param("id")
	if h.paperEngine == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "promotion context not configured"})
		return
	}

	paperRun := h.paperEngine.Get(id)
	if paperRun == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "paper trading run not found: " + id})
		return
	}

	// Stop current runner if running
	_ = h.runner.Stop()

	// Create a new pipeline from paper run config
	pipeline := &engine.Pipeline{
		Engine:    h.factory.ForSymbol(paperRun.Symbols[0]),
		Portfolio: &engine.Portfolio{Cash: paperRun.InitialCash, Equity: paperRun.InitialCash, Positions: make(map[string]*engine.Position)},
		Signal:    engine.NewSignalAdapter("localhost:8902", 10*time.Second),
		Risk:      engine.NewRiskManager(engine.RiskConfig{}),
		LastBars:  make(map[string]*engine.Bar),
	}

	newRunner := engine.NewLiveTradingRunner(pipeline, 1*time.Minute)
	newRunner.WithFetcher(&paperFetcher{ds: h.ds}, paperRun.Symbols, paperRun.Frequency)
	h.runner = newRunner

	if err := h.runner.Start(); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status":   h.runner.Status(),
		"symbols":  paperRun.Symbols,
		"source":   "paper",
		"source_id": id,
	})
}

// paperFetcher adapts market.DataStore to engine.BarFetcher.
type paperFetcher struct {
	ds *market.DataStore
}

func (f *paperFetcher) GetBars(symbol string, start, end time.Time, freq string) ([]engine.BarData, error) {
	bars, err := f.ds.GetBars(symbol, start, end, freq)
	if err != nil {
		return nil, err
	}
	result := make([]engine.BarData, len(bars))
	for i, b := range bars {
		result[i] = engine.BarData{
			Symbol:    b.Symbol,
			Open:      b.Open,
			High:      b.High,
			Low:       b.Low,
			Close:     b.Close,
			Volume:    b.Volume,
			Timestamp: time.UnixMilli(b.Timestamp),
		}
	}
	return result, nil
}
