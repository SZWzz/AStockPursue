package research

import (
	"context"
	"encoding/json"
	"time"
)

// NorthboundService monitors northbound capital flows from Hong Kong into
// A-share stocks via Stock Connect (沪深港通北向资金). It follows the same
// cache-first -> mock fallback pattern as FinancialsService.
type NorthboundService struct {
	name    string
	adapter interface{} // *NorthboundAdapter or nil (future real API)
	repo    *Repo
}

// NewNorthboundService creates a new NorthboundService. The adapter parameter
// is reserved for future real API integration and may be nil.
func NewNorthboundService(repo *Repo, adapter interface{}) *NorthboundService {
	return &NorthboundService{
		name:    "northbound",
		repo:    repo,
		adapter: adapter,
	}
}

// Name returns the service identifier.
func (s *NorthboundService) Name() string { return s.name }

// Analyze returns northbound capital flow metrics for the given symbol (stock code).
//
// The returned map contains:
//   - "net_inflow_daily"     — float64, today's net inflow (CNY)
//   - "net_inflow_weekly"    — float64, weekly net inflow (CNY)
//   - "net_inflow_monthly"   — float64, monthly net inflow (CNY)
//   - "cumulative_net_buy"   — float64, cumulative net buy (CNY)
//   - "top10_active_stocks"  — []map[string]any, top-10 stocks by net buy value
//   - "sector_distribution"  — map[string]float64, sector -> net inflow
//
// Cache-first: cached DataPoints are loaded if available and fresh.
// Otherwise mock data is generated, cached, and returned.
func (s *NorthboundService) Analyze(ctx context.Context, symbol string, params map[string]any) (map[string]any, error) {
	// 1. Cache-first
	if s.repo != nil {
		cached, _ := s.repo.GetCategory(symbol, "northbound")
		if len(cached) > 0 {
			return s.cachedResult(cached), nil
		}
	}

	// 2. Adapter — deferred (future real API integration)
	if s.adapter != nil {
		// Future: call adapter.FetchNorthbound(ctx, symbol)
	}

	// 3. Mock fallback
	mock := s.mockNorthbound(symbol)

	// Persist to cache
	if s.repo != nil {
		metricKeys := []string{"net_inflow_daily", "net_inflow_weekly", "net_inflow_monthly", "cumulative_net_buy"}
		for _, k := range metricKeys {
			v, _ := mock[k].(float64)
			_ = s.repo.Save(&DataPoint{
				Symbol:   symbol,
				Category: "northbound",
				Key:      k,
				Value:    v,
				Date:     time.Now(),
			})
		}
		// Store top10 stocks as JSON in metadata
		if top10, ok := mock["top10_active_stocks"]; ok {
			top10JSON, _ := json.Marshal(top10)
			_ = s.repo.Save(&DataPoint{
				Symbol:   symbol,
				Category: "northbound",
				Key:      "top10_active_stocks",
				Date:     time.Now(),
				Metadata: map[string]string{"data": string(top10JSON)},
			})
		}
		// Store sector distribution as JSON in metadata
		if sectors, ok := mock["sector_distribution"]; ok {
			sectorsJSON, _ := json.Marshal(sectors)
			_ = s.repo.Save(&DataPoint{
				Symbol:   symbol,
				Category: "northbound",
				Key:      "sector_distribution",
				Date:     time.Now(),
				Metadata: map[string]string{"data": string(sectorsJSON)},
			})
		}
	}

	return mock, nil
}

// History returns cached DataPoints for northbound capital flow.
func (s *NorthboundService) History(ctx context.Context, symbol string, days int) ([]DataPoint, error) {
	return s.repo.GetCategory(symbol, "northbound")
}

// IsAvailable returns false (mock data is disabled).
func (s *NorthboundService) IsAvailable() bool {
	return false
}

// ---------- private helpers ----------

// mockNorthbound generates deterministic pseudo-random northbound flow data.
// Values are calibrated to realistic A-share northbound magnitudes (CNY).
func (s *NorthboundService) mockNorthbound(symbol string) map[string]any {
	// Top-10 stocks northbound capital typically flows into (blue chips)
	topStocks := []map[string]any{
		{"code": "600519.SH", "name": "贵州茅台", "name_en": "Kweichow Moutai", "net_buy": 1.52e9 + hashFloat(symbol, 0)*5e8},
		{"code": "000858.SZ", "name": "五粮液", "name_en": "Wuliangye", "net_buy": 8.93e8 + hashFloat(symbol, 1)*3e8},
		{"code": "600036.SH", "name": "招商银行", "name_en": "China Merchants Bank", "net_buy": 7.21e8 + hashFloat(symbol, 2)*2.5e8},
		{"code": "601318.SH", "name": "中国平安", "name_en": "Ping An Insurance", "net_buy": 6.87e8 + hashFloat(symbol, 3)*3e8},
		{"code": "000333.SZ", "name": "美的集团", "name_en": "Midea Group", "net_buy": 5.44e8 + hashFloat(symbol, 4)*2e8},
		{"code": "600900.SH", "name": "长江电力", "name_en": "Yangtze Power", "net_buy": 4.32e8 + hashFloat(symbol, 5)*1.5e8},
		{"code": "002415.SZ", "name": "海康威视", "name_en": "Hikvision", "net_buy": 3.95e8 + hashFloat(symbol, 6)*2e8},
		{"code": "601012.SH", "name": "隆基绿能", "name_en": "LONGi Green Energy", "net_buy": 3.18e8 + hashFloat(symbol, 7)*2.5e8},
		{"code": "600276.SH", "name": "恒瑞医药", "name_en": "Hengrui Medicine", "net_buy": 2.76e8 + hashFloat(symbol, 8)*1.8e8},
		{"code": "002304.SZ", "name": "洋河股份", "name_en": "Yanghe Brewery", "net_buy": 2.11e8 + hashFloat(symbol, 9)*1.2e8},
	}

	// Sector distribution for northbound capital
	sectorDist := map[string]float64{
		"食品饮料": 4.2e9 + hashFloat(symbol, 10)*1e9,
		"银行":   3.8e9 + hashFloat(symbol, 11)*8e8,
		"非银金融": 2.9e9 + hashFloat(symbol, 12)*7e8,
		"家用电器": 2.1e9 + hashFloat(symbol, 13)*5e8,
		"电力":   1.8e9 + hashFloat(symbol, 14)*4e8,
		"电子":   1.5e9 + hashFloat(symbol, 15)*5e8,
		"医药生物": 1.2e9 + hashFloat(symbol, 16)*3e8,
		"电力设备": 9.5e8 + hashFloat(symbol, 17)*4e8,
	}

	daily := 5.8e9 + hashFloat(symbol, 18)*3e9
	weekly := daily * (4.0 + hashFloat(symbol, 19)*1.5)
	monthly := daily * (18.0 + hashFloat(symbol, 20)*6)
	cumulative := 2.15e11 + hashFloat(symbol, 21)*5e10

	return map[string]any{
		"net_inflow_daily":    daily,
		"net_inflow_weekly":   weekly,
		"net_inflow_monthly":  monthly,
		"cumulative_net_buy": cumulative,
		"top10_active_stocks": topStocks,
		"sector_distribution": sectorDist,
	}
}

// cachedResult reconstructs the API response from cached DataPoints.
func (s *NorthboundService) cachedResult(dps []DataPoint) map[string]any {
	result := map[string]any{
		"net_inflow_daily":    0.0,
		"net_inflow_weekly":   0.0,
		"net_inflow_monthly":  0.0,
		"cumulative_net_buy": 0.0,
	}

	for _, dp := range dps {
		switch dp.Key {
		case "net_inflow_daily", "net_inflow_weekly", "net_inflow_monthly", "cumulative_net_buy":
			result[dp.Key] = dp.Value
		case "top10_active_stocks":
			if dp.Metadata != nil {
				var stocks []map[string]any
				if err := json.Unmarshal([]byte(dp.Metadata["data"]), &stocks); err == nil {
					result["top10_active_stocks"] = stocks
				}
			}
		case "sector_distribution":
			if dp.Metadata != nil {
				sectors := make(map[string]float64)
				if err := json.Unmarshal([]byte(dp.Metadata["data"]), &sectors); err == nil {
					result["sector_distribution"] = sectors
				}
			}
		}
	}

	// Ensure defaults for complex fields in case they weren't cached
	if _, ok := result["top10_active_stocks"]; !ok {
		result["top10_active_stocks"] = []map[string]any{}
	}
	if _, ok := result["sector_distribution"]; !ok {
		result["sector_distribution"] = map[string]float64{}
	}

	return result
}
