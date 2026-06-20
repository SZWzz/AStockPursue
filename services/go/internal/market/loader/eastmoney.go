package loader

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
)

func init() {
	Register(NewEastMoneyLoader())
}

type EastMoneyLoader struct {
	client  *http.Client
	baseURL string
}

func NewEastMoneyLoader() *EastMoneyLoader {
	return &EastMoneyLoader{
		client:  &http.Client{Timeout: 30 * time.Second},
		baseURL: "https://push2his.eastmoney.com",
	}
}

func (e *EastMoneyLoader) Name() string { return "eastmoney" }

func (e *EastMoneyLoader) IsAvailable() bool {
	resp, err := e.client.Get(e.baseURL + "/api/qt/stock/kline/get")
	if err != nil {
		return false
	}
	resp.Body.Close()
	return true
}

func (e *EastMoneyLoader) FetchBars(symbol string, start, end time.Time) ([]*commonv1.Bar, error) {
	secID := e.toSecID(symbol)
	url := fmt.Sprintf("%s/api/qt/stock/kline/get?secid=%s&fields=f43,f44,f45,f46,f47&klt=101&fqt=1",
		e.baseURL, secID)

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("eastmoney create request: %w", err)
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	resp, err := e.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("eastmoney fetch: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("eastmoney read body: %w", err)
	}

	var result struct {
		Data struct {
			KLines []string `json:"klines"`
		} `json:"data"`
	}
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("eastmoney parse: %w", err)
	}

	var bars []*commonv1.Bar
	for _, kline := range result.Data.KLines {
		bar, err := e.parseKLine(kline)
		if err != nil {
			continue
		}
		bar.Symbol = symbol
		bars = append(bars, bar)
	}
	return bars, nil
}

func (e *EastMoneyLoader) toSecID(symbol string) string {
	if strings.HasPrefix(symbol, "6") {
		return "1." + symbol
	}
	if strings.HasPrefix(symbol, "4") || strings.HasPrefix(symbol, "8") || strings.HasPrefix(symbol, "9") {
		return "2." + symbol
	}
	return "0." + symbol
}

func (e *EastMoneyLoader) parseKLine(kline string) (*commonv1.Bar, error) {
	parts := strings.Split(kline, ",")
	if len(parts) < 6 {
		return nil, fmt.Errorf("invalid kline: %s", kline)
	}
	ts, err := time.Parse("2006-01-02", parts[0])
	if err != nil {
		return nil, err
	}
	open, err := strconv.ParseFloat(parts[1], 64)
	if err != nil {
		log.Printf("parse error for field open: %v", err)
	}
	close, err := strconv.ParseFloat(parts[2], 64)
	if err != nil {
		log.Printf("parse error for field close: %v", err)
	}
	high, err := strconv.ParseFloat(parts[3], 64)
	if err != nil {
		log.Printf("parse error for field high: %v", err)
	}
	low, err := strconv.ParseFloat(parts[4], 64)
	if err != nil {
		log.Printf("parse error for field low: %v", err)
	}
	vol, err := strconv.ParseInt(parts[5], 10, 64)
	if err != nil {
		log.Printf("parse error for field vol: %v", err)
	}

	return &commonv1.Bar{
		Open: open, Close: close, High: high, Low: low,
		Volume: vol, Timestamp: ts.UnixMilli(), Frequency: "1d",
	}, nil
}
