# Task 13 Report: protobuf Fields + Dynamic Slippage

## Changes Made

### 1. Protobuf Fields (`services/proto/common.proto`)

- **Bar message**: Added `double amount = 9` — turnover amount field
- **Position message**: Added `double unrealized_pnl = 7` and `double realized_pnl = 8` — separate unrealized/realized PnL tracking

### 2. Regenerated Go Code

- `buf generate` in `services/proto/` produced updated `services/go/internal/gen/common/v1/common.pb.go`
- New fields and getters: `Bar.Amount`/`GetAmount()`, `Position.UnrealizedPnl`/`GetUnrealizedPnl()`, `Position.RealizedPnl`/`GetRealizedPnl()`

### 3. Dynamic Slippage (`services/go/internal/engine/china_a.go`)

- Added `CalculateSlippage(symbol string, qty float64, isBuy bool) float64` — returns slippage rate based on daily amplitude
- Added `getDailyAmplitude(symbol string) float64` — stub returning 0 (placeholder for future data store integration)
- Updated `ApplySlippage` to call `CalculateSlippage` instead of hardcoded 1.001/0.999 multipliers

## Verification

- `go build ./cmd/server` — builds without errors
- `go test ./internal/engine/... -race -count=1` — all 129 tests pass, no race conditions
- Existing `TestChinaASlippageBuy`/`TestChinaASlippageSell` still pass (0.1% base rate matches old behavior)

## Files Modified

- `services/proto/common.proto` — added 3 proto fields
- `services/go/internal/gen/common/v1/common.pb.go` — regenerated
- `services/go/internal/engine/china_a.go` — dynamic slippage
