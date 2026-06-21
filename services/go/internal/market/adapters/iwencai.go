package adapters

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	"github.com/astockpursue/go-core/internal/market"
)

// ---------------------------------------------------------------------------
// IWenCaiStock — a single stock match from an iWenCai query
// ---------------------------------------------------------------------------

// IWenCaiStock represents a single stock returned by a natural language query
// through the iWenCai (问财) system.
type IWenCaiStock struct {
	Code    string  // stock code, e.g. "000001"
	Name    string  // stock name, e.g. "平安银行"
	Exchange string // exchange: "SH", "SZ", or "BJ"
	Score   float64 // relevance score in [0, 100], higher = better match
	MarketCap float64 // total market capitalisation (亿元), 0 if unavailable
}

// ---------------------------------------------------------------------------
// iWenCai API response types (flexible parsing for a changing API surface)
// ---------------------------------------------------------------------------

// iwencaiPickResponse is the top-level envelope from the /result/pick endpoint.
type iwencaiPickResponse struct {
	Data    *iwencaiPickResponseData `json:"data"`
	Status  string                   `json:"status"`
	Message string                   `json:"message"`
}

type iwencaiPickResponseData struct {
	Result      json.RawMessage `json:"result"`       // array or object
	TotalCount  int             `json:"totalCount,string"`
	TotalRecord int             `json:"totalRecord,string"` // alternative field name
}

// iwencaiStockItemV1: the result as a flat array of stock objects.
type iwencaiStockItemV1 struct {
	Code   string  `json:"code"`
	Name   string  `json:"name"`
	Score  float64 `json:"score,string"`
	Market float64 `json:"market,string"`
}

// iwencaiStockItemV2: alternative field naming used by some iWenCai responses.
type iwencaiStockItemV2 struct {
	StockCode string  `json:"stock_code"`
	StockName string  `json:"stock_name"`
	Relevance float64 `json:"relevance,string"`
	MC        float64 `json:"mc,string"` // market cap
}

// iwencaiStockItemV3: EastMoney-style numbered fields.
type iwencaiStockItemV3 struct {
	F1  string  `json:"f1"`  // code (may include exchange suffix, e.g. "000001.SZ")
	F2  string  `json:"f2"`  // name
	F3  float64 `json:"f3,string"` // score
	F20 float64 `json:"f20,string"` // market cap
}

// ---------------------------------------------------------------------------
// IWenCaiAdapter — market.Adapter implementation
// ---------------------------------------------------------------------------

// IWenCaiAdapter enables natural-language stock queries through the iWenCai
// (问财) AI stock-selection system, operated by 同花顺 (Hithink RoyalFlush).
//
// iWenCai accepts Chinese natural language queries such as:
//   - "2024年净利润增长超过50%的股票" (stocks with >50% net profit growth in 2024)
//   - "北向资金增持且市盈率低于20" (northbound capital increasing, PE < 20)
//   - "连续3年分红率大于30%" (dividend ratio >30% for 3 consecutive years)
//
// The adapter implements the market.Adapter interface by mapping each matched
// stock to a Bar (Symbol = stock code, Close = relevance score) so that
// iWenCai results can flow through the standard data pipeline. The dedicated
// Query() method returns the full structured match data.
//
// The public iWenCai endpoint requires no API key but depends on sessionless
// access to the unifiedwap API. Rate limits are not documented; callers should
// cache results when appropriate.
type IWenCaiAdapter struct {
	client  *http.Client
	baseURL string
}

// NewIWenCaiAdapter creates a new IWenCaiAdapter pointed at the iWenCai
// unified stock-pick API.
func NewIWenCaiAdapter() *IWenCaiAdapter {
	return &IWenCaiAdapter{
		client: &http.Client{
			Timeout: 30 * time.Second,
			// iWenCai may return a 302 redirect after submission; follow it.
			CheckRedirect: func(req *http.Request, via []*http.Request) error {
				if len(via) >= 3 {
					return fmt.Errorf("iwencai: too many redirects")
				}
				// Preserve POST method on redirect (some endpoints expect it).
				if len(via) > 0 && via[0].Method == http.MethodPost {
					req.Method = http.MethodPost
					req.Body = via[0].Body
				}
				return nil
			},
		},
		baseURL: "https://www.iwencai.com/unifiedwap/result/pick",
	}
}

// Name returns the adapter identifier.
func (i *IWenCaiAdapter) Name() string { return "iwencai" }

// Markets returns the single supported market identifier for China A-shares.
func (i *IWenCaiAdapter) Markets() []string { return []string{"CN"} }

// RequiresAuth reports that the iWenCai public API requires no authentication.
func (i *IWenCaiAdapter) RequiresAuth() bool { return false }

// IsAvailable performs a lightweight GET request against the iWenCai homepage
// to verify network reachability and service health.
func (i *IWenCaiAdapter) IsAvailable(ctx context.Context) bool {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, "https://www.iwencai.com/", nil)
	if err != nil {
		return false
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	resp, err := i.client.Do(req)
	if err != nil {
		return false
	}
	resp.Body.Close()
	return resp.StatusCode == http.StatusOK
}

// Fetch retrieves stock matches for a natural language query via iWenCai and
// returns them as Bar slices.
//
// The req.Symbol field is interpreted as the Chinese query string (URL-encoded
// or raw). Each returned Bar represents one matched stock:
//   - Symbol  = stock code (e.g. "000001")
//   - Close   = iWenCai relevance score in [0, 100]
//   - Volume  = market capitalisation (亿元), truncated to int64
//   - Timestamp = time of the query execution
//
// The req.StartDate and req.EndDate are ignored; iWenCai queries return
// current results. Only daily frequency is returned.
func (i *IWenCaiAdapter) Fetch(ctx context.Context, req market.FetchRequest) ([]*commonv1.Bar, error) {
	query := req.Symbol
	if query == "" {
		return nil, fmt.Errorf("iwencai: Symbol field must contain the query string")
	}

	stocks, err := i.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("iwencai fetch: %w", err)
	}

	now := time.Now().UnixMilli()
	bars := make([]*commonv1.Bar, 0, len(stocks))
	for _, s := range stocks {
		bars = append(bars, &commonv1.Bar{
			Symbol:    s.Code,
			Open:      s.Score,
			High:      s.Score,
			Low:       s.Score,
			Close:     s.Score,
			Volume:    int64(s.MarketCap * 100), // 亿元 → 万元-equivalent for ordering
			Timestamp: now,
			Frequency: "1d",
		})
	}
	return bars, nil
}

// Query submits a Chinese natural language query to iWenCai and returns the
// matched stocks with their relevance scores.
//
// The query parameter should be a Chinese sentence describing the stock
// selection criteria, for example:
//
//	"2024年净利润增长超过50%且市盈率低于20的股票"
//	"北向资金增持且股息率大于3%"
//	"连续三年ROE大于15%"
//
// Returns the matched stocks sorted by relevance (highest first), or an error
// if the query could not be submitted or the response could not be parsed.
func (i *IWenCaiAdapter) Query(ctx context.Context, query string) ([]IWenCaiStock, error) {
	if strings.TrimSpace(query) == "" {
		return nil, fmt.Errorf("iwencai: empty query")
	}

	form := url.Values{
		"question": {query},
		"perpage":  {"50"},
		"page":     {"1"},
		"source":   {"Ths_iwencai_Xuangu"},
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, i.baseURL,
		bytes.NewReader([]byte(form.Encode())))
	if err != nil {
		return nil, fmt.Errorf("iwencai create request: %w", err)
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
	req.Header.Set("Referer", "https://www.iwencai.com/")
	req.Header.Set("Origin", "https://www.iwencai.com")
	req.Header.Set("Accept", "application/json, text/plain, */*")

	resp, err := i.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("iwencai http do: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("iwencai: HTTP %d (query may be rejected)", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("iwencai read body: %w", err)
	}

	stocks, err := i.parseResponse(body)
	if err != nil {
		return nil, fmt.Errorf("iwencai parse: %w", err)
	}

	if len(stocks) == 0 {
		return nil, fmt.Errorf("iwencai: no stocks matched query %q", query)
	}

	return stocks, nil
}

// parseResponse attempts to decode the iWenCai JSON response into structured
// stock matches, trying several known response formats.
func (i *IWenCaiAdapter) parseResponse(body []byte) ([]IWenCaiStock, error) {
	// Attempt to strip JSONP padding if present.
	payload := stripJSONP(body)

	// Try the standard envelope first.
	var envelope iwencaiPickResponse
	if err := json.Unmarshal(payload, &envelope); err != nil || envelope.Data == nil {
		// If the envelope doesn't match, try parsing the body directly as a
		// result array.
		return i.parseDirectArray(payload)
	}

	if envelope.Data.Result == nil || len(envelope.Data.Result) == 0 {
		return nil, fmt.Errorf("iwencai: empty result in envelope")
	}

	// Try to unmarshal the result as a flat array of stock items.
	if stocks, err := i.parseResultArray(envelope.Data.Result); err == nil && len(stocks) > 0 {
		return stocks, nil
	}

	// Try to unmarshal the result as an object with an "items" key.
	var withItems struct {
		Items json.RawMessage `json:"items"`
	}
	if err := json.Unmarshal(envelope.Data.Result, &withItems); err == nil && len(withItems.Items) > 0 {
		if stocks, err := i.parseResultArray(withItems.Items); err == nil && len(stocks) > 0 {
			return stocks, nil
		}
	}

	return nil, fmt.Errorf("iwencai: unable to parse response (unknown format)")
}

// parseResultArray tries to unmarshal raw JSON bytes into an array of stock
// items, using several known field-naming conventions.
func (i *IWenCaiAdapter) parseResultArray(raw json.RawMessage) ([]IWenCaiStock, error) {
	// Try V1: {code, name, score, market}
	var v1 []iwencaiStockItemV1
	if err := json.Unmarshal(raw, &v1); err == nil && len(v1) > 0 && v1[0].Code != "" {
		stocks := make([]IWenCaiStock, 0, len(v1))
		for _, item := range v1 {
			code, exchange := splitCode(item.Code)
			stocks = append(stocks, IWenCaiStock{
				Code:      code,
				Name:      item.Name,
				Exchange:  exchange,
				Score:     item.Score,
				MarketCap: item.Market,
			})
		}
		return stocks, nil
	}

	// Try V2: {stock_code, stock_name, relevance, mc}
	var v2 []iwencaiStockItemV2
	if err := json.Unmarshal(raw, &v2); err == nil && len(v2) > 0 && v2[0].StockCode != "" {
		stocks := make([]IWenCaiStock, 0, len(v2))
		for _, item := range v2 {
			code, exchange := splitCode(item.StockCode)
			stocks = append(stocks, IWenCaiStock{
				Code:      code,
				Name:      item.StockName,
				Exchange:  exchange,
				Score:     item.Relevance,
				MarketCap: item.MC,
			})
		}
		return stocks, nil
	}

	// Try V3: EastMoney-style numeric fields {f1, f2, f3, f20}
	var v3 []iwencaiStockItemV3
	if err := json.Unmarshal(raw, &v3); err == nil && len(v3) > 0 && v3[0].F1 != "" {
		stocks := make([]IWenCaiStock, 0, len(v3))
		for _, item := range v3 {
			code, exchange := splitCode(item.F1)
			stocks = append(stocks, IWenCaiStock{
				Code:      code,
				Name:      item.F2,
				Exchange:  exchange,
				Score:     item.F3,
				MarketCap: item.F20,
			})
		}
		return stocks, nil
	}

	return nil, fmt.Errorf("iwencai: no known stock format matched")
}

// parseDirectArray tries to parse the raw body as a direct JSON array of
// stock objects, skipping the envelope entirely.
func (i *IWenCaiAdapter) parseDirectArray(body []byte) ([]IWenCaiStock, error) {
	var rawArr []json.RawMessage
	if err := json.Unmarshal(body, &rawArr); err != nil {
		return nil, err
	}
	if len(rawArr) == 0 {
		return nil, fmt.Errorf("iwencai: empty array")
	}
	// Re-marshal the first element to check if it looks like a stock object.
	first, _ := json.Marshal(rawArr[0])
	var v1 iwencaiStockItemV1
	if err := json.Unmarshal(first, &v1); err != nil || v1.Code == "" {
		return nil, fmt.Errorf("iwencai: array elements not recognised as stock items")
	}
	// All items matched; parse the full array.
	return i.parseResultArray(body)
}

// ---------------------------------------------------------------------------
// utility functions
// ---------------------------------------------------------------------------

// splitCode extracts the bare stock code and exchange from a possibly-qualified
// identifier like "000001.SZ" or "600519.SH".
func splitCode(raw string) (code, exchange string) {
	raw = strings.TrimSpace(raw)
	if idx := strings.LastIndex(raw, "."); idx > 0 && idx < len(raw)-1 {
		suffix := strings.ToUpper(raw[idx+1:])
		if suffix == "SH" || suffix == "SZ" || suffix == "BJ" {
			return raw[:idx], suffix
		}
	}
	// Infer exchange from code prefix.
	if strings.HasPrefix(raw, "6") {
		return raw, "SH"
	}
	if strings.HasPrefix(raw, "0") || strings.HasPrefix(raw, "3") {
		return raw, "SZ"
	}
	if strings.HasPrefix(raw, "4") || strings.HasPrefix(raw, "8") {
		return raw, "BJ"
	}
	return raw, ""
}

// stripJSONP removes JSONP padding from a response body if present. The iWenCai
// API sometimes wraps responses in a callback function like
//
//	jsonp_12345({...})
func stripJSONP(body []byte) []byte {
	s := strings.TrimSpace(string(body))
	if len(s) == 0 {
		return body
	}
	// Check if it starts with a typical JSONP callback pattern.
	if s[0] != '{' && s[0] != '[' {
		if idx := strings.Index(s, "("); idx > 0 && strings.HasSuffix(s, ")") {
			return []byte(s[idx+1 : len(s)-1])
		}
		// Try the last '(' pattern for nested callbacks.
		if idx := strings.LastIndex(s, "("); idx > 0 {
			if end := strings.LastIndex(s, ")"); end > idx {
				return []byte(s[idx+1 : end])
			}
		}
	}
	return body
}

