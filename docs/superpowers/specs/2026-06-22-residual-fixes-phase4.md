# Phase 4: Residual Fixes — Spec & Plan

**Date**: 2026-06-22 | **Status**: Executing
**Scope**: 12 remaining Minor items from fullstack review, excluding 3 large feature items (Risk Dashboard, Trade Journal, JWT refresh — these need dedicated projects)

---

## Stream A: Frontend Quick Wins (6 items)

### A1: Google Fonts → next/font
**Files**: `frontend/app/layout.tsx`
- Replace inline `<link href="https://fonts.googleapis.com/...">` with `next/font/google` imports
- Keep Fira Sans (400/500/600) + Fira Code (400) only
- Remove unused font weights

### A2: WebSocket real-time quotes
**Files**: `frontend/lib/ws.ts`, `services/go/internal/api/ws.go`
- Go: wire up `TickerFeed()` function (exists but never called), push ticker data on `ticker` channel
- Frontend: subscribe to `ticker` channel in trading/market pages

### A3: Chart library consolidation → Recharts only
**Files**: `frontend/components/financial/`
- Keep Recharts (already used for Equity/Drawdown/Candlestick)
- Replace D3 usage in `CorrelationMatrix` with Recharts
- Remove echarts dependency if not deeply used
- Run `npx tsc --noEmit` after changes

### A4: Editor consolidation → CodeMirror only
**Files**: `frontend/package.json`, `frontend/components/financial/CodeMirror.tsx`
- Keep CodeMirror (already used in financial components + agent page)
- Remove `@monaco-editor/react` dependency
- Ensure all editor users point to CodeMirror

### A5: Zustand persist middleware versioning
**Files**: `frontend/stores/uiStore.ts`, `frontend/stores/themeStore.ts`
- Add `version: 1` and `migrate` to persist middleware
- Safe migration that keeps existing stored state

### A6: BFF rate limiting
**Files**: `frontend/lib/bff-proxy.ts`
- Add simple in-memory rate limiter: max 60 requests per minute per IP
- Return 429 when exceeded

---

## Stream B: Backend Cleanup (6 items)

### B1: Python mcp loader caching
**Files**: `services/python/mcp_server.py` ~line 567
- Cache loader instances by source name in a dict
- Reuse on subsequent calls instead of `loader_cls()` per call

### B2: Python DB retry deduplication
**Files**: `services/python/src/db/pool.py`, `services/python/src/db/async_pool.py`
- Extract shared retry+health check logic into `_acquire_with_retry()` in pool.py
- Both sync and async pool call the same function

### B3: Python sandbox except narrowing
**Files**: `services/python/src/security/sandbox.py` ~line 105
- Replace bare `except ValueError: pass` with explicit `except (ValueError, OSError)` where signal.signal fails in non-main thread
- Add comment explaining why

### B4: Python eval() context hardening
**Files**: `services/python/src/tools/quant_research_tools.py` ~line 104
- Whitelist only the specific pd/np functions needed (not entire modules)
- Or add comment documenting why full pd/np exposure is safe (ast.parse mode="eval" + no builtins)

### B5: Python token estimation for Chinese
**Files**: `services/python/src/agent/loop.py` ~line 93
- Replace `len(json.dumps(messages)) // 4` with more accurate: count ASCII chars as ~0.25 tokens, CJK chars as ~1.5 tokens
- Simple heuristic: `sum(1.5 if ord(c) > 0x4E00 else 0.25 for c in text)`

### B6: Go Futu reconnect lock + create_hypertable
**Files**: `services/go/internal/broker/futu.go` ~line 214
- Move `time.Sleep` outside the `mu.Lock()` block
- Unlock before sleep, re-lock after

**Files**: `services/go/internal/db/timescale.go` ~line 89
- Distinguish "not TimescaleDB" vs "other error" in create_hypertable failure
- Return specific error message

---

## Execution

Two parallel agents: Stream A (frontend, 6 items), Stream B (backend mixed, 6 items). No cross-dependencies.
