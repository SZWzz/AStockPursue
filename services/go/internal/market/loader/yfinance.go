package loader

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
)

func init() {
	// Priority 8: after A-share sources, before ultra-low-priority fallbacks
	RegisterPriority(NewYFinanceLoader(), 8)
}

// YFinanceLoader fetches historical bars from Yahoo Finance via the v8 chart API.
// Supports US equities, HK equities (with .HK suffix), ETFs, and indices.
// No API key required. Rate-limited at ~2000 requests/hour.
type YFinanceLoader struct {
	client  *http.Client
	baseURL string
}

// yfResponse mirrors the Yahoo Finance v8 chart API JSON structure.
type yfResponse struct {
	Chart struct {
		Error  *yfError `json:"error"`
		Result []yfResult `json:"result"`
	} `json:"chart"`
}

type yfError struct {
	Code        string `json:"code"`
	Description string `json:"description"`
}

type yfResult struct {
	Timestamp  []int64 `json:"timestamp"`
	Indicators struct {
		Quote []yfQuote `json:"quote"`
	} `json:"indicators"`
}

type yfQuote struct {
	Open   []float64 `json:"open"`
	High   []float64 `json:"high"`
	Low    []float64 `json:"low"`
	Close  []float64 `json:"close"`
	Volume []int64   `json:"volume"`
}

func NewYFinanceLoader() *YFinanceLoader {
	return &YFinanceLoader{
		client:  &http.Client{Timeout: 30 * time.Second},
		baseURL: "https://query1.finance.yahoo.com",
	}
}

func (y *YFinanceLoader) Name() string { return "yfinance" }

func (y *YFinanceLoader) IsAvailable() bool {
	req, err := http.NewRequest("GET", y.baseURL+"/v8/finance/chart/AAPL?range=1d&interval=1d", nil)
	if err != nil {
		return false
	}
	req.Header.Set("User-Agent", "Mozilla/5.0")
	resp, err := y.client.Do(req)
	if err != nil {
		return false
	}
	resp.Body.Close()
	return true
}

func (y *YFinanceLoader) FetchBars(symbol string, start, end time.Time) ([]*commonv1.Bar, error) {
	period1 := start.Unix()
	period2 := end.Unix()
	if period2 == 0 {
		period2 = time.Now().Unix()
	}

	url := fmt.Sprintf("%s/v8/finance/chart/%s?period1=%d&period2=%d&interval=1d",
		y.baseURL, symbol, period1, period2)

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("yfinance create request: %w", err)
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

	resp, err := y.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("yfinance fetch: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("yfinance read body: %w", err)
	}

	var result yfResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("yfinance parse: %w", err)
	}

	if result.Chart.Error != nil {
		return nil, fmt.Errorf("yfinance API error: %s - %s",
			result.Chart.Error.Code, result.Chart.Error.Description)
	}

	if len(result.Chart.Result) == 0 || len(result.Chart.Result[0].Indicators.Quote) == 0 {
		return nil, fmt.Errorf("yfinance: no data for %s", symbol)
	}

	r := result.Chart.Result[0]
	q := r.Indicators.Quote[0]

	n := len(r.Timestamp)
	bars := make([]*commonv1.Bar, 0, n)
	for i := 0; i < n; i++ {
		// Skip rows with all-null OHLC (non-trading days in Yahoo data)
		if i >= len(q.Open) || (q.Open[i] == 0 && q.Close[i] == 0) {
			continue
		}
		bar := &commonv1.Bar{
			Symbol:    symbol,
			Timestamp: r.Timestamp[i] * 1000, // Yahoo returns seconds, proto expects milliseconds
			Frequency: "1d",
		}
		if i < len(q.Open) {
			bar.Open = q.Open[i]
		}
		if i < len(q.High) {
			bar.High = q.High[i]
		}
		if i < len(q.Low) {
			bar.Low = q.Low[i]
		}
		if i < len(q.Close) {
			bar.Close = q.Close[i]
		}
		if i < len(q.Volume) {
			bar.Volume = q.Volume[i]
		}
		bars = append(bars, bar)
	}
	return bars, nil
}
