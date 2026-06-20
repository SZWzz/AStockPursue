# Additional A-Share Data Loaders Implementation Plan

## Context

The 8-source A-share data fallback chain requires 8 loaders, but only 2 are currently implemented (EastMoney @ priority 10, Tencent @ priority 5). This leaves a data availability gap — if EastMoney and Tencent both fail, there's no fallback. Adding 3 more loaders fills the chain: **Sina(1), Baidu(6), TwelveData(7)**.

The full chain after implementation:
`Sina(1) → Tencent(5) → Baidu(6) → TwelveData(7) → EastMoney(10)`

## Design

Follow the exact same pattern as `eastmoney.go` / `tencent.go`:
- `init()` self-registration with priority
- `Loader` interface: `Name()`, `IsAvailable()`, `FetchBars()`
- Tests using `httptest.NewServer` with static mock responses
- Each loader ~80-110 lines, each test ~35-50 lines

### New Files (6 total, all in `services/go/internal/market/loader/`)

| File | Loader | Priority | Type |
|------|--------|----------|------|
| `sina.go` | Sina Finance | 1 | Real-time text format |
| `sina_test.go` | Tests | — | httptest mock |
| `baidu.go` | Baidu Finance | 6 | Historical JSON |
| `baidu_test.go` | Tests | — | httptest mock |
| `twelvedata.go` | TwelveData | 7 | Historical JSON (string values) |
| `twelvedata_test.go` | Tests | — | httptest mock |

**No existing files modified** — loaders self-register via `init()`.

### Loader Details

#### 1. Sina Loader (priority 1) — Real-time only
- **URL**: `http://hq.sinajs.cn/list=sh600000` (comma-separated for batches)
- **Symbol conversion**: 6→`sh`, 0/3→`sz`, 4/8/9→`bj`
- **Required header**: `Referer: http://finance.sina.com.cn`
- **Response**: `var hq_str_sh600000="name,open,prev_close,price,high,low,...,volume,...,date,time,..."`
- **Fields**: Open=[1], Price(Close)=[3], High=[4], Low=[5], Volume=[8], Date=[30]
- **Historical**: Returns error if start/end non-zero (same pattern as Tencent)
- **Charset**: GBK — response body may need charset handling

#### 2. Baidu Finance Loader (priority 6) — Historical daily
- **URL**: `https://finance.pc22333.com/finance/stock/history?code=sh.600000&start_date=2026-01-01&end_date=2026-06-20`
- **Symbol conversion**: 6→`sh.`, 0/3→`sz.`, 4/8/9→`bj.`
- **Response JSON**: `{"status":0,"data":[{"date":"...","open":...,"close":...,"high":...,"low":...,"volume":...}]}`
- **No API key**, free access
- **Parsing**: JSON unmarshal into struct with float64/int64 fields

#### 3. TwelveData Loader (priority 7) — Historical multi-interval
- **URL**: `https://api.twelvedata.com/time_series?symbol=600000.SHH&interval=1day&apikey=KEY`
- **Symbol conversion**: 6→`.SHH`, 0/3→`.SHZ`, 4/8/9→`.BJS`
- **Response JSON**: `{"status":"ok","values":[{"datetime":"...","open":"...",...,"volume":"..."}]}`
- **All values are strings** — must parse with `strconv.ParseFloat`/`ParseInt`
- **API key**: Optional (env `TWELVEDATA_API_KEY`), lower rate limit without it
- **Rate limits**: ~8 req/min without key, returns 429 when exceeded → return error (store falls through)

### Symbol Conversion Summary

| Prefix | Exchange | Sina | Baidu | TwelveData |
|--------|----------|------|-------|------------|
| 6 | Shanghai | `sh` | `sh.` | `.SHH` |
| 0/3 | Shenzhen | `sz` | `sz.` | `.SHZ` |
| 4/8/9 | Beijing | `bj` | `bj.` | `.BJS` |

### Test Strategy

Each test file:
1. Creates `httptest.NewServer` with static mock response
2. Injects test server URL as `baseURL`
3. Verifies: `Name()`, `IsAvailable()`, `FetchBars()` result count, field values

## Task Breakdown

| Step | Task | Estimated Lines |
|------|------|-----------------|
| 1 | Create `sina.go` — HTTP text format real-time loader | ~90 |
| 2 | Create `sina_test.go` — mock Sina response | ~45 |
| 3 | Create `baidu.go` — JSON historical loader | ~100 |
| 4 | Create `baidu_test.go` — mock Baidu response | ~45 |
| 5 | Create `twelvedata.go` — JSON string-value historical loader | ~110 |
| 6 | Create `twelvedata_test.go` — mock TwelveData response | ~45 |
| 7 | Run `go test ./internal/market/loader/...` to verify all 3 loaders pass | — |
| 8 | Run `go test ./...` to verify full integration (168 existing tests still pass) | — |

## Verification

```bash
# Unit tests for new loaders
cd services/go
go test ./internal/market/loader/ -v -count=1 -run "TestSina|TestBaidu|TestTwelveData"

# Full test suite
go test ./... -count=1 -short

# Build check
go build ./...
```

Expected: all new loader tests PASS; all 168 existing tests continue to PASS.
