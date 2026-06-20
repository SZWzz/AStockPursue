package loader

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
)

func init() {
	RegisterPriority(NewTwelveDataLoader(), 7)
}

// TwelveDataLoader fetches historical A-share daily bars from the Twelve Data API.
// Supports date-range queries with optional API key (env TWELVEDATA_API_KEY).
// Without an API key, rate limits are ~8 requests/minute.
type TwelveDataLoader struct {
	client  *http.Client
	baseURL string
	apiKey  string
}

// twelvedataResponse is the top-level JSON structure returned by Twelve Data.
type twelvedataResponse struct {
	Status string             `json:"status"`
	Values []twelvedataValue  `json:"values"`
}

type twelvedataValue struct {
	Datetime string `json:"datetime"`
	Open     string `json:"open"`
	High     string `json:"high"`
	Low      string `json:"low"`
	Close    string `json:"close"`
	Volume   string `json:"volume"`
}

func NewTwelveDataLoader() *TwelveDataLoader {
	return &TwelveDataLoader{
		client:  &http.Client{Timeout: 30 * time.Second},
		baseURL: "https://api.twelvedata.com",
		apiKey:  os.Getenv("TWELVEDATA_API_KEY"),
	}
}

func (t *TwelveDataLoader) Name() string { return "twelvedata" }

func (t *TwelveDataLoader) IsAvailable() bool {
	url := t.baseURL + "/time_series?symbol=600000.SHH&interval=1day&outputsize=1"
	if t.apiKey != "" {
		url += "&apikey=" + t.apiKey
	}
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return false
	}
	req.Header.Set("User-Agent", "Mozilla/5.0")
	resp, err := t.client.Do(req)
	if err != nil {
		return false
	}
	resp.Body.Close()
	return true
}

func (t *TwelveDataLoader) FetchBars(symbol string, start, end time.Time) ([]*commonv1.Bar, error) {
	twdSymbol := t.toTwelveDataSymbol(symbol)
	url := fmt.Sprintf("%s/time_series?symbol=%s&interval=1day&start_date=%s&end_date=%s",
		t.baseURL, twdSymbol, start.Format("2006-01-02"), end.Format("2006-01-02"))
	if t.apiKey != "" {
		url += "&apikey=" + t.apiKey
	}

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("twelvedata create request: %w", err)
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

	resp, err := t.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("twelvedata fetch: %w", err)
	}
	defer resp.Body.Close()

	// Rate-limited: return error so store falls through to next loader
	if resp.StatusCode == http.StatusTooManyRequests {
		return nil, fmt.Errorf("twelvedata rate limited (429)")
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("twelvedata read body: %w", err)
	}

	var result twelvedataResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("twelvedata parse: %w", err)
	}

	if result.Status != "ok" {
		return nil, fmt.Errorf("twelvedata API error: status=%s", result.Status)
	}

	bars := make([]*commonv1.Bar, 0, len(result.Values))
	for _, v := range result.Values {
		ts, err := time.Parse("2006-01-02", v.Datetime)
		if err != nil {
			continue
		}

		open, _ := strconv.ParseFloat(v.Open, 64)
		high, _ := strconv.ParseFloat(v.High, 64)
		low, _ := strconv.ParseFloat(v.Low, 64)
		close, _ := strconv.ParseFloat(v.Close, 64)
		volume, _ := strconv.ParseInt(v.Volume, 10, 64)

		bars = append(bars, &commonv1.Bar{
			Symbol:    symbol,
			Open:      open,
			High:      high,
			Low:       low,
			Close:     close,
			Volume:    volume,
			Timestamp: ts.UnixMilli(),
			Frequency: "1d",
		})
	}
	return bars, nil
}

// toTwelveDataSymbol converts an A-share code to Twelve Data's exchange-suffixed format.
// 6xxxxx → {code}.SHH (Shanghai), 0/3xxxxx → {code}.SHZ (Shenzhen), 4/8/9xxxxx → {code}.BJS (Beijing).
func (t *TwelveDataLoader) toTwelveDataSymbol(symbol string) string {
	if strings.HasPrefix(symbol, "6") {
		return symbol + ".SHH"
	}
	if strings.HasPrefix(symbol, "0") || strings.HasPrefix(symbol, "3") {
		return symbol + ".SHZ"
	}
	if strings.HasPrefix(symbol, "4") || strings.HasPrefix(symbol, "8") || strings.HasPrefix(symbol, "9") {
		return symbol + ".BJS"
	}
	return symbol + ".SHH"
}
