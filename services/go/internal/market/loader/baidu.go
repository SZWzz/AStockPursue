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
	RegisterPriority(NewBaiduLoader(), 6)
}

// BaiduLoader fetches historical A-share daily bars from Baidu Finance.
// No API key required. Supports date-range queries via start_date/end_date params.
type BaiduLoader struct {
	client  *http.Client
	baseURL string
}

// baiduResponse is the top-level JSON structure returned by Baidu Finance.
type baiduResponse struct {
	Status int              `json:"status"`
	Data   []baiduKlineItem `json:"data"`
}

type baiduKlineItem struct {
	Date   string  `json:"date"`
	Open   float64 `json:"open"`
	Close  float64 `json:"close"`
	High   float64 `json:"high"`
	Low    float64 `json:"low"`
	Volume int64   `json:"volume"`
}

func NewBaiduLoader() *BaiduLoader {
	return &BaiduLoader{
		client:  &http.Client{Timeout: 30 * time.Second},
		baseURL: "https://finance.pc22333.com",
	}
}

func (b *BaiduLoader) Name() string { return "baidu" }

func (b *BaiduLoader) IsAvailable() bool {
	req, err := http.NewRequest("GET", b.baseURL+"/finance/stock/history?code=sh.600000", nil)
	if err != nil {
		return false
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	resp, err := b.client.Do(req)
	if err != nil {
		return false
	}
	resp.Body.Close()
	return true
}

func (b *BaiduLoader) FetchBars(symbol string, start, end time.Time) ([]*commonv1.Bar, error) {
	code := b.toBaiduCode(symbol)
	url := fmt.Sprintf("%s/finance/stock/history?code=%s&start_date=%s&end_date=%s",
		b.baseURL, code, start.Format("2006-01-02"), end.Format("2006-01-02"))

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("baidu create request: %w", err)
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

	resp, err := b.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("baidu fetch: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("baidu read body: %w", err)
	}

	var result baiduResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("baidu parse: %w", err)
	}

	if result.Status != 0 {
		return nil, fmt.Errorf("baidu API error: status=%d", result.Status)
	}

	bars := make([]*commonv1.Bar, 0, len(result.Data))
	for _, item := range result.Data {
		ts, err := time.Parse("2006-01-02", item.Date)
		if err != nil {
			continue
		}
		bars = append(bars, &commonv1.Bar{
			Symbol:    symbol,
			Open:      item.Open,
			High:      item.High,
			Low:       item.Low,
			Close:     item.Close,
			Volume:    item.Volume,
			Timestamp: ts.UnixMilli(),
			Frequency: "1d",
		})
	}
	return bars, nil
}

// toBaiduCode converts an A-share stock code to Baidu's exchange-prefixed format.
// 6xxxxx → sh. (Shanghai), 0/3xxxxx → sz. (Shenzhen), 4/8/9xxxxx → bj. (Beijing).
func (b *BaiduLoader) toBaiduCode(symbol string) string {
	if strings.HasPrefix(symbol, "6") {
		return "sh." + symbol
	}
	if strings.HasPrefix(symbol, "0") || strings.HasPrefix(symbol, "3") {
		return "sz." + symbol
	}
	if strings.HasPrefix(symbol, "4") || strings.HasPrefix(symbol, "8") || strings.HasPrefix(symbol, "9") {
		return "bj." + symbol
	}
	return "sh." + symbol
}
