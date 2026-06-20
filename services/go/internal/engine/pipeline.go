package engine

import (
	"log"
	"sort"
	"time"
)

type SignalAdapter interface {
	Generate(bars []interface{}, ts time.Time) (map[string]float64, error)
}

type RiskPipeline interface {
	CheckExits(portfolio *Portfolio, bar interface{}) []*Order
}

type Pipeline struct {
	Engine      Engine
	Portfolio   *Portfolio
	Signal      SignalAdapter
	Risk        RiskPipeline
	LastBars    map[string]interface{}
	EquityCache float64
}

func (p *Pipeline) OnBar(bar interface{}, ts time.Time) {
	b, ok := bar.(*Bar)
	if !ok {
		log.Printf("pipeline: expected *Bar, got %T", bar)
		return
	}

	p.EquityCache = p.Portfolio.Equity

	p.checkGaps(b)

	p.checkSuspension(b)

	var weights map[string]float64
	var err error
	if p.Signal != nil {
		weights, err = p.Signal.Generate(p.barWindow(), ts)
		if err != nil {
			log.Printf("signal error: %v", err)
		}
	}

	p.LastBars[b.Symbol] = b

	riskOrders := p.Risk.CheckExits(p.Portfolio, b)

	p.processOrders(weights, riskOrders, b, ts)

	p.recordEquity(b)
}

func (p *Pipeline) checkGaps(b *Bar) {
	if prev, ok := p.LastBars[b.Symbol]; ok {
		pb := prev.(*Bar)
		gap := (b.Open - pb.Close) / pb.Close * 100
		if gap > 5 || gap < -5 {
			log.Printf("gap detected: %s %.2f%%", b.Symbol, gap)
		}
	}
}

func (p *Pipeline) checkSuspension(b *Bar) {
	if b.Open == b.Close && b.Volume == 0 {
		log.Printf("suspension detected: %s", b.Symbol)
	}
}

func (p *Pipeline) barWindow() []interface{} {
	var bars []interface{}
	var keys []string
	for sym := range p.LastBars {
		keys = append(keys, sym)
	}
	sort.Strings(keys)
	for _, sym := range keys {
		bars = append(bars, p.LastBars[sym])
	}
	return bars
}

func (p *Pipeline) processOrders(weights map[string]float64, riskOrders []*Order, bar interface{}, ts time.Time) {
	for _, order := range riskOrders {
		p.executeOrder(order, bar)
	}
	for symbol, targetWeight := range weights {
		p.generateSignalOrder(symbol, targetWeight, bar, ts)
	}
}

func (p *Pipeline) generateSignalOrder(symbol string, targetWeight float64, bar interface{}, ts time.Time) {
	b := bar.(*Bar)
	targetValue := p.EquityCache * targetWeight
	currentValue := 0.0
	if pos, ok := p.Portfolio.Positions[symbol]; ok {
		currentValue = pos.Size * b.Close
	}
	diff := targetValue - currentValue
	if diff == 0 {
		return
	}
	side := Buy
	if diff < 0 {
		side = Sell
		diff = -diff
	}
	qty := p.Engine.RoundSize(diff / b.Close)
	if qty < 1 {
		return
	}
	if side == Sell {
		if pos, ok := p.Portfolio.Positions[symbol]; ok && qty > pos.Size {
			qty = pos.Size
		}
	}
	if qty < 1 {
		return
	}
	price := b.Close
	commission := p.Engine.CalcCommission(&Order{Quantity: qty, Price: price, Side: side})
	total := qty*price + commission
	if side == Buy && total > p.Portfolio.Cash {
		maxQty := p.Engine.RoundSize(p.Portfolio.Cash / price)
		if maxQty < 1 {
			return
		}
		qty = maxQty
	}
	p.executeOrder(&Order{
		Symbol: symbol, Side: side, Type: Market, Price: price,
		Quantity: qty, Status: OrderFilled, CreatedAt: ts,
	}, bar)
}

func (p *Pipeline) executeOrder(order *Order, bar interface{}) {
	if err := order.Validate(); err != nil {
		log.Printf("order rejected: %v", err)
		return
	}
	if p.Engine != nil && !p.Engine.CanExecute(order) {
		return
	}
	if p.Engine != nil {
		order.Price = p.Engine.ApplySlippage(order, bar)
	}
	cost := order.Quantity * order.Price
	commission := p.Engine.CalcCommission(order)
	if order.Side == Buy {
		pos := p.Portfolio.Positions[order.Symbol]
		if pos == nil {
			pos = &Position{Symbol: order.Symbol}
			p.Portfolio.Positions[order.Symbol] = pos
		}
		totalCost := pos.Size*pos.EntryPrice + cost
		pos.Size += order.Quantity
		pos.EntryPrice = totalCost / pos.Size
		p.Portfolio.Cash -= (cost + commission)
	} else {
		pos := p.Portfolio.Positions[order.Symbol]
		if pos == nil || pos.Size < order.Quantity {
			return
		}
		pos.Size -= order.Quantity
		p.Portfolio.Cash += (cost - commission)
		if pos.Size <= 0 {
			delete(p.Portfolio.Positions, order.Symbol)
		}
	}
	order.Status = OrderFilled
}

func (p *Pipeline) recordEquity(bar interface{}) {
	b := bar.(*Bar)
	if pos, ok := p.Portfolio.Positions[b.Symbol]; ok {
		pos.CurrentPrice = b.Close
	}
	totalPositionValue := 0.0
	for _, pos := range p.Portfolio.Positions {
		totalPositionValue += pos.Size * pos.CurrentPrice
	}
	p.Portfolio.Equity = p.Portfolio.Cash + totalPositionValue
}
