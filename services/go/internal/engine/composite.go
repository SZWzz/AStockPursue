package engine

import "strings"

// EngineFactory manages engine registration and symbol-to-engine routing.
// It is the single source of truth for determining which Engine handles a given symbol.
type EngineFactory struct {
	engines map[string]Engine
}

// NewEngineFactory creates a factory pre-registered with all 7 engine types.
func NewEngineFactory() *EngineFactory {
	return &EngineFactory{
		engines: map[string]Engine{
			"china_a": NewChinaAEngine(),
			"crypto": &CryptoEngine{
				MakerFee:          0.0002,
				TakerFee:          0.0006,
				Slippage:          0.001,
				Leverage:          10,
				MaintenanceMargin: 0.005,
				Precision:         map[string]float64{},
			},
			"global_equity": &GlobalEquityEngine{
				Market:        "US",
				PerShareComm:  0.005,
				MinCommission: 1.0,
				Slippage:      0.001,
				CanShort:      true,
			},
			"forex": &ForexEngine{
				SpreadMajor: 0.0002,
				SpreadMinor: 0.0005,
				Slippage:    0.0001,
				Leverage:    30,
				LotSize:     100000,
			},
			"options": &OptionsEngine{
				CommPerContract: 0.65,
				ExerciseFee:     5.00,
				AssignmentFee:   5.00,
				Slippage:        0.01,
				MarginRateShort: 0.20,
			},
		},
	}
}

func (f *EngineFactory) Register(name string, engine Engine) {
	f.engines[name] = engine
}

func (f *EngineFactory) Get(name string) (Engine, bool) {
	e, ok := f.engines[name]
	return e, ok
}

// ForSymbol routes a symbol to the correct Engine based on exchange/market conventions.
//
// Routing priority (first match wins):
//  1. A-share numeric codes (6xxxxx SH, 0xxxxx/3xxxxx SZ, 4xxxxx/8xxxxx/9xxxxx BJ)
//  2. China futures (exact contract codes: IF, IC, IH, RB, CU, AU, etc.)
//  3. Global futures (exact contract codes: ES, NQ, CL, GC, etc.)
//  4. Options (.OPT suffix)
//  5. Crypto (prefix: BTC, ETH, BNB, SOL, XRP, etc.)
//  6. Forex (prefix: EUR, GBP, JPY, AUD, etc.)
//  7. Default: global_equity
func (f *EngineFactory) ForSymbol(symbol string) Engine {
	// Guard: empty symbol falls back to china_a
	if len(symbol) == 0 {
		return f.engines["china_a"]
	}

	// 1. A-share: numeric exchange codes
	first := symbol[0]
	if first == '6' || first == '0' || first == '3' ||
		first == '4' || first == '8' || first == '9' {
		return f.engines["china_a"]
	}

	// 2. China futures: exact contract code match (before forex prefix to avoid
	//    conflicts like "AU" gold futures vs "AUD" forex)
	if NewChinaFuturesEngine(symbol) != nil {
		return NewChinaFuturesEngine(symbol)
	}

	// 3. Global futures: exact contract code match
	if NewGlobalFuturesEngine(symbol) != nil {
		return NewGlobalFuturesEngine(symbol)
	}

	// 4. Options: .OPT suffix
	if len(symbol) > 4 && strings.HasSuffix(symbol, ".OPT") {
		return f.engines["options"]
	}

	// 5. Crypto: known crypto base currencies
	cryptoBases := []string{"BTC", "ETH", "BNB", "SOL", "XRP", "ADA",
		"DOGE", "DOT", "MATIC", "AVAX", "LINK", "TRX", "LTC", "ATOM",
		"UNI", "FIL", "APT", "ARB", "OP", "SUI", "PEPE", "SHIB", "WIF",
		"BONK", "TIA", "SEI", "STRK", "ENA", "EIGEN", "JUP", "W",
		"ONDO", "MKR", "AAVE", "FET", "RENDER", "TAO", "INJ", "STX"}
	for _, base := range cryptoBases {
		if len(symbol) >= len(base) && symbol[:len(base)] == base {
			if e, ok := f.engines["crypto"]; ok {
				return e
			}
			return f.engines["china_a"]
		}
	}

	// 6. Forex: currency pair prefixes
	forexCurrencies := []string{"EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"}
	for _, cc := range forexCurrencies {
		if len(symbol) >= len(cc) && symbol[:len(cc)] == cc {
			if e, ok := f.engines["forex"]; ok {
				return e
			}
			return f.engines["china_a"]
		}
	}

	// 7. Default: global equity (US/HK/other exchanges)
	if e, ok := f.engines["global_equity"]; ok {
		return e
	}
	return f.engines["china_a"]
}

type CompositeEngine struct {
	factory *EngineFactory
}

func NewCompositeEngine(factory *EngineFactory) *CompositeEngine {
	return &CompositeEngine{factory: factory}
}

func (c *CompositeEngine) resolve(order *Order) Engine {
	if order != nil {
		return c.factory.ForSymbol(order.Symbol)
	}
	return c.factory.ForSymbol("000001")
}

func (c *CompositeEngine) resolvePosition(position *Position) Engine {
	if position != nil {
		return c.factory.ForSymbol(position.Symbol)
	}
	return c.factory.ForSymbol("000001")
}

func (c *CompositeEngine) resolveBar(bar interface{}) Engine {
	if b, ok := bar.(*Bar); ok {
		return c.factory.ForSymbol(b.Symbol)
	}
	return c.factory.ForSymbol("000001")
}

func (c *CompositeEngine) Name() string       { return "composite" }
func (c *CompositeEngine) CanExecute(order *Order) bool {
	return c.resolve(order).CanExecute(order)
}
func (c *CompositeEngine) RoundSize(size float64) float64 {
	return c.resolve(nil).RoundSize(size)
}
func (c *CompositeEngine) CalcCommission(order *Order) float64 {
	return c.resolve(order).CalcCommission(order)
}
func (c *CompositeEngine) ApplySlippage(order *Order, bar interface{}) float64 {
	return c.resolve(order).ApplySlippage(order, bar)
}
func (c *CompositeEngine) CalcMargin(position *Position) float64 {
	return c.resolvePosition(position).CalcMargin(position)
}
func (c *CompositeEngine) CalcPnL(position *Position) float64 {
	return c.resolvePosition(position).CalcPnL(position)
}
