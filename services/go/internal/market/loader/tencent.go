package loader

import (
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
)

func init() {
	RegisterPriority(NewTencentLoader(), 5)
}

type TencentLoader struct {
	client  *http.Client
	baseURL string
}

func NewTencentLoader() *TencentLoader {
	return &TencentLoader{
		client:  &http.Client{Timeout: 30 * time.Second},
		baseURL: "http://qt.gtimg.cn",
	}
}

func (t *TencentLoader) Name() string { return "tencent" }

func (t *TencentLoader) IsAvailable() bool {
	resp, err := t.client.Get(t.baseURL)
	if err != nil {
		return false
	}
	resp.Body.Close()
	return true
}

func (t *TencentLoader) FetchBars(symbol string, start, end time.Time) ([]*commonv1.Bar, error) {
	if !start.IsZero() && !end.IsZero() {
		return nil, fmt.Errorf("tencent loader does not support historical data")
	}
	prefix := "sh"
	if strings.HasPrefix(symbol, "0") || strings.HasPrefix(symbol, "3") {
		prefix = "sz"
	}
	url := fmt.Sprintf("%s/q=sd_%s%s", t.baseURL, prefix, symbol)

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("tencent create request: %w", err)
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	resp, err := t.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("tencent fetch: %w", err)
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	return t.parseResponse(symbol, string(body))
}

func (t *TencentLoader) parseResponse(symbol, raw string) ([]*commonv1.Bar, error) {
	idx := strings.Index(raw, "\"")
	if idx < 0 {
		return nil, fmt.Errorf("tencent: unexpected response format for %s", symbol)
	}
	data := raw[idx+1:]
	endIdx := strings.LastIndex(data, "\"")
	if endIdx >= 0 {
		data = data[:endIdx]
	}

	parts := strings.Split(data, "~")
	if len(parts) < 8 {
		return nil, fmt.Errorf("tencent: expected >=8 fields, got %d for %s", len(parts), symbol)
	}

	open, _ := strconv.ParseFloat(parts[3], 64)
	close_, _ := strconv.ParseFloat(parts[4], 64)
	high, _ := strconv.ParseFloat(parts[5], 64)
	low, _ := strconv.ParseFloat(parts[6], 64)
	volStr := strings.ReplaceAll(parts[7], ",", "")
	vol, _ := strconv.ParseFloat(volStr, 64)

	return []*commonv1.Bar{{
		Symbol: symbol, Open: open, Close: close_, High: high, Low: low,
		Volume: int64(vol), Timestamp: time.Now().UnixMilli(), Frequency: "1d",
	}}, nil
}
