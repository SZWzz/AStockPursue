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

func (e *ChinaAEngine) ApplySlippage(order *Order, bar interface{}) float64 {
	b := bar.(*Bar)
	price := b.Close
	if order.Side == Buy {
		price *= 1.001
	} else {
		price *= 0.999
	}
	upperLimit := b.Close * (1 + ChinaAPriceLimitPct)
	lowerLimit := b.Close * (1 - ChinaAPriceLimitPct)
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
