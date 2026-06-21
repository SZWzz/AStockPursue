package research

import (
	"context"
	"fmt"
	"math/rand"
	"sort"
	"strconv"
	"time"
)

// GeopoliticsTopic defines a geopolitical risk topic tracked via GDELT.
type GeopoliticsTopic struct {
	ID               string   `json:"id"`
	Title            string   `json:"title"`
	TitleCN          string   `json:"title_cn"`
	GDELTQuery       string   `json:"gdelt_query"`
	AssociatedAssets []string `json:"associated_assets"`
}

// predefinedTopics are the 10 pre-configured geopolitical risk topics for GDELT tracking.
// Each includes Chinese and English names, a GDELT search query string, and associated
// assets likely affected by changes in that topic's risk profile.
var predefinedTopics = []GeopoliticsTopic{
	{
		ID:               "us_china_trade",
		Title:            "US-China Trade",
		TitleCN:          "中美贸易",
		GDELTQuery:       "United States China trade tariff",
		AssociatedAssets: []string{"600519.SH", "000858.SZ", "601318.SH"},
	},
	{
		ID:               "taiwan_strait",
		Title:            "Taiwan Strait",
		TitleCN:          "台海局势",
		GDELTQuery:       "Taiwan Strait cross-strait military",
		AssociatedAssets: []string{"002049.SZ", "600760.SH", "600893.SH"},
	},
	{
		ID:               "south_china_sea",
		Title:            "South China Sea",
		TitleCN:          "南海争端",
		GDELTQuery:       "South China Sea Spratly navigation",
		AssociatedAssets: []string{"600893.SH", "600685.SH", "601989.SH"},
	},
	{
		ID:               "russia_ukraine",
		Title:            "Russia-Ukraine Conflict",
		TitleCN:          "俄乌冲突",
		GDELTQuery:       "Russia Ukraine war sanctions",
		AssociatedAssets: []string{"600028.SH", "601857.SH", "600188.SH"},
	},
	{
		ID:               "middle_east",
		Title:            "Middle East",
		TitleCN:          "中东局势",
		GDELTQuery:       "Middle East Iran Israel OPEC",
		AssociatedAssets: []string{"601857.SH", "600028.SH", "600030.SH"},
	},
	{
		ID:               "energy_security",
		Title:            "Energy Security",
		TitleCN:          "能源安全",
		GDELTQuery:       "energy security oil gas supply",
		AssociatedAssets: []string{"600028.SH", "601857.SH", "600188.SH", "600795.SH"},
	},
	{
		ID:               "semiconductor_supply_chain",
		Title:            "Semiconductor Supply Chain",
		TitleCN:          "半导体供应链",
		GDELTQuery:       "semiconductor chip export restriction",
		AssociatedAssets: []string{"002049.SZ", "688981.SH", "600745.SH", "603986.SH"},
	},
	{
		ID:               "rare_earth",
		Title:            "Rare Earth",
		TitleCN:          "稀土",
		GDELTQuery:       "rare earth mineral export control",
		AssociatedAssets: []string{"600010.SH", "600111.SH", "600259.SH"},
	},
	{
		ID:               "global_inflation",
		Title:            "Global Inflation",
		TitleCN:          "全球通胀",
		GDELTQuery:       "inflation CPI central bank interest rate",
		AssociatedAssets: []string{"600036.SH", "601166.SH", "000001.SZ"},
	},
	{
		ID:               "emerging_market_debt",
		Title:            "Emerging Market Debt",
		TitleCN:          "新兴市场债务",
		GDELTQuery:       "emerging market debt sovereign default",
		AssociatedAssets: []string{"601318.SH", "600036.SH", "601398.SH"},
	},
}

// GeopoliticsService provides geopolitical risk analysis for 10 pre-configured
// GDELT-tracked topics. It uses a cache-first strategy with mock fallback;
// real GDELT API integration is deferred to P6.
type GeopoliticsService struct {
	name    string
	adapter interface{} // *GDELTAdapter or nil (P6)
	repo    *Repo
}

// NewGeopoliticsService creates a new GeopoliticsService. The adapter parameter
// is reserved for future GDELT API integration and may be nil.
func NewGeopoliticsService(repo *Repo, adapter interface{}) *GeopoliticsService {
	return &GeopoliticsService{
		name:    "geopolitics",
		repo:    repo,
		adapter: adapter,
	}
}

// Name returns the service identifier.
func (s *GeopoliticsService) Name() string { return s.name }

// Analyze returns risk assessments for all 10 pre-configured topics.
//
// The returned map contains:
//   - "topics" — []map[string]any, each with keys: topic_id, title, title_cn,
//     risk_level, tone, tone_change, vol_change, associated_assets
//   - "updated_at" — RFC3339 timestamp string
//
// Cache-first: cached DataPoints are loaded if available and fresh.
// Otherwise mock data is generated, cached, and returned.
// The symbol and params arguments are accepted for interface compatibility;
// geopolitics analysis is global (symbol is ignored).
func (s *GeopoliticsService) Analyze(ctx context.Context, symbol string, params map[string]any) (map[string]any, error) {
	// 1. Cache-first: try loading cached assessments
	if s.repo != nil {
		cached, _ := s.repo.GetCategory("", "geopolitics")
		if len(cached) > 0 {
			return s.cachedResult(cached), nil
		}
	}

	// 2. Adapter — deferred to Phase 6 (GDELT real API integration)
	if s.adapter != nil {
		// Future: call adapter.FetchGeopolitics(ctx)
	}

	// 3. Mock fallback
	result := s.mockAssessments()

	// Persist mock data to cache
	if s.repo != nil {
		for _, topic := range predefinedTopics {
			a := result[topic.ID]
			s.repo.Save(&DataPoint{
				Symbol:   "",
				Category: "geopolitics",
				Key:      topic.ID,
				Value:    a.RiskScore,
				Date:     time.Now(),
				Metadata: map[string]string{
					"risk_level":  a.RiskLevel,
					"tone":        fmt.Sprintf("%.2f", a.Tone),
					"tone_change": fmt.Sprintf("%.2f", a.ToneChange),
					"vol_change":  fmt.Sprintf("%.2f", a.VolChange),
					"title":       topic.Title,
					"title_cn":    topic.TitleCN,
				},
			})
		}
	}

	return s.buildResponse(result), nil
}

// History returns cached DataPoints for geopolitics assessments.
func (s *GeopoliticsService) History(ctx context.Context, symbol string, days int) ([]DataPoint, error) {
	return s.repo.GetCategory("", "geopolitics")
}

// IsAvailable always returns true because the mock fallback is always ready.
func (s *GeopoliticsService) IsAvailable(ctx context.Context) bool {
	return true
}

// ---------- private helpers ----------

// assessment holds the computed risk values for a single topic.
type assessment struct {
	RiskLevel  string  // "high", "medium", "low"
	Tone       float64 // -10 to +10
	ToneChange float64
	VolChange  float64
	RiskScore  float64 // composite 0-10 used for caching
}

// mockAssessments generates deterministic pseudo-random assessments for all topics.
// It uses the topic ID as a seed so results are stable for the same topic.
func (s *GeopoliticsService) mockAssessments() map[string]assessment {
	assessments := make(map[string]assessment, len(predefinedTopics))
	for i, topic := range predefinedTopics {
		rng := rand.New(rand.NewSource(int64(i + 1)))

		tone := rng.Float64()*20 - 10                                    // -10 to +10
		toneChange := rng.Float64()*6 - 3                                 // -3 to +3
		volChange := rng.Float64()*20 - 10                                // -10% to +10%
		riskScore := (tone+10)/20*10 + volChange/10 + toneChange/3        // composite 0-10
		if riskScore < 0 {
			riskScore = 0
		}
		if riskScore > 10 {
			riskScore = 10
		}

		var riskLevel string
		switch {
		case riskScore >= 6:
			riskLevel = "high"
		case riskScore >= 3:
			riskLevel = "medium"
		default:
			riskLevel = "low"
		}

		assessments[topic.ID] = assessment{
			RiskLevel:  riskLevel,
			Tone:       tone,
			ToneChange: toneChange,
			VolChange:  volChange,
			RiskScore:  riskScore,
		}
	}
	return assessments
}

// buildResponse converts the internal assessment map into the public API format.
func (s *GeopoliticsService) buildResponse(assessments map[string]assessment) map[string]any {
	var topics []map[string]any
	for _, topic := range predefinedTopics {
		a := assessments[topic.ID]
		topics = append(topics, map[string]any{
			"topic_id":          topic.ID,
			"title":             topic.Title,
			"title_cn":          topic.TitleCN,
			"risk_level":        a.RiskLevel,
			"tone":              a.Tone,
			"tone_change":       a.ToneChange,
			"vol_change":        a.VolChange,
			"associated_assets": topic.AssociatedAssets,
		})
	}
	// Stable sort so the response order matches the topic definition order.
	sort.Slice(topics, func(i, j int) bool {
		return topics[i]["topic_id"].(string) < topics[j]["topic_id"].(string)
	})
	return map[string]any{
		"topics":     topics,
		"updated_at": time.Now().Format(time.RFC3339),
	}
}

// cachedResult reconstructs the API response from cached DataPoints.
func (s *GeopoliticsService) cachedResult(dps []DataPoint) map[string]any {
	topicsByID := make(map[string]map[string]any)
	for _, dp := range dps {
		topicID := dp.Key
		entry, ok := topicsByID[topicID]
		if !ok {
			meta := dp.Metadata
			if meta == nil {
				meta = make(map[string]string)
			}
			assetList := []string{}
			for _, t := range predefinedTopics {
				if t.ID == topicID {
					assetList = t.AssociatedAssets
					break
				}
			}
			tone, _ := strconv.ParseFloat(meta["tone"], 64)
			toneChange, _ := strconv.ParseFloat(meta["tone_change"], 64)
			volChange, _ := strconv.ParseFloat(meta["vol_change"], 64)

			entry = map[string]any{
				"topic_id":          topicID,
				"title":             meta["title"],
				"title_cn":          meta["title_cn"],
				"risk_level":        meta["risk_level"],
				"tone":              tone,
				"tone_change":       toneChange,
				"vol_change":        volChange,
				"associated_assets": assetList,
			}
			topicsByID[topicID] = entry
		}
	}
	topics := make([]map[string]any, 0, len(predefinedTopics))
	for _, t := range predefinedTopics {
		if entry, ok := topicsByID[t.ID]; ok {
			topics = append(topics, entry)
		}
	}
	return map[string]any{
		"topics":     topics,
		"updated_at": time.Now().Format(time.RFC3339),
	}
}

// dataPointsToResult is an alias of cachedResult for consistent naming.
func (s *GeopoliticsService) dataPointsToResult(dps []DataPoint) map[string]any {
	return s.cachedResult(dps)
}
