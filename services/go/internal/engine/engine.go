package engine

type Engine interface {
	Name() string
	CanExecute(order *Order) bool
	RoundSize(size float64) float64
	CalcCommission(order *Order) float64
	ApplySlippage(order *Order, bar interface{}) float64
	CalcMargin(position *Position) float64
	CalcPnL(position *Position) float64
}
