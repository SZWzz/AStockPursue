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
	Symbols       []string      `json:"symbols"`
	Frequency     string        `json:"frequency"`
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
		Cash:          br.pipeline.Portfolio.Cash,
		Equity:        br.pipeline.Portfolio.Equity,
		InitialEquity: br.pipeline.Portfolio.InitialEquity,
		Positions:     make(map[string]*Position),
	}
	br.pipeline.LastBars = make(map[string]*Bar)
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

	for _, ts := range merged {
		tsTime := time.UnixMilli(ts)
		for _, sym := range sortedKeys(symbolBars) {
			bars := symbolBars[sym]
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

				posBefore := copyPositions(br.pipeline.Portfolio.Positions)

				br.pipeline.OnBar(eb, tsTime)

				br.recordTrades(bar, posBefore)
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

	result := br.calculateMetrics(initialCash, equityCurve, freq)
	result.StartTime = start
	result.EndTime = end
	result.Symbols = symbols
	result.Frequency = freq
	result.Trades = br.trades
	return result, nil
}

func sortedKeys(m map[string][]*commonv1.Bar) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
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

func (br *BacktestRunner) recordTrades(bar *commonv1.Bar, posBefore map[string]*Position) {
	portfolio := br.pipeline.Portfolio
	for symbol, pos := range portfolio.Positions {
		oldPos, existed := posBefore[symbol]
		if !existed {
			qty := pos.Size
			comm := br.pipeline.Engine.CalcCommission(&Order{
				Quantity: qty, Price: bar.Close, Side: Buy,
			})
			br.trades = append(br.trades, TradeRecord{
				Symbol: symbol, Side: Buy,
				Quantity: qty, Price: bar.Close,
				Commission: comm,
				Timestamp:  time.UnixMilli(bar.Timestamp),
			})
			continue
		}
		if oldPos.Size < pos.Size {
			qty := pos.Size - oldPos.Size
			comm := br.pipeline.Engine.CalcCommission(&Order{
				Quantity: qty, Price: bar.Close, Side: Buy,
			})
			br.trades = append(br.trades, TradeRecord{
				Symbol: symbol, Side: Buy,
				Quantity: qty, Price: bar.Close,
				Commission: comm,
				Timestamp:  time.UnixMilli(bar.Timestamp),
			})
		}
	}
	for symbol, oldPos := range posBefore {
		if _, stillHolding := portfolio.Positions[symbol]; !stillHolding {
			pnl := oldPos.Size * (bar.Close - oldPos.EntryPrice)
			comm := br.pipeline.Engine.CalcCommission(&Order{
				Quantity: oldPos.Size, Price: bar.Close, Side: Sell,
			})
			br.trades = append(br.trades, TradeRecord{
				Symbol: symbol, Side: Sell,
				Quantity: oldPos.Size, Price: bar.Close,
				Commission: comm,
				PnL: pnl, Timestamp: time.UnixMilli(bar.Timestamp),
			})
		}
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

func (br *BacktestRunner) calculateMetrics(initialCash float64, curve []EquityPoint, freq string) *BacktestResult {
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
			r.SharpeRatio = mean / std * math.Sqrt(periodsPerYear(freq))
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
	if len(values) == 1 {
		return values[0], 0
	}
	for _, v := range values {
		mean += v
	}
	mean /= float64(len(values))
	for _, v := range values {
		diff := v - mean
		std += diff * diff
	}
	std = math.Sqrt(std / float64(len(values)-1))
	return mean, std
}

// periodsPerYear returns the approximate number of trading periods per year
// for a given bar frequency, used to annualize Sharpe ratio.
func periodsPerYear(freq string) float64 {
	switch freq {
	case "1m":
		return 252 * 240
	case "5m":
		return 252 * 48
	case "15m":
		return 252 * 16
	case "30m":
		return 252 * 8
	case "1h":
		return 252 * 6.5
	case "4h":
		return 252 * 1.625
	case "1d":
		return 252
	case "1w":
		return 52
	default:
		return 252
	}
}
