# P4.5 + P4.6 Report - NorthboundService + NewsService

## Files Created

- `services/go/internal/research/northbound.go` — NorthboundService (P4.5)
- `services/go/internal/research/news.go` — NewsService (P4.6)

## Summary

Both services implement the `research.Service` interface (`Name`, `Analyze`, `History`, `IsAvailable`) following the exact same patterns established by `FinancialsService` and `GeopoliticsService`:

### NorthboundService (northbound.go)
- **Category key**: `"northbound"`
- **Analyze() returns**: `net_inflow_daily`, `net_inflow_weekly`, `net_inflow_monthly`, `cumulative_net_buy`, `top10_active_stocks` (list of 10 stocks with code/name/net_buy), `sector_distribution` (8 sectors with inflow values)
- Uses `hashFloat()` from `financials.go` for deterministic mock data
- Mock stocks include real A-share blue chips (600519.SH, 000858.SZ, etc.)
- Realistic magnitudes in CNY (billions)

### NewsService (news.go)
- **Category key**: `"news"`
- **Analyze() returns**: `recent_articles` (7 deterministic articles per symbol), `overall_sentiment` (-1 to +1, average of article sentiments), `sentiment_change`, `key_topics` (5 keywords), `source_count`
- Articles have varied titles, sources, sentiments (all positive-biased)
- Sources include: 证券时报, 财联社, 上海证券报, 中国证券报, 华尔街见闻, 天风证券, 21世纪经济报道
- **History()** returns cached DataPoints for the `"news"` category

### Verification
- `go build ./internal/research/...` — success
- `go vet ./internal/research/...` — no issues
- `go build ./...` — full project build success
- `go vet ./...` — full project vet, no issues

### CHANGELOG
Updated `CHANGELOG.md` with entries for both services under `[2026.6.21]`.
