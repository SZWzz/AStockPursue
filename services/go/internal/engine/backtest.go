package engine

import (
	"fmt"
	"math"
	"sort"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
)

type BarLoader interface {
	GetBars(symbol string, start, end time.Time, freq string) ([]*commonv1.Bar, error)
}

type EquityPoint struct {
	Timestamp     time.Time `json:"timestamp"`
	Equity        float64   `json:"equity"`
	Cash          float64   `json:"cash"`
	PositionCount int       `json:"position_count"`
}

type TradeRecord struct {
	Symbol     string    `json:"symbol"`
	Side       OrderSide `json:"side"`
	Quantity   float64   `json:"quantity"`
	Price      float64   `json:"price"`
	Commission float64   `json:"commission"`
	PnL        float64   `json:"pnl,omitempty"`
	Timestamp  time.Time `json:"timestamp"`
}

type BacktestResult struct {
	StartTime     time.Time     `json:"start_time"`
	EndTime       time.Time     `json:"end_time"`
	InitialCash   float64       `json:"initial_cash"`
	FinalEquity   float64       `json:"final_equity"`
	TotalReturn   float64       `json:"total_return"`
	SharpeRatio   float64       `json:"sharpe_ratio"`
	MaxDrawdown   float64       `json:"max_drawdown"`
	MaxDrawdownPct float64      `json:"max_drawdown_pct"`
	WinRate       float64       `json:"win_rate"`
	TotalTrades   int           `json:"total_trades"`
	WinningTrades int           `json:"winning_trades"`
	LosingTrades  int           `json:"losing_trades"`
	EquityCurve   []EquityPoint `json:"equity_curve"`
	Trades        []TradeRecord `json:"trades"`
}

type BacktestRunner struct {
	pipeline *Pipeline
	loader   BarLoader
	trades   []TradeRecord
}

func NewBacktestRunner(pipeline *Pipeline, loader BarLoader) *BacktestRunner {
	return &BacktestRunner{
		pipeline: pipeline,
		loader:   loader,
		trades:   make([]TradeRecord, 0),
	}
}

func (br *BacktestRunner) Run(symbols []string, start, end time.Time, freq string) (*BacktestResult, error) {
	br.pipeline.Portfolio = &Portfolio{
		Cash:      br.pipeline.Portfolio.Cash,
		Equity:    br.pipeline.Portfolio.Equity,
		Positions: make(map[string]*Position),
	}
	br.pipeline.LastBars = make(map[string]interface{})
	br.trades = nil

	symbolBars := make(map[string][]*commonv1.Bar)
	for _, symbol := range symbols {
		bars, err := br.loader.GetBars(symbol, start, end, freq)
		if err != nil {
			return nil, fmt.Errorf("load bars for %s: %w", symbol, err)
		}
		if len(bars) == 0 {
			return nil, fmt.Errorf("no bars for %s in range", symbol)
		}
		symbolBars[symbol] = bars
	}

	merged := br.mergeBars(symbolBars)
	if len(merged) == 0 {
		return nil, fmt.Errorf("no bars to process")
	}

	initialCash := br.pipeline.Portfolio.Cash
	var equityCurve []EquityPoint
	openTrades := make(map[string]*TradeRecord)

	for _, ts := range merged {
		tsTime := time.UnixMilli(ts)
		for _, bars := range symbolBars {
			for _, bar := range bars {
				if bar.Timestamp != ts {
					continue
				}
				eb := &Bar{
					Symbol: bar.Symbol,
					Open:   bar.Open,
					High:   bar.High,
					Low:    bar.Low,
					Close:  bar.Close,
					Volume: bar.Volume,
				}

				cashBefore := br.pipeline.Portfolio.Cash
				posBefore := copyPositions(br.pipeline.Portfolio.Positions)

				br.pipeline.OnBar(eb, tsTime)

				br.recordTrades(bar, cashBefore, posBefore, openTrades)
				break
			}
		}

		eq := EquityPoint{
			Timestamp:     tsTime,
			Equity:        br.pipeline.Portfolio.Equity,
			Cash:          br.pipeline.Portfolio.Cash,
			PositionCount: len(br.pipeline.Portfolio.Positions),
		}
		equityCurve = append(equityCurve, eq)
	}

	result := br.calculateMetrics(initialCash, equityCurve)
	result.StartTime = start
	result.EndTime = end
	result.Trades = br.trades
	return result, nil
}

func (br *BacktestRunner) mergeBars(symbolBars map[string][]*commonv1.Bar) []int64 {
	tsSet := make(map[int64]struct{})
	for _, bars := range symbolBars {
		for _, b := range bars {
			tsSet[b.Timestamp] = struct{}{}
		}
	}
	ts := make([]int64, 0, len(tsSet))
	for t := range tsSet {
		ts = append(ts, t)
	}
	sort.Slice(ts, func(i, j int) bool { return ts[i] < ts[j] })
	return ts
}

func (br *BacktestRunner) recordTrades(bar *commonv1.Bar, cashBefore float64, posBefore map[string]*Position, openTrades map[string]*TradeRecord) {
	portfolio := br.pipeline.Portfolio
	for symbol, pos := range portfolio.Positions {
		oldPos, existed := posBefore[symbol]
		if !existed {
			br.trades = append(br.trades, TradeRecord{
				Symbol: symbol, Side: Buy,
				Quantity: pos.Size, Price: bar.Close,
				Timestamp: time.UnixMilli(bar.Timestamp),
			})
			continue
		}
		if oldPos.Size < pos.Size {
			br.trades = append(br.trades, TradeRecord{
				Symbol: symbol, Side: Buy,
				Quantity: pos.Size - oldPos.Size,
				Price:    bar.Close,
				Timestamp: time.UnixMilli(bar.Timestamp),
			})
		}
	}
	for symbol, oldPos := range posBefore {
		if _, stillHolding := portfolio.Positions[symbol]; !stillHolding {
			pnl := oldPos.Size * (bar.Close - oldPos.EntryPrice)
			br.trades = append(br.trades, TradeRecord{
				Symbol: symbol, Side: Sell,
				Quantity: oldPos.Size, Price: bar.Close,
				PnL: pnl, Timestamp: time.UnixMilli(bar.Timestamp),
			})
		}
	}
	if cashBefore != portfolio.Cash {
	}
}

func copyPositions(src map[string]*Position) map[string]*Position {
	dst := make(map[string]*Position, len(src))
	for k, v := range src {
		copied := *v
		dst[k] = &copied
	}
	return dst
}

func (br *BacktestRunner) calculateMetrics(initialCash float64, curve []EquityPoint) *BacktestResult {
	r := &BacktestResult{
		InitialCash: initialCash,
		EquityCurve: curve,
	}
	if len(curve) == 0 {
		return r
	}

	r.FinalEquity = curve[len(curve)-1].Equity
	r.TotalReturn = (r.FinalEquity - initialCash) / initialCash

	returns := make([]float64, len(curve)-1)
	for i := 1; i < len(curve); i++ {
		returns[i-1] = (curve[i].Equity - curve[i-1].Equity) / curve[i-1].Equity
	}

	if len(returns) > 0 {
		mean, std := meanStd(returns)
		if std > 0 {
			r.SharpeRatio = mean / std * math.Sqrt(252)
		}
	}

	peak := curve[0].Equity
	for _, pt := range curve {
		if pt.Equity > peak {
			peak = pt.Equity
		}
		dd := peak - pt.Equity
		if dd > r.MaxDrawdown {
			r.MaxDrawdown = dd
		}
		ddPct := dd / peak
		if ddPct > r.MaxDrawdownPct {
			r.MaxDrawdownPct = ddPct
		}
	}

	var winning, losing int
	for _, t := range br.trades {
		if t.PnL > 0 {
			winning++
		} else if t.PnL < 0 {
			losing++
		}
	}
	r.TotalTrades = len(br.trades)
	r.WinningTrades = winning
	r.LosingTrades = losing
	if r.TotalTrades > 0 {
		r.WinRate = float64(winning) / float64(r.TotalTrades)
	}

	return r
}

func meanStd(values []float64) (mean, std float64) {
	if len(values) == 0 {
		return 0, 0
	}
	for _, v := range values {
		mean += v
	}
	mean /= float64(len(values))
	for _, v := range values {
		diff := v - mean
		std += diff * diff
	}
	std = math.Sqrt(std / float64(len(values)))
	return mean, std
}
