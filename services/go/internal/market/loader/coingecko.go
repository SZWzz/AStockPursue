package loader

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
)

func init() {
	// Priority 12: low-priority, no API key, good for crypto fallback
	RegisterPriority(NewCoinGeckoLoader(), 12)
}

// CoinGeckoLoader fetches historical daily prices from the CoinGecko public API.
// Supports 1000+ cryptocurrencies. No API key required (free tier: ~30 req/min).
// Note: CoinGecko only provides OHLC via /ohlc endpoint; the simpler /market_chart
// endpoint provides timestamp+price only, which we use as Open=High=Low=Close.
type CoinGeckoLoader struct {
	client  *http.Client
	baseURL string
}

// cgResponse is the CoinGecko /market_chart JSON structure.
type cgResponse struct {
	Prices       [][]float64 `json:"prices"`
	TotalVolumes [][]float64 `json:"total_volumes"`
}

func NewCoinGeckoLoader() *CoinGeckoLoader {
	return &CoinGeckoLoader{
		client:  &http.Client{Timeout: 30 * time.Second},
		baseURL: "https://api.coingecko.com/api/v3",
	}
}

func (c *CoinGeckoLoader) Name() string { return "coingecko" }

func (c *CoinGeckoLoader) IsAvailable() bool {
	req, err := http.NewRequest("GET", c.baseURL+"/ping", nil)
	if err != nil {
		return false
	}
	resp, err := c.client.Do(req)
	if err != nil {
		return false
	}
	resp.Body.Close()
	return resp.StatusCode == http.StatusOK
}

func (c *CoinGeckoLoader) FetchBars(symbol string, start, end time.Time) ([]*commonv1.Bar, error) {
	// CoinGecko uses slug-based IDs (lowercase, hyphenated)
	coinID := c.toCoinID(symbol)
	from := start.Unix()
	to := end.Unix()
	if to == 0 {
		to = time.Now().Unix()
	}

	url := fmt.Sprintf("%s/coins/%s/market_chart/range?vs_currency=usd&from=%d&to=%d",
		c.baseURL, coinID, from, to)

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("coingecko create request: %w", err)
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("coingecko fetch: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusTooManyRequests {
		return nil, fmt.Errorf("coingecko rate limited (429)")
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("coingecko read body: %w", err)
	}

	var result cgResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("coingecko parse: %w", err)
	}

	bars := make([]*commonv1.Bar, 0, len(result.Prices))
	for i, p := range result.Prices {
		if len(p) < 2 {
			continue
		}
		ts := int64(p[0])
		price := p[1]
		volume := int64(0)
		if i < len(result.TotalVolumes) && len(result.TotalVolumes[i]) >= 2 {
			volume = int64(result.TotalVolumes[i][1])
		}
		bars = append(bars, &commonv1.Bar{
			Symbol:    symbol,
			Open:      price,
			High:      price,
			Low:       price,
			Close:     price,
			Volume:    volume,
			Timestamp: ts,
			Frequency: "1d",
		})
	}
	return bars, nil
}

// toCoinID converts common ticker symbols to CoinGecko coin IDs.
func (c *CoinGeckoLoader) toCoinID(symbol string) string {
	known := map[string]string{
		"BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin",
		"SOL": "solana", "XRP": "ripple", "ADA": "cardano",
		"DOGE": "dogecoin", "DOT": "polkadot", "MATIC": "matic-network",
		"AVAX": "avalanche-2", "LINK": "chainlink", "TRX": "tron",
		"LTC": "litecoin", "ATOM": "cosmos", "UNI": "uniswap",
	}
	s := strings.ToUpper(strings.TrimSpace(symbol))
	if id, ok := known[s]; ok {
		return id
	}
	return strings.ToLower(s)
}
