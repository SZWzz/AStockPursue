package adapters

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	"github.com/astockpursue/go-core/internal/market"
)

// ---------------------------------------------------------------------------
// Types for extended northbound data methods
// ---------------------------------------------------------------------------

// NorthboundActiveStock represents a single stock ranked by northbound capital
// activity on a given trading day.
type NorthboundActiveStock struct {
	Code          string  // stock code (e.g. "600519")
	Name          string  // stock name (e.g. "贵州茅台")
	Price         float64 // latest price
	NetInflow     float64 // net northbound capital inflow (万元)
	BuyAmount     float64 // total buy amount via Stock Connect (万元)
	SellAmount    float64 // total sell amount via Stock Connect (万元)
	InflowPercent float64 // net inflow as a percentage of turnover
	Rank          int     // activity rank (1-based)
}

// NorthboundSectorFlow represents industry-level northbound capital flow
// distribution.
type NorthboundSectorFlow struct {
	SectorName string  // industry/sector name
	NetInflow  float64 // net capital inflow (万元)
	StockCount int     // number of stocks tracked in this sector
	Rank       int     // ranking by net inflow
}

// ---------------------------------------------------------------------------
// EastMoney API response types
// ---------------------------------------------------------------------------

// northboundKlineResponse mirrors the EastMoney /api/qt/kamt.kline/get response.
type northboundKlineResponse struct {
	Data *northboundKlineData `json:"data"`
}

type northboundKlineData struct {
	Klines []string `json:"klines"`
}

// northboundRankResponse mirrors the EastMoney /api/qt/kamt.rank/get response.
type northboundRankResponse struct {
	Data *northboundRankData `json:"data"`
}

type northboundRankData struct {
	Diff []northboundRankItem `json:"diff"`
}

// northboundRankItem represents a single stock entry in the ranking response.
// Field names use EastMoney's internal numbering convention.
type northboundRankItem struct {
	Code          string  `json:"f12"`
	Name          string  `json:"f14"`
	Price         float64 `json:"f4,string"`
	NetInflow     float64 `json:"f62,string"`
	BuyAmount     float64 `json:"f60,string"`
	SellAmount    float64 `json:"f61,string"`
	InflowPercent float64 `json:"f63,string"`
}

// northboundSectorItem represents a single sector entry in the sector-flow
// response.
type northboundSectorItem struct {
	SectorName string  `json:"f14"`
	NetInflow  float64 `json:"f4,string"`
	StockCount int     `json:"f5,string"`
}

// ---------------------------------------------------------------------------
// NorthboundAdapter – market.Adapter implementation
// ---------------------------------------------------------------------------

// NorthboundAdapter fetches northbound capital (北向资金) flow data from
// EastMoney's public push API. Northbound capital tracks foreign investment
// flowing into China A-shares through the Shanghai-HK Stock Connect (沪股通)
// and Shenzhen-HK Stock Connect (深股通) programs.
//
// The EastMoney push API is free and requires no authentication. All data is
// publicly available from https://data.eastmoney.com/.
type NorthboundAdapter struct {
	client  *http.Client
	baseURL string
}

// NewNorthboundAdapter creates a new NorthboundAdapter pointed at EastMoney's
// northbound capital data API.
func NewNorthboundAdapter() *NorthboundAdapter {
	return &NorthboundAdapter{
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		baseURL: "https://push2.eastmoney.com/api/qt/kamt.kline/get",
	}
}

// Name returns the adapter identifier.
func (n *NorthboundAdapter) Name() string { return "northbound" }

// Markets returns the single supported market identifier for China A-shares.
func (n *NorthboundAdapter) Markets() []string { return []string{"CN"} }

// RequiresAuth reports that the EastMoney northbound API is free and requires
// no API key or token.
func (n *NorthboundAdapter) RequiresAuth() bool { return false }

// IsAvailable performs a lightweight GET request against the EastMoney
// northbound kline API to verify network reachability and service health.
// Requests a single data point (lmt=1) to minimise bandwidth.
func (n *NorthboundAdapter) IsAvailable(ctx context.Context) bool {
	u := fmt.Sprintf("%s?fields1=f1,f2,f3&fields2=f51,f52,f53&klt=101&fqt=1&lmt=1", n.baseURL)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	if err != nil {
		return false
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	req.Header.Set("Referer", "https://data.eastmoney.com/")
	resp, err := n.client.Do(req)
	if err != nil {
		return false
	}
	resp.Body.Close()
	return resp.StatusCode == http.StatusOK
}

// Fetch retrieves daily northbound capital flow time series from EastMoney.
//
// Each returned Bar represents one trading day:
//   - Close  = total net northbound inflow (万元). Positive = net buying,
//     negative = net selling by foreign investors.
//   - Open   = previous trading day's Close, providing a reference baseline.
//   - High   = larger of the SH and SZ component inflows for the day.
//   - Low    = smaller of the SH and SZ component inflows for the day.
//   - Volume = cumulative total northbound capital (万元) up to this day.
//
// The Symbol field in req is ignored; northbound data is an aggregate
// market-level metric. Only daily frequency ("1d") is supported.
//
// The req.StartDate and req.EndDate are used to determine how many data
// points to request (clamped to [1, 1000]).
func (n *NorthboundAdapter) Fetch(ctx context.Context, req market.FetchRequest) ([]*commonv1.Bar, error) {
	lmt := daysInRange(req.StartDate, req.EndDate)
	if lmt < 1 {
		lmt = 1
	}
	if lmt > 1000 {
		lmt = 1000
	}

	u := fmt.Sprintf("%s?fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55&klt=101&fqt=1&lmt=%d",
		n.baseURL, lmt)

	resp, err := n.doRequest(ctx, u)
	if err != nil {
		return nil, fmt.Errorf("northbound fetch: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("northbound API returned HTTP %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("northbound read body: %w", err)
	}

	var result northboundKlineResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("northbound json decode: %w", err)
	}

	if result.Data == nil || len(result.Data.Klines) == 0 {
		return nil, fmt.Errorf("northbound: no data returned")
	}

	bars := make([]*commonv1.Bar, 0, len(result.Data.Klines))
	for _, kline := range result.Data.Klines {
		bar, err := n.parseKline(kline)
		if err != nil {
			// Skip malformed entries rather than failing the entire fetch.
			continue
		}
		bars = append(bars, bar)
	}

	if len(bars) == 0 {
		return nil, fmt.Errorf("northbound: no valid bars after parsing")
	}

	// Sort chronologically, then backfill Open from previous bar's Close.
	sort.Slice(bars, func(i, j int) bool {
		return bars[i].Timestamp < bars[j].Timestamp
	})
	for i := len(bars) - 1; i > 0; i-- {
		bars[i].Open = bars[i-1].Close
	}
	if len(bars) > 0 {
		bars[0].Open = bars[0].Close // first bar: Open = Close
	}

	return bars, nil
}

// parseKline converts a single EastMoney kline CSV string into a Bar.
//
// EastMoney kline format:
//
//	"YYYY-MM-DD,sh_net_inflow,sz_net_inflow,total_net_inflow,cumulative_total"
//
// All flow values are denominated in 万元 (ten-thousands of CNY).
func (n *NorthboundAdapter) parseKline(kline string) (*commonv1.Bar, error) {
	parts := strings.Split(kline, ",")
	if len(parts) < 4 {
		return nil, fmt.Errorf("northbound: malformed kline entry (got %d fields)", len(parts))
	}

	ts, err := time.Parse("2006-01-02", strings.TrimSpace(parts[0]))
	if err != nil {
		return nil, fmt.Errorf("northbound: parse date %q: %w", parts[0], err)
	}

	shInflow, _ := strconv.ParseFloat(strings.TrimSpace(parts[1]), 64)
	szInflow, _ := strconv.ParseFloat(strings.TrimSpace(parts[2]), 64)
	totalInflow, _ := strconv.ParseFloat(strings.TrimSpace(parts[3]), 64)
	cumulative := 0.0
	if len(parts) >= 5 {
		cumulative, _ = strconv.ParseFloat(strings.TrimSpace(parts[4]), 64)
	}

	high := math.Max(shInflow, szInflow)
	low := math.Min(shInflow, szInflow)
	if math.IsNaN(high) || math.IsNaN(low) {
		high = totalInflow
		low = totalInflow
	}

	return &commonv1.Bar{
		Symbol:    "northbound",
		Open:      totalInflow, // will be backfilled in Fetch
		High:      high,
		Low:       low,
		Close:     totalInflow,
		Volume:    int64(math.Round(cumulative)),
		Timestamp: ts.UnixMilli(),
		Frequency: "1d",
	}, nil
}

// FetchTop10Active returns the top 10 stocks ranked by northbound capital
// net inflow for the latest trading day.
//
// Data comes from the EastMoney northbound stock ranking API
// (/api/qt/kamt.rank/get with type=1 for buy-side ranking).
func (n *NorthboundAdapter) FetchTop10Active(ctx context.Context) ([]NorthboundActiveStock, error) {
	u := "https://push2.eastmoney.com/api/qt/kamt.rank/get" +
		"?fields1=f1,f2,f3,f4,f5,f6" +
		"&fields2=f12,f14,f4,f60,f61,f62,f63" +
		"&market=1&type=1"

	resp, err := n.doRequest(ctx, u)
	if err != nil {
		return nil, fmt.Errorf("northbound top10: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("northbound top10: HTTP %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("northbound top10 read body: %w", err)
	}

	var result northboundRankResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("northbound top10 json decode: %w", err)
	}

	if result.Data == nil || len(result.Data.Diff) == 0 {
		return nil, fmt.Errorf("northbound top10: no data returned")
	}

	limit := 10
	if len(result.Data.Diff) < limit {
		limit = len(result.Data.Diff)
	}

	stocks := make([]NorthboundActiveStock, 0, limit)
	for i, item := range result.Data.Diff[:limit] {
		stocks = append(stocks, NorthboundActiveStock{
			Code:          item.Code,
			Name:          item.Name,
			Price:         item.Price,
			NetInflow:     item.NetInflow,
			BuyAmount:     item.BuyAmount,
			SellAmount:    item.SellAmount,
			InflowPercent: item.InflowPercent,
			Rank:          i + 1,
		})
	}

	return stocks, nil
}

// FetchSectorDistribution returns the industry-level breakdown of northbound
// capital flow for the latest trading day, sorted by net inflow descending.
//
// Data comes from the EastMoney northbound sector-flow API
// (/api/qt/kamt.rank/get with type=3 for sector-level aggregation).
func (n *NorthboundAdapter) FetchSectorDistribution(ctx context.Context) ([]NorthboundSectorFlow, error) {
	u := "https://push2.eastmoney.com/api/qt/kamt.rank/get" +
		"?fields1=f1,f2,f3,f4,f5,f6" +
		"&fields2=f14,f4,f5" +
		"&market=1&type=3"

	resp, err := n.doRequest(ctx, u)
	if err != nil {
		return nil, fmt.Errorf("northbound sector: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("northbound sector: HTTP %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("northbound sector read body: %w", err)
	}

	var result struct {
		Data *struct {
			Diff []northboundSectorItem `json:"diff"`
		} `json:"data"`
	}
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("northbound sector json decode: %w", err)
	}

	if result.Data == nil || len(result.Data.Diff) == 0 {
		return nil, fmt.Errorf("northbound sector: no data returned")
	}

	sectors := make([]NorthboundSectorFlow, 0, len(result.Data.Diff))
	for i, item := range result.Data.Diff {
		sectors = append(sectors, NorthboundSectorFlow{
			SectorName: item.SectorName,
			NetInflow:  item.NetInflow,
			StockCount: item.StockCount,
			Rank:       i + 1,
		})
	}

	return sectors, nil
}

// ---------------------------------------------------------------------------
// internal helpers
// ---------------------------------------------------------------------------

// doRequest creates and sends an HTTP GET request with browser-like headers
// and the EastMoney referer.
func (n *NorthboundAdapter) doRequest(ctx context.Context, url string) (*http.Response, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	req.Header.Set("Referer", "https://data.eastmoney.com/")
	return n.client.Do(req)
}

// daysInRange returns the number of calendar days between start and end,
// inclusive of both endpoints. Returns at least 1.
func daysInRange(start, end time.Time) int {
	if end.Before(start) {
		return 1
	}
	days := int(end.Sub(start).Hours()/24) + 1
	if days < 1 {
		return 1
	}
	return days
}
