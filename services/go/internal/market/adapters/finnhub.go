package adapters

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	"github.com/astockpursue/go-core/internal/market"
)

// ---------------------------------------------------------------------------
// FinnhubAdapter — US stock fundamental data from Finnhub.io
// ---------------------------------------------------------------------------

// FinnhubAdapter fetches US stock data from the Finnhub.io REST API.
//
// Core functionality (market.Adapter):
//   - /stock/candle — OHLCV daily bars
//
// Extended data methods:
//   - FetchInsiderTransactions — insider trading records
//   - FetchFilings            — SEC filing metadata
//   - FetchNewsSentiment      — aggregate news buzz and sentiment
//
// Free-tier rate limit: 60 requests per minute. The API key is read from
// the FINNHUB_API_KEY environment variable. The adapter returns
// IsAvailable = false when no key is set.
type FinnhubAdapter struct {
	client  *http.Client
	baseURL string
	apiKey  string
}

// finnhubCandleResponse mirrors the Finnhub /stock/candle JSON response.
type finnhubCandleResponse struct {
	Close  []float64 `json:"c"`
	High   []float64 `json:"h"`
	Low    []float64 `json:"l"`
	Open   []float64 `json:"o"`
	Status string    `json:"s"`
	Time   []int64   `json:"t"`
	Volume []int64   `json:"v"`
}

// InsiderTransaction represents a single insider trading record returned by
// the Finnhub /stock/insider-transactions endpoint.
type InsiderTransaction struct {
	Symbol          string  `json:"symbol"`
	Shares          int64   `json:"shares"`
	Change          float64 `json:"change"`
	FilingDate      string  `json:"filingDate"`
	TransactionDate string  `json:"transactionDate"`
	TransactionType string  `json:"transactionType"`
	Price           float64 `json:"price"`
}

// SECFiling represents a single SEC filing record returned by the Finnhub
// /stock/filings endpoint.
type SECFiling struct {
	Symbol      string `json:"symbol"`
	FilingID    string `json:"filingId"`
	FilingType  string `json:"filingType"`
	FiledDate   string `json:"filedDate"`
	Description string `json:"description"`
	URL         string `json:"url"`
}

// NewsSentiment represents aggregate news sentiment for a symbol returned
// by the Finnhub /news/sentiment endpoint.
type NewsSentiment struct {
	Symbol              string  `json:"symbol"`
	Buzz                float64 `json:"buzz"`
	CompanyNewsScore    float64 `json:"companyNewsScore"`
	SectorAverageBullish float64 `json:"sectorAverageBullish"`
	LastUpdated         string  `json:"lastUpdated"`
}

// finnhubInsiderResponse wraps the list returned by the insider endpoint.
type finnhubInsiderResponse struct {
	Data []InsiderTransaction `json:"data"`
}

// finnhubFilingResponse wraps the list returned by the filing endpoint.
type finnhubFilingResponse struct {
	Data []SECFiling `json:"data"`
}

// NewFinnhubAdapter creates a new Finnhub adapter. The API key is read from
// the FINNHUB_API_KEY environment variable at construction time.
func NewFinnhubAdapter() *FinnhubAdapter {
	return &FinnhubAdapter{
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		baseURL: "https://finnhub.io/api/v1",
		apiKey:  os.Getenv("FINNHUB_API_KEY"),
	}
}

// Name returns the adapter identifier.
func (f *FinnhubAdapter) Name() string { return "finnhub" }

// Markets returns the single supported market identifier.
func (f *FinnhubAdapter) Markets() []string { return []string{"US"} }

// RequiresAuth returns true when an API key is configured, false otherwise.
// The adapter is unusable without a key because Finnhub requires it.
func (f *FinnhubAdapter) RequiresAuth() bool { return f.apiKey != "" }

// IsAvailable checks Finnhub connectivity by calling /stock/symbol for AAPL.
// Returns false immediately if no API key is set.
func (f *FinnhubAdapter) IsAvailable(ctx context.Context) bool {
	if f.apiKey == "" {
		return false
	}
	u := fmt.Sprintf("%s/stock/symbol?exchange=US&token=%s", f.baseURL, f.apiKey)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	if err != nil {
		return false
	}
	req.Header.Set("User-Agent", "Mozilla/5.0")
	resp, err := f.client.Do(req)
	if err != nil {
		return false
	}
	resp.Body.Close()
	return resp.StatusCode == http.StatusOK
}

// Fetch retrieves daily OHLCV bars from Finnhub /stock/candle.
//
// Supported frequency mappings:
//   - "1d" (default), "D" → daily resolution
//   - "1h", "60"         → 60-minute resolution
//   - "1m", "1"          → 1-minute resolution
//   - "5", "15", "30"    → intraday resolutions
//   - "W", "1w"          → weekly resolution
//   - "M", "1M"          → monthly resolution
//
// The Symbol field in req should be a recognised US ticker (e.g. "AAPL").
func (f *FinnhubAdapter) Fetch(ctx context.Context, req market.FetchRequest) ([]*commonv1.Bar, error) {
	if f.apiKey == "" {
		return nil, fmt.Errorf("finnhub: FINNHUB_API_KEY not set")
	}

	from := req.StartDate.Unix()
	to := req.EndDate.Unix()
	if to == 0 {
		to = time.Now().Unix()
	}

	resolution := f.resolveResolution(req.Frequency)

	u := fmt.Sprintf("%s/stock/candle?symbol=%s&resolution=%s&from=%d&to=%d&token=%s",
		f.baseURL, req.Symbol, resolution, from, to, f.apiKey)

	resp, err := f.doRequest(ctx, u)
	if err != nil {
		return nil, fmt.Errorf("finnhub fetch: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusTooManyRequests {
		return nil, fmt.Errorf("finnhub rate limited (429)")
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("finnhub HTTP %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("finnhub read body: %w", err)
	}

	var result finnhubCandleResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("finnhub parse: %w", err)
	}

	if result.Status != "ok" {
		return nil, fmt.Errorf("finnhub API error: status=%s", result.Status)
	}

	n := len(result.Time)
	bars := make([]*commonv1.Bar, 0, n)
	for i := 0; i < n; i++ {
		// Skip entries with missing or zero open (non-trading days).
		if i >= len(result.Open) || result.Open[i] == 0 {
			continue
		}
		bar := &commonv1.Bar{
			Symbol:    req.Symbol,
			Timestamp: result.Time[i] * 1000, // Finnhub returns seconds, proto needs ms
			Frequency: stringOr(req.Frequency, "1d"),
		}
		if i < len(result.Open) {
			bar.Open = result.Open[i]
		}
		if i < len(result.High) {
			bar.High = result.High[i]
		}
		if i < len(result.Low) {
			bar.Low = result.Low[i]
		}
		if i < len(result.Close) {
			bar.Close = result.Close[i]
		}
		if i < len(result.Volume) {
			bar.Volume = result.Volume[i]
		}
		bars = append(bars, bar)
	}
	return bars, nil
}

// ---------------------------------------------------------------------------
// Extended data methods
// ---------------------------------------------------------------------------

// FetchInsiderTransactions retrieves insider transaction records for the
// given symbol within the date range.
func (f *FinnhubAdapter) FetchInsiderTransactions(ctx context.Context, symbol string, start, end time.Time) ([]InsiderTransaction, error) {
	if f.apiKey == "" {
		return nil, fmt.Errorf("finnhub: FINNHUB_API_KEY not set")
	}

	u := fmt.Sprintf("%s/stock/insider-transactions?symbol=%s&from=%s&to=%s&token=%s",
		f.baseURL, symbol, start.Format("2006-01-02"), end.Format("2006-01-02"), f.apiKey)

	resp, err := f.doRequest(ctx, u)
	if err != nil {
		return nil, fmt.Errorf("finnhub insider: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusTooManyRequests {
		return nil, fmt.Errorf("finnhub rate limited (429)")
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("finnhub read body: %w", err)
	}

	var result finnhubInsiderResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("finnhub insider parse: %w", err)
	}
	return result.Data, nil
}

// FetchFilings retrieves SEC filing records for the given symbol within the
// date range.
func (f *FinnhubAdapter) FetchFilings(ctx context.Context, symbol string, start, end time.Time) ([]SECFiling, error) {
	if f.apiKey == "" {
		return nil, fmt.Errorf("finnhub: FINNHUB_API_KEY not set")
	}

	u := fmt.Sprintf("%s/stock/filings?symbol=%s&from=%s&to=%s&token=%s",
		f.baseURL, symbol, start.Format("2006-01-02"), end.Format("2006-01-02"), f.apiKey)

	resp, err := f.doRequest(ctx, u)
	if err != nil {
		return nil, fmt.Errorf("finnhub filings: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusTooManyRequests {
		return nil, fmt.Errorf("finnhub rate limited (429)")
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("finnhub read body: %w", err)
	}

	var result finnhubFilingResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("finnhub filings parse: %w", err)
	}
	return result.Data, nil
}

// FetchNewsSentiment retrieves aggregate news buzz and sentiment scores for
// the given symbol from Finnhub's /news/sentiment endpoint.
func (f *FinnhubAdapter) FetchNewsSentiment(ctx context.Context, symbol string) (*NewsSentiment, error) {
	if f.apiKey == "" {
		return nil, fmt.Errorf("finnhub: FINNHUB_API_KEY not set")
	}

	u := fmt.Sprintf("%s/news/sentiment?symbol=%s&token=%s", f.baseURL, symbol, f.apiKey)

	resp, err := f.doRequest(ctx, u)
	if err != nil {
		return nil, fmt.Errorf("finnhub news sentiment: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusTooManyRequests {
		return nil, fmt.Errorf("finnhub rate limited (429)")
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("finnhub read body: %w", err)
	}

	var result NewsSentiment
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("finnhub news sentiment parse: %w", err)
	}
	return &result, nil
}

// ---------------------------------------------------------------------------
// internal helpers
// ---------------------------------------------------------------------------

// doRequest creates and sends an authenticated GET request.
func (f *FinnhubAdapter) doRequest(ctx context.Context, url string) (*http.Response, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	return f.client.Do(req)
}

// resolveResolution maps common frequency strings to Finnhub resolution values.
func (f *FinnhubAdapter) resolveResolution(freq string) string {
	switch freq {
	case "1m", "1":
		return "1"
	case "5":
		return "5"
	case "15":
		return "15"
	case "30":
		return "30"
	case "1h", "60":
		return "60"
	case "W", "1w":
		return "W"
	case "M", "1M":
		return "M"
	default: // "1d", "D", or empty
		return "D"
	}
}

// stringOr returns primary if non-empty, otherwise fallback.
func stringOr(s, fallback string) string {
	if s != "" {
		return s
	}
	return fallback
}
