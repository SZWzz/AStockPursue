package engine

import (
	"log"
	"math"
	"time"
)

const (
	ChinaACommissionRate  = 0.0003
	ChinaAStampDutyRate   = 0.001
	ChinaAMinCommission   = 5.0
	ChinaARoundLot        = 100.0
	ChinaAPriceLimitPct   = 0.10
)

type ChinaAEngine struct {
	PurchaseDate map[string]time.Time
}

func NewChinaAEngine() *ChinaAEngine {
	return &ChinaAEngine{PurchaseDate: make(map[string]time.Time)}
}

func (e *ChinaAEngine) Name() string { return "china_a" }

func (e *ChinaAEngine) CanExecute(order *Order) bool {
	if order.Side == Sell {
		if purchaseDate, ok := e.PurchaseDate[order.Symbol]; ok {
			if !purchaseDate.Before(order.CreatedAt) {
				log.Printf("T+1 restriction: cannot sell %s on same day as purchase", order.Symbol)
				return false
			}
		}
	}
	return true
}

func (e *ChinaAEngine) RoundSize(size float64) float64 {
	return math.Floor(size/ChinaARoundLot) * ChinaARoundLot
}

func (e *ChinaAEngine) CalcCommission(order *Order) float64 {
	if order.Quantity <= 0 {
		return 0
	}
	turnover := order.Quantity * order.Price
	comm := turnover * ChinaACommissionRate
	if comm < ChinaAMinCommission {
		comm = ChinaAMinCommission
	}
	if order.Side == Sell {
		stamp := turnover * ChinaAStampDutyRate
		comm += stamp
	}
	return comm
}

func (e *ChinaAEngine) CalculateSlippage(symbol string, qty float64, isBuy bool) float64 {
	// Dynamic slippage based on daily amplitude
	base := 0.001 // 0.1% base
	amp := e.getDailyAmplitude(symbol)
	if amp > 0 {
		base += amp * 0.01 // scale with amplitude
	}
	return base
}

func (e *ChinaAEngine) getDailyAmplitude(symbol string) float64 {
	// Get latest bar amplitude from data store
	// Fallback to 0 if unavailable
	return 0
}

func (e *ChinaAEngine) ApplySlippage(order *Order, bar *Bar) float64 {
	price := bar.Close
	slip := e.CalculateSlippage(order.Symbol, order.Quantity, order.Side == Buy)
	if order.Side == Buy {
		price *= (1 + slip)
	} else {
		price *= (1 - slip)
	}
	upperLimit := bar.Close * (1 + ChinaAPriceLimitPct)
	lowerLimit := bar.Close * (1 - ChinaAPriceLimitPct)
	if price > upperLimit {
		price = upperLimit
	} else if price < lowerLimit {
		price = lowerLimit
	}
	return math.Round(price*100) / 100
}

func (e *ChinaAEngine) CalcMargin(position *Position) float64 {
	return 0
}

func (e *ChinaAEngine) CalcPnL(position *Position) float64 {
	return position.Size * (position.CurrentPrice - position.EntryPrice)
}
