package research

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"time"
)

// eastMoneyNewsResponse mirrors the EastMoney /getNewsByKeyword JSON shape.
type eastMoneyNewsResponse struct {
	Success bool `json:"success"`
	Data    struct {
		List []struct {
			Title     string `json:"title"`
			Source    string `json:"source"`
			Url       string `json:"url"`
			Timestamp int64  `json:"timestamp"`
		} `json:"list"`
	} `json:"data"`
}

// NewsRealService fetches A-share news headlines from EastMoney's public API
// and returns aggregated news + sentiment. It implements the Service interface
// and replaces the mock-only NewsService.
type NewsRealService struct {
	httpClient *http.Client
	available  bool
	repo       *Repo
}

// NewNewsRealService creates a NewsRealService. If httpClient is nil a
// default client with a 10-second timeout is used. If repo is non-nil it is
// used for caching.
func NewNewsRealService(httpClient *http.Client, repo *Repo) *NewsRealService {
	if httpClient == nil {
		httpClient = &http.Client{Timeout: 10 * time.Second}
	}
	return &NewsRealService{
		httpClient: httpClient,
		available:  true,
		repo:       repo,
	}
}

// Name returns the service identifier.
func (s *NewsRealService) Name() string { return "news" }

// IsAvailable reports whether the real news source is reachable.
func (s *NewsRealService) IsAvailable() bool {
	return s.available
}

// Analyze fetches news from EastMoney, computes basic sentiment, and returns
// the aggregated result in the same shape as the mock NewsService.
func (s *NewsRealService) Analyze(ctx context.Context, symbol string, params ResearchParams) (ResearchResult, error) {
	// 1. Check cache
	if s.repo != nil {
		cached, err := s.repo.GetCategory(symbol, "news")
		if err != nil {
			log.Printf("research: cache read error for %s/news: %v", symbol, err)
		}
		if len(cached) > 0 {
			return cachedNewsResult(cached), nil
		}
	}

	// 2. Fetch real data from EastMoney
	articles, err := s.fetchFromEastMoney(ctx, symbol)
	if err != nil {
		s.available = false
		return nil, fmt.Errorf("news: %w", err)
	}

	// 3. Compute overall sentiment from the fetched articles
	var totalSentiment float64
	sourceSet := map[string]bool{}
	keyTopics := []string{}
	topicSet := map[string]bool{}
	topicKeywords := []string{"业绩", "政策", "资金", "估值", "行业"}

	for i, a := range articles {
		sentiment := simpleSentiment(a["title"].(string))
		articles[i]["sentiment"] = sentiment
		totalSentiment += sentiment
		sourceSet[a["source"].(string)] = true

		for _, kw := range topicKeywords {
			if containsWord(a["title"].(string), kw) && !topicSet[kw] {
				keyTopics = append(keyTopics, kw)
				topicSet[kw] = true
			}
		}
	}
	if len(articles) == 0 {
		return s.emptyResult(), nil
	}

	overallSentiment := totalSentiment / float64(len(articles))

	result := ResearchResult{
		"recent_articles":   articles,
		"overall_sentiment": overallSentiment,
		"sentiment_change":  0.0,
		"key_topics":        keyTopics,
		"source_count":      len(sourceSet),
	}

	// 4. Persist to cache
	if s.repo != nil {
		if err := s.repo.Save(&DataPoint{
			Symbol: symbol, Category: "news", Key: "overall_sentiment",
			Value: overallSentiment, Date: time.Now(),
		}); err != nil {
			log.Printf("[research/news_real] save error: %v", err)
		}
		if err := s.repo.Save(&DataPoint{
			Symbol: symbol, Category: "news", Key: "sentiment_change",
			Value: 0.0, Date: time.Now(),
		}); err != nil {
			log.Printf("[research/news_real] save error: %v", err)
		}
		if err := s.repo.Save(&DataPoint{
			Symbol: symbol, Category: "news", Key: "source_count",
			Value: float64(len(sourceSet)), Date: time.Now(),
		}); err != nil {
			log.Printf("[research/news_real] save error: %v", err)
		}
		if articlesJSON, err := json.Marshal(articles); err == nil {
			if err := s.repo.Save(&DataPoint{
				Symbol: symbol, Category: "news", Key: "recent_articles",
				Date: time.Now(), Metadata: map[string]string{"data": string(articlesJSON)},
			}); err != nil {
				log.Printf("[research/news_real] save error: %v", err)
			}
		}
		if topicsJSON, err := json.Marshal(keyTopics); err == nil {
			if err := s.repo.Save(&DataPoint{
				Symbol: symbol, Category: "news", Key: "key_topics",
				Date: time.Now(), Metadata: map[string]string{"data": string(topicsJSON)},
			}); err != nil {
				log.Printf("[research/news_real] save error: %v", err)
			}
		}
	}

	return result, nil
}

// History returns cached DataPoints for news analysis.
func (s *NewsRealService) History(ctx context.Context, symbol string, days int) ([]DataPoint, error) {
	if s.repo == nil {
		return nil, nil
	}
	return s.repo.GetCategory(symbol, "news")
}

// ---------- private helpers ----------

func (s *NewsRealService) fetchFromEastMoney(ctx context.Context, keyword string) ([]map[string]any, error) {
	queryURL := fmt.Sprintf(
		"https://np-listapi.eastmoney.com/comm/web/getNewsByKeyword?keyword=%s&client=web",
		url.QueryEscape(keyword),
	)
	req, err := http.NewRequestWithContext(ctx, "GET", queryURL, nil)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	req.Header.Set("User-Agent", "AStockPursue/0.1")
	req.Header.Set("Accept", "application/json")

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetch failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read body: %w", err)
	}

	var apiResp eastMoneyNewsResponse
	if err := json.Unmarshal(body, &apiResp); err != nil {
		return nil, fmt.Errorf("parse response: %w", err)
	}

	if !apiResp.Success {
		return nil, fmt.Errorf("eastmoney api returned success=false")
	}

	articles := make([]map[string]any, 0, len(apiResp.Data.List))
	for _, item := range apiResp.Data.List {
		ts := time.Unix(item.Timestamp, 0).Format(time.RFC3339)
		articles = append(articles, map[string]any{
			"title":     item.Title,
			"source":    item.Source,
			"url":       item.Url,
			"timestamp": ts,
		})
	}
	return articles, nil
}

func (s *NewsRealService) emptyResult() ResearchResult {
	return ResearchResult{
		"recent_articles":   []map[string]any{},
		"overall_sentiment": 0.0,
		"sentiment_change":  0.0,
		"key_topics":        []string{},
		"source_count":      0,
	}
}

// simpleSentiment computes a rough sentiment score (-1 to +1) from a title
// using keyword heuristics for Chinese financial news.
func simpleSentiment(title string) float64 {
	positiveWords := []string{"利好", "涨停", "增持", "业绩增长", "超预期", "买入", "加仓", "增资", "创新高"}
	negativeWords := []string{"利空", "跌停", "减持", "亏损", "下跌", "风险", "爆雷", "退市", "新低"}

	score := 0.0
	for _, w := range positiveWords {
		if containsWord(title, w) {
			score += 0.3
		}
	}
	for _, w := range negativeWords {
		if containsWord(title, w) {
			score -= 0.3
		}
	}
	if score > 1.0 {
		score = 1.0
	}
	if score < -1.0 {
		score = -1.0
	}
	return score
}

func containsWord(s, substr string) bool {
	return len(s) >= len(substr) && searchRunes([]rune(s), []rune(substr))
}

func searchRunes(s, substr []rune) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		match := true
		for j := 0; j < len(substr); j++ {
			if s[i+j] != substr[j] {
				match = false
				break
			}
		}
		if match {
			return true
		}
	}
	return false
}

// cachedNewsResult reconstructs the API response from cached DataPoints.
// (Same logic as the mock NewsService.cachedResult.)
func cachedNewsResult(dps []DataPoint) ResearchResult {
	result := ResearchResult{
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
