# Security & Stability Fixes Spec

> **Date**: 2026-06-23  
> **Status**: Approved  
> **Scope**: P0 CRITICAL (3) + P1 HIGH (6) issues from comprehensive audit

---

## P0-1: `factor_kb.py` `setdefault` Typo (Runtime Crash)

**File**: `services/python/src/factors/mining/factor_kb.py`  
**Lines**: 314, 738  
**Severity**: CRITICAL — `AttributeError` at runtime

### Root Cause
Python dict's method is `setdefault()`, not `setdefault()`. Two callsites using the typo.

### Fix
- Change `self._by_source_version.setdefault(...)` → `self._by_source_version.setdefault(...)`
- Change `kb._by_source_version.setdefault(...)` → `kb._by_source_version.setdefault(...)`
- Add unit test in `test_factor_kb.py` covering `_by_source_version` indexing path

### Verification
- Run `pytest tests/test_factor_kb.py -v`
- Confirm no `AttributeError` on the fixed paths

---

## P0-2: gRPC TLS No Certificate Verification

**Files**: `services/go/internal/engine/signal.go:64`, `services/go/internal/grpc/connmgr.go:198`  
**Severity**: CRITICAL — Man-in-the-middle attack vector, security theater

### Root Cause
`credentials.NewClientTLSFromCert(nil, "")` creates TLS config that skips server certificate verification, making the connection effectively plaintext while appearing secure.

### Fix

**signal.go** and **connmgr.go** both need the same change:

```go
// New helper: services/go/internal/grpc/tls.go
func loadTLSCredentials() (credentials.TransportCredentials, error) {
    caCertPath := os.Getenv("GRPC_CA_CERT")
    tlsRequired := os.Getenv("GRPC_TLS_REQUIRED") == "true"

    var cp *x509.CertPool
    if caCertPath != "" {
        pem, err := os.ReadFile(caCertPath)
        if err != nil {
            if tlsRequired {
                return nil, fmt.Errorf("GRPC_CA_CERT set but cannot read: %w", err)
            }
            return nil, fmt.Errorf("cannot read CA cert: %w", err)
        }
        cp = x509.NewCertPool()
        if !cp.AppendCertsFromPEM(pem) {
            return nil, fmt.Errorf("failed to parse CA certificate")
        }
    } else {
        var err error
        cp, err = x509.SystemCertPool()
        if err != nil {
            if tlsRequired {
                return nil, fmt.Errorf("cannot load system CA pool: %w", err)
            }
            return nil, fmt.Errorf("cannot load system CA pool: %w", err)
        }
    }

    return credentials.NewTLS(&tls.Config{
        RootCAs:    cp,
        MinVersion: tls.VersionTLS12,
    }), nil
}
```

- `signal.go:64`: Replace `NewClientTLSFromCert(nil, "")` with `loadTLSCredentials()`
- `connmgr.go:198`: Same replacement
- If TLS is enabled but credentials can't be loaded, return error (don't silently fall back)
- `GRPC_TLS_REQUIRED` env var: when true, any credential loading failure is fatal

### Verification
- Unit test: `TestLoadTLSCredentials` with mock CA cert
- Unit test: `TestTLSRequiredFailsWithoutCert`

---

## P0-3: FutuBroker TOCTOU Race Condition

**File**: `services/go/internal/broker/futu.go`  
**Lines**: 203-211  
**Severity**: CRITICAL — Concurrent goroutine connection leak, state corruption

### Root Cause
```go
b.mu.Lock()
if b.conn != nil {
    defer b.mu.Unlock()
    return nil
}
b.mu.Unlock()        // <-- lock released
return b.reconnect() // <-- race window: another goroutine enters
```

Two goroutines can both see `conn == nil` and both call `reconnect()`.

### Fix

Double-checked locking pattern:

```go
func (b *FutuBroker) ensureConnected() error {
    b.mu.Lock()
    if b.conn != nil {
        b.mu.Unlock()
        return nil
    }
    // Still nil under lock — hold lock through reconnect
    err := b.reconnectLocked()
    b.mu.Unlock()
    return err
}

func (b *FutuBroker) reconnectLocked() error {
    // caller holds b.mu
    // ... existing reconnect logic, without its own lock/unlock ...
}
```

Alternative: keep `reconnect()` unchanged, but hold the lock:

```go
func (b *FutuBroker) ensureConnected() error {
    b.mu.Lock()
    defer b.mu.Unlock()
    if b.conn != nil {
        return nil
    }
    return b.reconnect() // reconnect must NOT try to lock b.mu internally
}
```

### Verification
- Existing tests in `futu_test.go` must still pass
- Optional: concurrent stress test with `-race` flag

---

## P1-1: WebSocket Allows Any Origin

**File**: `services/go/internal/api/ws.go`  
**Lines**: 15  
**Severity**: HIGH — CSRF/WebSocket hijacking vector

### Root Cause
`CheckOrigin: func(r *http.Request) bool { return true }` permits cross-origin WebSocket connections from any domain.

### Fix
```go
var wsAllowedOrigins map[string]bool

func init() {
    raw := os.Getenv("WS_ALLOWED_ORIGINS")
    if raw == "" {
        raw = "http://localhost:5899,http://127.0.0.1:5899"
    }
    wsAllowedOrigins = make(map[string]bool)
    for _, origin := range strings.Split(raw, ",") {
        wsAllowedOrigins[strings.TrimSpace(origin)] = true
    }
}

// In NewHub():
upgrader: websocket.Upgrader{
    CheckOrigin: func(r *http.Request) bool {
        origin := r.Header.Get("Origin")
        return wsAllowedOrigins[origin]
    },
}
```

### Verification
- Unit test: `TestWebSocketOriginCheck` — valid origin passes, invalid origin rejected

---

## P1-2: ParseFloat Error Silently Swallowed

**Files**: `services/go/internal/broker/binance.go`, `services/go/internal/broker/okx.go`  
**Severity**: HIGH — Silent data corruption when API returns unexpected format

### Root Cause
`qty, _ := strconv.ParseFloat(bp.PositionAmt, 64)` — errors ignored, value defaults to 0 silently.

### Fix

Add helper in `services/go/internal/broker/helpers.go`:

```go
func mustParseFloat(s string) (float64, error) {
    s = strings.TrimSpace(s)
    if s == "" {
        return 0, fmt.Errorf("empty string")
    }
    v, err := strconv.ParseFloat(s, 64)
    if err != nil {
        return 0, fmt.Errorf("parse float %q: %w", s, err)
    }
    return v, nil
}
```

Replace all `_, _ = strconv.ParseFloat(...)` with `mustParseFloat(...)` and propagate errors. In binance.go (~6 occurrences) and okx.go (~6 occurrences).

### Verification
- Existing broker tests continue to pass
- Unit test: `TestMustParseFloat` — valid input, empty string, invalid string

---

## P1-3: Hardcoded Admin Credentials

**File**: `services/go/internal/api/handler/auth.go`  
**Lines**: 144  
**Severity**: HIGH — Default admin password in source code

### Root Cause
```go
users: map[string]*userRecord{
    "admin": {Username: "admin", Password: hashPassword("admin123")},
},
```

### Fix

Remove the hardcoded admin user from the in-memory default. Add:

```go
func initAdminUser(store UserStore) error {
    adminPass := os.Getenv("ADMIN_PASSWORD")
    if adminPass == "" {
        log.Println("ADMIN_PASSWORD not set — no default admin created")
        return nil
    }
    // Only create if admin doesn't already exist
    if _, err := store.GetUser("admin"); err == nil {
        return nil // admin already exists
    }
    return store.CreateUser("admin", adminPass)
}
```

Call `initAdminUser` during server startup. Add an admin setup endpoint:

```
POST /api/admin/setup
Body: {"password": "..."}
→ Creates admin user if none exists
→ Returns 409 Conflict if admin already exists
```

### Verification
- Unit test: `TestAdminSetupEndpoint` — success, duplicate rejection

---

## P1-4: API Returns Decrypted API Keys in Plaintext

**File**: `services/go/internal/api/handler/broker.go`  
**Lines**: 242  
**Severity**: HIGH — Any authenticated user can exfiltrate broker API keys

### Root Cause
`GetCredentials` endpoint returns full decrypted API key in response.

### Fix

Two-level access:

1. **`GET /api/broker/credentials`** — returns masked keys only:
   ```json
   {"api_key": "sk-****b1c2", "api_secret": "****", "broker": "binance"}
   ```

2. **`POST /api/broker/credentials/reveal`** — requires password re-verification:
   ```
   Body: {"current_password": "..."}
   → Returns full decrypted credentials
   → Logs audit event (who, when, which broker)
   ```

Masking helper:
```go
func maskString(s string) string {
    if len(s) <= 8 {
        return "****"
    }
    return s[:3] + "-****" + s[len(s)-4:]
}
```

### Verification
- Unit test: `TestCredentialsMasking` — masked endpoint returns masked, reveal endpoint requires password
- Unit test: `TestRevealCredentialsAuditLog`

---

## P1-5: LLM Miner eval() Sandbox Bypass

**File**: `services/python/src/factors/mining/llm_miner.py`  
**Lines**: 435  
**Severity**: HIGH — `pd.read_csv("/etc/passwd")` executable inside sandbox

### Root Cause
`eval(formula, {"__builtins__": {}}, safe_locals)` — `pd` in `safe_locals` exposes full pandas API including I/O methods.

### Fix

Create `SandboxPandas` wrapper class:

```python
class SandboxPandas:
    """Whitelist-only pandas proxy for LLM formula evaluation."""
    
    _ALLOWED_ATTRS = frozenset({
        'DataFrame', 'Series', 'concat',
        'rolling', 'shift', 'rank', 'pct_change', 'diff',
        'corr', 'cov', 'std', 'mean', 'sum', 'min', 'max',
        'abs', 'sqrt', 'log', 'exp', 'sign', 'clip', 'where',
        'replace', 'fillna', 'dropna', 'isna', 'notna',
        'ewm', 'cumsum', 'cumprod', 'cummin', 'cummax',
    })
    
    def __init__(self):
        self._pd = __import__('pandas')
    
    def __getattr__(self, name):
        if name not in self._ALLOWED_ATTRS:
            raise SandboxError(f"pandas.{name} is not allowed in formula sandbox")
        return getattr(self._pd, name)
```

Same for numpy: whitelist `SandboxNumpy` with mathematical functions only.

In `_sandbox_pre_run`:
```python
safe_locals = {
    'pd': SandboxPandas(),
    'np': SandboxNumpy(),
}
# Use restricted builtins: only True, False, None, basic types
safe_builtins = {'True': True, 'False': False, 'None': None, 'abs': abs, 'min': min, 'max': max}
eval(formula, {"__builtins__": safe_builtins}, safe_locals)
```

### Verification
- `test_sandbox.py` — extend existing test with I/O method rejection
- Test `pd.read_csv`, `pd.to_parquet`, `pd.DataFrame.to_csv` all raise `SandboxError`

---

## P1-6: TimescaleDB Hypertable on Standard PostgreSQL

**File**: `services/go/internal/db/timescale.go`  
**Severity**: HIGH — Application fails to start on standard PostgreSQL

### Root Cause
`SELECT create_hypertable('bars', 'timestamp', ...)` fails if TimescaleDB extension is not installed.

### Fix

```go
func (s *Store) ensureHypertable(ctx context.Context, tableName string) error {
    // Check if TimescaleDB is available
    var hasTimescaleDB bool
    err := s.pool.QueryRow(ctx,
        "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')",
    ).Scan(&hasTimescaleDB)
    if err != nil {
        return fmt.Errorf("check timescaledb extension: %w", err)
    }
    if !hasTimescaleDB {
        log.Printf("TimescaleDB not installed — %s will run as regular table", tableName)
        return nil
    }
    
    // TimescaleDB available — create hypertable
    _, err = s.pool.Exec(ctx, fmt.Sprintf(
        "SELECT create_hypertable('%s', 'timestamp', if_not_exists => TRUE)",
        tableName,
    ))
    if err != nil {
        log.Printf("create_hypertable for %s failed: %v — continuing with regular table", tableName, err)
        return nil // non-fatal
    }
    return nil
}
```

Call `ensureHypertable` instead of inline `create_hypertable` in `buildBarsTableSQL` and `buildEquityCurvesSQL`.

### Verification
- Test with standard PostgreSQL: should create regular tables without error
- Test with TimescaleDB: should create hypertables

---

## Non-Scope (Explicitly Excluded)

| Issue | Reason |
|-------|--------|
| P2: Default DB credentials in config.go | Low priority, dev convenience |
| P2: OKX JSON string concatenation | Refactor, not a security fix |
| P2: Composite engine double-instantiation | Performance, not a bug |
| P2: Frontend `any` types, font config, tests | Separate frontend audit round |
| P2: GIL ThreadPoolExecutor, singleflight | Performance optimization round |
| P2: Agent/Swarm ReAct code duplication | Architecture refactor round |

## Verification Strategy

After all fixes:
1. Go: `cd services/go && go build ./... && go test ./... -race -count=1`
2. Python: `cd services/python && pytest tests/ -v`
3. gRPC TLS: manual verification with self-signed cert in dev
4. WebSocket: manual verification with cross-origin request
