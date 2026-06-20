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
	RegisterPriority(NewSinaLoader(), 1)
}

// SinaLoader fetches real-time A-share quotes from Sina Finance (hq.sinajs.cn).
// It provides rapid real-time snapshots but does not support historical data queries.
type SinaLoader struct {
	client  *http.Client
	baseURL string
}

func NewSinaLoader() *SinaLoader {
	return &SinaLoader{
		client:  &http.Client{Timeout: 10 * time.Second},
		baseURL: "http://hq.sinajs.cn",
	}
}

func (s *SinaLoader) Name() string { return "sina" }

func (s *SinaLoader) IsAvailable() bool {
	req, err := http.NewRequest("GET", s.baseURL+"/list=sh600000", nil)
	if err != nil {
		return false
	}
	req.Header.Set("Referer", "http://finance.sina.com.cn")
	resp, err := s.client.Do(req)
	if err != nil {
		return false
	}
	resp.Body.Close()
	return true
}

func (s *SinaLoader) FetchBars(symbol string, start, end time.Time) ([]*commonv1.Bar, error) {
	if !start.IsZero() && !end.IsZero() {
		return nil, fmt.Errorf("sina loader does not support historical data")
	}

	code := s.toSinaCode(symbol)
	url := s.baseURL + "/list=" + code

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("sina create request: %w", err)
	}
	req.Header.Set("Referer", "http://finance.sina.com.cn")
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("sina fetch: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("sina read body: %w", err)
	}

	bar, err := s.parseResponse(string(body), symbol)
	if err != nil {
		return nil, err
	}
	return []*commonv1.Bar{bar}, nil
}

// toSinaCode converts an A-share stock code to Sina's exchange-prefixed format.
// 6xxxxx → sh (Shanghai), 0xxxxx/3xxxxx → sz (Shenzhen), 4/8/9xxxxx → bj (Beijing).
func (s *SinaLoader) toSinaCode(symbol string) string {
	switch {
	case strings.HasPrefix(symbol, "6"):
		return "sh" + symbol
	case strings.HasPrefix(symbol, "0") || strings.HasPrefix(symbol, "3"):
		return "sz" + symbol
	case strings.HasPrefix(symbol, "4") || strings.HasPrefix(symbol, "8") || strings.HasPrefix(symbol, "9"):
		return "bj" + symbol
	default:
		return "sh" + symbol
	}
}

// parseResponse extracts OHLCV fields from a Sina quote response line.
// Format: var hq_str_XXcode="name,open,prev_close,price,high,low,...,volume,...,date,time,..."
func (s *SinaLoader) parseResponse(body, symbol string) (*commonv1.Bar, error) {
	// Extract content between first and last double-quote
	start := strings.IndexByte(body, '"')
	if start < 0 {
		return nil, fmt.Errorf("sina parse: no opening quote")
	}
	end := strings.LastIndexByte(body, '"')
	if end <= start {
		return nil, fmt.Errorf("sina parse: no closing quote")
	}
	content := body[start+1 : end]
	if content == "" {
		return nil, fmt.Errorf("sina parse: empty quote (symbol may not exist)")
	}

	fields := strings.Split(content, ",")
	if len(fields) < 31 {
		return nil, fmt.Errorf("sina parse: expected >=31 fields, got %d", len(fields))
	}

	open, _ := strconv.ParseFloat(fields[1], 64)
	price, _ := strconv.ParseFloat(fields[3], 64) // current price → Close
	high, _ := strconv.ParseFloat(fields[4], 64)
	low, _ := strconv.ParseFloat(fields[5], 64)
	volume, _ := strconv.ParseInt(fields[8], 10, 64)

	ts, err := time.Parse("2006-01-02", fields[30])
	if err != nil {
		ts = time.Now()
	}

	return &commonv1.Bar{
		Symbol:    symbol,
		Open:      open,
		High:      high,
		Low:       low,
		Close:     price,
		Volume:    volume,
		Timestamp: ts.UnixMilli(),
		Frequency: "1d",
	}, nil
}
