package research

import (
	"context"
	"log"
	"time"
)

type FinancialsService struct {
	name    string
	adapter interface{} // FinancialsAdapter or nil
	repo    *Repo
}

func NewFinancialsService(repo *Repo, adapter interface{}) *FinancialsService {
	return &FinancialsService{name: "financials", repo: repo, adapter: adapter}
}

func (s *FinancialsService) Name() string { return s.name }

func (s *FinancialsService) Analyze(ctx context.Context, symbol string, params ResearchParams) (ResearchResult, error) {
	// 1. Check cache
	if s.repo != nil {
		cached, _ := s.repo.GetCategory(symbol, "financials")
		if len(cached) > 0 {
			result := make(ResearchResult)
			for _, dp := range cached {
				result[dp.Key] = dp.Value
			}
			return result, nil
		}
	}

	// 2. Try adapter (placeholder for future Sina/CNINFO integration)
	if s.adapter != nil {
		// Future: call adapter.FetchFinancials(ctx, symbol)
	}

	// 3. Mock fallback — reasonable A-share industry averages
	mock := s.mockFinancials(symbol)
	if s.repo != nil {
		for k, v := range mock {
			if err := s.repo.Save(&DataPoint{
				Symbol:   symbol,
				Category: "financials",
				Key:      k,
				Value:    v,
				Date:     time.Now(),
			}); err != nil {
				log.Printf("[research/financials] save error: %v", err)
			}
		}
	}
	result := make(map[string]any)
	for k, v := range mock {
		result[k] = v
	}
	return result, nil
}

func (s *FinancialsService) History(ctx context.Context, symbol string, days int) ([]DataPoint, error) {
	return s.repo.GetCategory(symbol, "financials")
}

func (s *FinancialsService) IsAvailable() bool {
	return false
}

func (s *FinancialsService) mockFinancials(symbol string) map[string]float64 {
	return map[string]float64{
		"revenue_yoy":        12.5 + hashFloat(symbol, 0)*5,
		"net_profit_yoy":     10.2 + hashFloat(symbol, 1)*8,
		"roe":                15.3 + hashFloat(symbol, 2)*5,
		"gross_margin":       35.0 + hashFloat(symbol, 3)*10,
		"debt_to_asset":      42.0 + hashFloat(symbol, 4)*15,
		"current_ratio":      1.8 + hashFloat(symbol, 5)*0.8,
		"eps":                0.85 + hashFloat(symbol, 6)*0.5,
		"pb_ratio":           2.5 + hashFloat(symbol, 7)*2,
		"pe_ratio":           18.0 + hashFloat(symbol, 8)*10,
		"operating_cashflow": 5.2e9 + hashFloat(symbol, 9)*2e9,
	}
}

// hashFloat generates a deterministic pseudo-random float from a string + seed.
func hashFloat(s string, seed int) float64 {
	var h uint64
	for _, c := range s {
		h = h*31 + uint64(c)
	}
	h += uint64(seed) * 2654435761
	return float64(h%100)/100.0 - 0.5
}
