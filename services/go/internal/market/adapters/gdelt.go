package adapters

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"net/url"
	"sort"
	"sync"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	"github.com/astockpursue/go-core/internal/market"
)

// ---------------------------------------------------------------------------
// GeopoliticsAdapter – extended interface for geopolitical data sources
// ---------------------------------------------------------------------------

// GeopoliticsAdapter extends the market.Adapter interface with methods
// specific to geopolitical event monitoring. Implementations provide
// article-volume and average-tone time series for named topics.
type GeopoliticsAdapter interface {
	market.Adapter

	// FetchTopicVolume returns daily article-count time series for a topic.
	// The topic parameter should match one of the pre-configured topic names
	// returned by Topics().
	FetchTopicVolume(ctx context.Context, topic string, start, end time.Time) ([]VolumePoint, error)

	// FetchTopicTone returns daily average-tone time series for a topic.
	// Tone values range from -10 (extremely negative) to +10 (extremely positive).
	FetchTopicTone(ctx context.Context, topic string, start, end time.Time) ([]TonePoint, error)

	// Topics returns the list of pre-configured geopolitical topic queries.
	Topics() []TopicQuery
}

// VolumePoint represents a single article-count observation.
type VolumePoint struct {
	Date   time.Time
	Volume int64
}

// TonePoint represents a single average-tone observation.
type TonePoint struct {
	Date time.Time
	Tone float64
}

// TopicQuery holds a pre-configured geopolitical topic that can be queried
// against the GDELT API.
type TopicQuery struct {
	Name        string // canonical identifier, used as symbol in Fetch()
	Keyword     string // URL-escaped search phrase sent to the GDELT query parameter
	Description string // human-readable description of the topic
}

// ---------------------------------------------------------------------------
// GDELTAdapter – market.Adapter + GeopoliticsAdapter implementation
// ---------------------------------------------------------------------------

// GDELTAdapter fetches geopolitical event data from the GDELT Project API.
//
// GDELT (Global Database of Events, Language, and Tone) monitors print,
// broadcast, and web news in over 100 languages worldwide. This adapter
// exposes article volume and average tone as daily OHLCV-like bars, plus
// structured time series through the GeopoliticsAdapter extension.
//
// No API key is required. The GDELT service is free and unrestricted.
type GDELTAdapter struct {
	client  *http.Client
	baseURL string
	topics  []TopicQuery
	mu      sync.RWMutex
}

// gdeltTimelineResponse mirrors the GDELT v2/doc TimelineVol / ToneChart
// JSON response structure.
type gdeltTimelineResponse struct {
	Timeline []gdeltTimelineEntry `json:"timeline"`
}

type gdeltTimelineEntry struct {
	Date  string  `json:"date"`
	Value float64 `json:"value"`
}

// NewGDELTAdapter creates a new GDELT adapter initialised with 10 default
// pre-configured geopolitical topic queries covering US-China trade,
// Taiwan strait, South China Sea, North Korea, Russia-Ukraine, Middle East,
// global oil, Federal Reserve, EU, and Chinese economy.
func NewGDELTAdapter() *GDELTAdapter {
	return &GDELTAdapter{
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		baseURL: "https://api.gdeltproject.org/api/v2/doc/doc",
		topics:  defaultTopics(),
	}
}

// defaultTopics returns the 10 pre-configured geopolitical topic queries.
func defaultTopics() []TopicQuery {
	return []TopicQuery{
		{
			Name:        "us-china-trade",
			Keyword:     `"US-China trade"`,
			Description: "US-China trade relations and tariff announcements",
		},
		{
			Name:        "taiwan-strait",
			Keyword:     `"Taiwan strait"`,
			Description: "Taiwan strait military exercises and diplomatic tensions",
		},
		{
			Name:        "south-china-sea",
			Keyword:     `"South China Sea"`,
			Description: "South China Sea territorial disputes and naval activity",
		},
		{
			Name:        "north-korea",
			Keyword:     `"North Korea"`,
			Description: "North Korea missile tests, nuclear programme and diplomacy",
		},
		{
			Name:        "russia-ukraine",
			Keyword:     `Russia Ukraine war`,
			Description: "Russia-Ukraine war, sanctions and peace negotiations",
		},
		{
			Name:        "middle-east",
			Keyword:     `"Middle East" conflict`,
			Description: "Middle East conflicts, peace talks and diplomatic developments",
		},
		{
			Name:        "global-oil",
			Keyword:     `"crude oil" prices supply`,
			Description: "Global crude oil price drivers and supply-chain disruptions",
		},
		{
			Name:        "federal-reserve",
			Keyword:     `"Federal Reserve" interest rate`,
			Description: "US Federal Reserve monetary policy and FOMC rate decisions",
		},
		{
			Name:        "european-union",
			Keyword:     `"European Union" regulation economy`,
			Description: "EU economic, political and regulatory developments",
		},
		{
			Name:        "china-economy",
			Keyword:     `"Chinese economy" GDP growth`,
			Description: "Chinese macro-economic indicators and industrial policy",
		},
	}
}

// Name returns the adapter identifier.
func (g *GDELTAdapter) Name() string { return "gdelt" }

// Markets returns the single market identifier for geopolitical data.
func (g *GDELTAdapter) Markets() []string { return []string{"GEOPOLITICAL"} }

// RequiresAuth reports that the GDELT API is free and requires no key.
func (g *GDELTAdapter) RequiresAuth() bool { return false }

// IsAvailable performs a lightweight HEAD request against the GDELT API
// to verify network reachability and service health.
func (g *GDELTAdapter) IsAvailable(ctx context.Context) bool {
	req, err := http.NewRequestWithContext(ctx, http.MethodHead,
		"https://api.gdeltproject.org/api/v2/doc/doc?query=test&format=json&mode=TimelineVol", nil)
	if err != nil {
		return false
	}
	resp, err := g.client.Do(req)
	if err != nil {
		return false
	}
	resp.Body.Close()
	return resp.StatusCode == http.StatusOK
}

// Fetch retrieves OHLCV-like bars for a geopolitical topic.
//
// The Symbol field in req is matched against the pre-configured topic names
// (see Topics()). Each returned bar represents one day:
//   - Close  = average GDELT tone on [-10, +10] scale
//   - Open   = previous day's Close scaled slightly (simulated range)
//   - High   = max of Open and Close, expanded by 2 %
//   - Low    = min of Open and Close, contracted by 2 %
//   - Volume = article count for that day
//
// Both volume and tone are fetched concurrently from the GDELT API.
func (g *GDELTAdapter) Fetch(ctx context.Context, req market.FetchRequest) ([]*commonv1.Bar, error) {
	topic := g.resolveTopic(req.Symbol)
	if topic == nil {
		return nil, fmt.Errorf("gdelt: unknown topic %q; see Topics() for valid names", req.Symbol)
	}

	// Fetch volume and tone simultaneously.
	type timelineResult struct {
		entries []gdeltTimelineEntry
		err     error
	}

	volCh := make(chan timelineResult, 1)
	toneCh := make(chan timelineResult, 1)

	go func() {
		entries, err := g.queryTimeline(ctx, topic.Keyword, "TimelineVol", req.StartDate, req.EndDate)
		volCh <- timelineResult{entries, err}
	}()

	go func() {
		entries, err := g.queryTimeline(ctx, topic.Keyword, "ToneChart", req.StartDate, req.EndDate)
		toneCh <- timelineResult{entries, err}
	}()

	volResult := <-volCh
	if volResult.err != nil {
		return nil, fmt.Errorf("gdelt volume query: %w", volResult.err)
	}

	toneResult := <-toneCh
	if toneResult.err != nil {
		return nil, fmt.Errorf("gdelt tone query: %w", toneResult.err)
	}

	// Index tone data by date string for O(1) lookup.
	toneByDate := make(map[string]float64, len(toneResult.entries))
	for _, e := range toneResult.entries {
		toneByDate[e.Date] = e.Value
	}

	bars := make([]*commonv1.Bar, 0, len(volResult.entries))
	for _, v := range volResult.entries {
		ts, err := time.Parse("2006-01-02", v.Date)
		if err != nil {
			continue
		}

		tone, ok := toneByDate[v.Date]
		if !ok {
			continue // skip dates that have volume but no tone data
		}

		// Derive simulated OHLC from tone: GDELT reports daily average
		// tone so we build a narrow range around it to preserve the
		// OHLCV structural contract.
		close := math.Round(tone*100) / 100
		open := math.Round(tone*0.98*100) / 100

		var high, low float64
		if tone >= 0 {
			high = math.Round(math.Max(open, close)*1.02*100) / 100
			low = math.Round(math.Min(open, close)*0.98*100) / 100
		} else {
			// Negative tone: swap direction so high is the higher
			// (less negative) value.
			high = math.Round(math.Min(open, close)*0.98*100) / 100
			low = math.Round(math.Max(open, close)*1.02*100) / 100
		}

		bars = append(bars, &commonv1.Bar{
			Symbol:    req.Symbol,
			Open:      open,
			High:      high,
			Low:       low,
			Close:     close,
			Volume:    int64(v.Value),
			Timestamp: ts.UnixMilli(),
			Frequency: "1d",
		})
	}

	sort.Slice(bars, func(i, j int) bool {
		return bars[i].Timestamp < bars[j].Timestamp
	})

	return bars, nil
}

// FetchTopicVolume returns a daily article-count time series for one of the
// pre-configured topics.  Returns an error if the topic is not recognised.
func (g *GDELTAdapter) FetchTopicVolume(ctx context.Context, topic string, start, end time.Time) ([]VolumePoint, error) {
	tq := g.resolveTopic(topic)
	if tq == nil {
		return nil, fmt.Errorf("gdelt: unknown topic %q", topic)
	}

	entries, err := g.queryTimeline(ctx, tq.Keyword, "TimelineVol", start, end)
	if err != nil {
		return nil, err
	}

	points := make([]VolumePoint, 0, len(entries))
	for _, e := range entries {
		ts, err := time.Parse("2006-01-02", e.Date)
		if err != nil {
			continue
		}
		points = append(points, VolumePoint{Date: ts, Volume: int64(e.Value)})
	}
	return points, nil
}

// FetchTopicTone returns a daily average-tone time series for one of the
// pre-configured topics.  Tone values range from -10 to +10.
func (g *GDELTAdapter) FetchTopicTone(ctx context.Context, topic string, start, end time.Time) ([]TonePoint, error) {
	tq := g.resolveTopic(topic)
	if tq == nil {
		return nil, fmt.Errorf("gdelt: unknown topic %q", topic)
	}

	entries, err := g.queryTimeline(ctx, tq.Keyword, "ToneChart", start, end)
	if err != nil {
		return nil, err
	}

	points := make([]TonePoint, 0, len(entries))
	for _, e := range entries {
		ts, err := time.Parse("2006-01-02", e.Date)
		if err != nil {
			continue
		}
		points = append(points, TonePoint{Date: ts, Tone: e.Value})
	}
	return points, nil
}

// Topics returns a copy of the pre-configured topic list.
func (g *GDELTAdapter) Topics() []TopicQuery {
	g.mu.RLock()
	defer g.mu.RUnlock()
	result := make([]TopicQuery, len(g.topics))
	copy(result, g.topics)
	return result
}

// ---------------------------------------------------------------------------
// internal helpers
// ---------------------------------------------------------------------------

// resolveTopic matches a symbol against topic names and keywords.
func (g *GDELTAdapter) resolveTopic(symbol string) *TopicQuery {
	g.mu.RLock()
	defer g.mu.RUnlock()
	for i := range g.topics {
		if g.topics[i].Name == symbol {
			return &g.topics[i]
		}
	}
	return nil
}

// queryTimeline calls the GDELT v2/doc API with the given mode (TimelineVol
// or ToneChart) and returns the parsed timeline entries.
func (g *GDELTAdapter) queryTimeline(ctx context.Context, query, mode string, start, end time.Time) ([]gdeltTimelineEntry, error) {
	u := fmt.Sprintf("%s?query=%s&format=json&mode=%s&timelinemonths=%d",
		g.baseURL,
		url.QueryEscape(query),
		mode,
		monthsInRange(start, end),
	)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

	resp, err := g.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("http do: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("gdelt API returned HTTP %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read body: %w", err)
	}

	var result gdeltTimelineResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("json decode: %w", err)
	}

	return result.Timeline, nil
}

// monthsInRange returns the number of whole months between start and end,
// clamped to [1, 60] as required by the GDELT API.
func monthsInRange(start, end time.Time) int {
	months := int(end.Sub(start).Hours() / (24 * 30))
	if months < 1 {
		months = 1
	}
	if months > 60 {
		months = 60
	}
	return months
}
