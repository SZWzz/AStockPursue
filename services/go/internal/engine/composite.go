package engine

import "strings"

type EngineFactory struct {
	engines map[string]Engine
}

func NewEngineFactory() *EngineFactory {
	return &EngineFactory{
		engines: map[string]Engine{
			"china_a": &ChinaAEngine{},
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

func (f *EngineFactory) ForSymbol(symbol string) Engine {
	if strings.HasPrefix(symbol, "6") ||
		strings.HasPrefix(symbol, "0") ||
		strings.HasPrefix(symbol, "3") {
		return f.engines["china_a"]
	}
	if strings.HasPrefix(symbol, "BTC") || strings.HasPrefix(symbol, "ETH") {
		if e, ok := f.engines["crypto"]; ok {
			return e
		}
	}
	if e, ok := f.engines["global"]; ok {
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
