package engine

// GlobalFuturesEngine handles CME, ICE, and EUREX futures contracts.
// It embeds FuturesBase for common futures calculations (margin, PnL, slippage)
// and overrides CanExecute/CalcCommission to match the Engine interface.
type GlobalFuturesEngine struct {
	FuturesBase
	Symbol      string
	PerContract float64
}

type globalFuturesContract struct {
	Multiplier  float64
	MarginRate  float64
	PerContract float64
	PriceTick   float64
}

var globalFuturesContracts = map[string]globalFuturesContract{
	// CME
	"ES": {50, 0.05, 2.50, 0.25},
	"NQ": {20, 0.05, 2.50, 0.25},
	"CL": {1000, 0.08, 1.75, 0.01},
	"GC": {100, 0.05, 2.00, 0.10},
	// ICE
	"B":  {50000, 0.05, 1.50, 0.0001},
	"CC": {10, 0.05, 1.50, 1},
	// EUREX
	"FDAX": {25, 0.05, 1.80, 0.5},
	"FESX": {10, 0.05, 1.80, 0.5},
}

func NewGlobalFuturesEngine(symbol string) *GlobalFuturesEngine {
	c, ok := globalFuturesContracts[symbol]
	if !ok {
		return nil
	}
	return &GlobalFuturesEngine{
		FuturesBase: FuturesBase{
			ContractMultiplier: c.Multiplier,
			MarginRate:         c.MarginRate,
			PriceTick:          c.PriceTick,
			RoundLot:           1,
		},
		Symbol:      symbol,
		PerContract: c.PerContract,
	}
}

func (e *GlobalFuturesEngine) Name() string { return "global_futures" }

// CanExecute implements the Engine interface (single-param version).
// Checks that quantity is positive and respects round-lot constraints.
func (e *GlobalFuturesEngine) CanExecute(order *Order) bool {
	if order.Quantity <= 0 {
		return false
	}
	return true
}

// CalcCommission implements the Engine interface (single-param version).
// Global futures use per-contract flat fees instead of percentage rates.
func (e *GlobalFuturesEngine) CalcCommission(order *Order) float64 {
	return order.Quantity * e.PerContract
}
