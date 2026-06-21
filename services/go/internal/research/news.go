package research

import (
	"context"
	"encoding/json"
	"fmt"
	"time"
)

// NewsArticle represents a single news article headline with metadata.
type NewsArticle struct {
	Title     string  `json:"title"`
	Source    string  `json:"source"`
	URL       string  `json:"url"`
	Sentiment float64 `json:"sentiment"` // -1 to +1
	Timestamp string  `json:"timestamp"` // RFC3339
}

// NewsService provides multi-source news aggregation with sentiment analysis
// for A-share market research. It follows the same cache-first -> mock fallback
// pattern as FinancialsService and NorthboundService.
type NewsService struct {
	name    string
	adapter interface{} // *NewsAdapter or nil (future real API)
	repo    *Repo
}

// NewNewsService creates a new NewsService. The adapter parameter is reserved
// for future real news API integration and may be nil.
func NewNewsService(repo *Repo, adapter interface{}) *NewsService {
	return &NewsService{
		name:    "news",
		repo:    repo,
		adapter: adapter,
	}
}

// Name returns the service identifier.
func (s *NewsService) Name() string { return s.name }

// Analyze returns aggregated news and sentiment for the given symbol.
//
// The returned map contains:
//   - "recent_articles"   — []map[string]any, each with: title, source, url,
//     sentiment, timestamp
//   - "overall_sentiment" — float64, -1 to +1
//   - "sentiment_change"  — float64, change from previous period
//   - "key_topics"        — []string, 3-5 keywords
//   - "source_count"      — int, number of unique sources
//
// Cache-first: cached DataPoints are loaded if available and fresh.
// Otherwise mock data is generated, cached, and returned.
func (s *NewsService) Analyze(ctx context.Context, symbol string, params map[string]any) (map[string]any, error) {
	// 1. Cache-first
	if s.repo != nil {
		cached, _ := s.repo.GetCategory(symbol, "news")
		if len(cached) > 0 {
			return s.cachedResult(cached), nil
		}
	}

	// 2. Adapter — deferred (future real news API integration)
	if s.adapter != nil {
		// Future: call adapter.FetchNews(ctx, symbol)
	}

	// 3. Mock fallback
	mock := s.mockNews(symbol)

	// Persist to cache
	if s.repo != nil {
		_ = s.repo.Save(&DataPoint{
			Symbol:   symbol,
			Category: "news",
			Key:      "overall_sentiment",
			Value:    mock["overall_sentiment"].(float64),
			Date:     time.Now(),
		})
		_ = s.repo.Save(&DataPoint{
			Symbol:   symbol,
			Category: "news",
			Key:      "sentiment_change",
			Value:    mock["sentiment_change"].(float64),
			Date:     time.Now(),
		})
		_ = s.repo.Save(&DataPoint{
			Symbol:   symbol,
			Category: "news",
			Key:      "source_count",
			Value:    float64(mock["source_count"].(int)),
			Date:     time.Now(),
		})

		articles, _ := json.Marshal(mock["recent_articles"])
		_ = s.repo.Save(&DataPoint{
			Symbol:   symbol,
			Category: "news",
			Key:      "recent_articles",
			Date:     time.Now(),
			Metadata: map[string]string{"data": string(articles)},
		})

		topics, _ := json.Marshal(mock["key_topics"])
		_ = s.repo.Save(&DataPoint{
			Symbol:   symbol,
			Category: "news",
			Key:      "key_topics",
			Date:     time.Now(),
			Metadata: map[string]string{"data": string(topics)},
		})
	}

	return mock, nil
}

// History returns cached DataPoints for news analysis.
func (s *NewsService) History(ctx context.Context, symbol string, days int) ([]DataPoint, error) {
	return s.repo.GetCategory(symbol, "news")
}

// IsAvailable returns false (mock data is disabled, use NewsRealService instead).
func (s *NewsService) IsAvailable() bool {
	return false
}

// ---------- private helpers ----------


// clampSentiment clamps a sentiment score to [lo, hi] range.
func clampSentiment(v, lo, hi float64) float64 {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

// mockNews generates deterministic pseudo-random news and sentiment data.
func (s *NewsService) mockNews(symbol string) map[string]any {
	now := time.Now()

	// Pre-defined article templates to give variety per symbol via hashFloat
		// Clamp to [-0.3, 0.3] then apply 0.1 base positive bias
		overallSentiment := clampSentiment(hashFloat(symbol, 0)*0.8, -0.3, 0.3) + 0.1

	articles := []map[string]any{
		{
			"title":      fmt.Sprintf("%s 业绩超预期，机构上调目标价", symbol),
			"source":     "证券时报",
			"url":        fmt.Sprintf("https://example.com/news/%s/001", symbol),
			"sentiment":  0.65 + hashFloat(symbol, 1)*0.3,
			"timestamp":  now.Add(-time.Duration(hashFloat(symbol, 2)*120) * time.Minute).Format(time.RFC3339),
		},
		{
			"title":      "北向资金今日净买入" + fmt.Sprintf("%.0f", 3+hashFloat(symbol, 3)*5) + "亿元",
			"source":     "财联社",
			"url":        fmt.Sprintf("https://example.com/news/%s/002", symbol),
			"sentiment":  0.4 + hashFloat(symbol, 4)*0.4,
			"timestamp":  now.Add(-time.Duration(2+hashFloat(symbol, 5)*3) * time.Hour).Format(time.RFC3339),
		},
		{
			"title":      "行业政策利好频出，" + fmt.Sprintf("%.0f", 8+hashFloat(symbol, 6)*4) + "只概念股涨停",
			"source":     "上海证券报",
			"url":        fmt.Sprintf("https://example.com/news/%s/003", symbol),
			"sentiment":  0.5 + hashFloat(symbol, 7)*0.5,
			"timestamp":  now.Add(-time.Duration(5+hashFloat(symbol, 8)*4) * time.Hour).Format(time.RFC3339),
		},
		{
			"title":      "券商策略会：下半年关注" + fmt.Sprintf("%.0f", 3+hashFloat(symbol, 9)*4) + "大主线",
			"source":     "中国证券报",
			"url":        fmt.Sprintf("https://example.com/news/%s/004", symbol),
			"sentiment":  0.3 + hashFloat(symbol, 10)*0.3,
			"timestamp":  now.Add(-time.Duration(10+hashFloat(symbol, 11)*6) * time.Hour).Format(time.RFC3339),
		},
		{
			"title":      "外资持续加仓A股，" + fmt.Sprintf("%.0f", hashFloat(symbol, 12)*100+50) + "亿元增量资金入场",
			"source":     "华尔街见闻",
			"url":        fmt.Sprintf("https://example.com/news/%s/005", symbol),
			"sentiment":  0.55 + hashFloat(symbol, 13)*0.35,
			"timestamp":  now.Add(-time.Duration(16+hashFloat(symbol, 14)*8) * time.Hour).Format(time.RFC3339),
		},
		{
			"title":      fmt.Sprintf("【深度研报】%s 估值处于历史低位，配置价值凸显", symbol),
			"source":     "天风证券",
			"url":        fmt.Sprintf("https://example.com/news/%s/006", symbol),
			"sentiment":  0.7 + hashFloat(symbol, 15)*0.2,
			"timestamp":  now.Add(-time.Duration(24+hashFloat(symbol, 16)*12) * time.Hour).Format(time.RFC3339),
		},
		{
			"title":      "市场情绪回暖，成交额突破万亿",
			"source":     "21世纪经济报道",
			"url":        fmt.Sprintf("https://example.com/news/%s/007", symbol),
			"sentiment":  0.45 + hashFloat(symbol, 17)*0.3,
			"timestamp":  now.Add(-time.Duration(30+hashFloat(symbol, 18)*10) * time.Hour).Format(time.RFC3339),
		},
	}

	// Compute overall sentiment as average of article sentiments
	keyTopics := []string{
		"北向资金",
		"业绩预增",
		"政策利好",
		"估值修复",
		"增量资金",
	}

	uniqueSources := map[string]bool{}
	for _, a := range articles {
		uniqueSources[a["source"].(string)] = true
	}

	return map[string]any{
		"recent_articles":   articles,
		"overall_sentiment": overallSentiment,
		"sentiment_change":  hashFloat(symbol, 19) * 0.15,
		"key_topics":        keyTopics,
		"source_count":      len(uniqueSources),
	}
}

// cachedResult reconstructs the API response from cached DataPoints.
func (s *NewsService) cachedResult(dps []DataPoint) map[string]any {
	result := map[string]any{
		"overall_sentiment": 0.0,
		"sentiment_change":  0.0,
		"source_count":      0,
		"recent_articles":   []map[string]any{},
		"key_topics":        []string{},
	}

	for _, dp := range dps {
		switch dp.Key {
		case "overall_sentiment":
			result["overall_sentiment"] = dp.Value
		case "sentiment_change":
			result["sentiment_change"] = dp.Value
		case "source_count":
			result["source_count"] = int(dp.Value)
		case "recent_articles":
			if dp.Metadata != nil {
				var articles []map[string]any
				if err := json.Unmarshal([]byte(dp.Metadata["data"]), &articles); err == nil {
					result["recent_articles"] = articles
				}
			}
		case "key_topics":
			if dp.Metadata != nil {
				var topics []string
				if err := json.Unmarshal([]byte(dp.Metadata["data"]), &topics); err == nil {
					result["key_topics"] = topics
				}
			}
		}
	}

	return result
}
