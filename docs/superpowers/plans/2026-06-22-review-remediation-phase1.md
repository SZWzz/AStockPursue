# Code Review Remediation — Phase 1 Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 12 Critical and high-priority Important issues across Go Core, Python Research, and Next.js Frontend.

**Architecture:** Three independent streams with no cross-layer dependencies. Go stream creates crypto package, fixes auth/user isolation/pipeline/broker/date validation. Python stream fixes workflow engine race and gRPC return type. Frontend stream fixes PnL bug, dashboard zero-div, BFF proxy, settings save, and JWT types.

**Tech Stack:** Go 1.24 + Gin + pgx, Python 3.11+ + FastAPI + gRPC, Next.js 15 + React 19 + TypeScript

## Global Constraints

- All fixes must compile / pass type-check
- Must not break existing tests
- Include focused tests where feasible
- No new lint warnings
- AES-256-GCM for encryption, key from ENCRYPTION_KEY env var
- JWT user_id from `sub` claim, stored in gin context

---

## Stream A: Go Core (6 tasks)

### Task A1: Create crypto package

**Files:**
- Create: `services/go/internal/crypto/crypto.go`

**Interfaces:**
- Produces: `Encrypt(plaintext string) (string, error)`, `Decrypt(ciphertext string) (string, error)`, `GenerateKey() string`

- [ ] **Step 1: Create crypto/crypto.go with AES-256-GCM implementation**

```go
package crypto

import (
    "crypto/aes"
    "crypto/cipher"
    "crypto/rand"
    "encoding/base64"
    "errors"
    "fmt"
    "io"
)

var key []byte

func Init(encodedKey string) error {
    if encodedKey == "" {
        return errors.New("crypto: ENCRYPTION_KEY is required")
    }
    k, err := base64.StdEncoding.DecodeString(encodedKey)
    if err != nil {
        return fmt.Errorf("crypto: invalid ENCRYPTION_KEY: %w", err)
    }
    if len(k) != 32 {
        return errors.New("crypto: ENCRYPTION_KEY must be 32 bytes (base64 encoded)")
    }
    key = k
    return nil
}

func Encrypt(plaintext string) (string, error) {
    if key == nil {
        return "", errors.New("crypto: not initialized")
    }
    block, err := aes.NewCipher(key)
    if err != nil {
        return "", fmt.Errorf("crypto: %w", err)
    }
    gcm, err := cipher.NewGCM(block)
    if err != nil {
        return "", fmt.Errorf("crypto: %w", err)
    }
    nonce := make([]byte, gcm.NonceSize())
    if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
        return "", fmt.Errorf("crypto: %w", err)
    }
    ciphertext := gcm.Seal(nonce, nonce, []byte(plaintext), nil)
    return base64.StdEncoding.EncodeToString(ciphertext), nil
}

func Decrypt(encoded string) (string, error) {
    if key == nil {
        return "", errors.New("crypto: not initialized")
    }
    ciphertext, err := base64.StdEncoding.DecodeString(encoded)
    if err != nil {
        return "", fmt.Errorf("crypto: %w", err)
    }
    block, err := aes.NewCipher(key)
    if err != nil {
        return "", fmt.Errorf("crypto: %w", err)
    }
    gcm, err := cipher.NewGCM(block)
    if err != nil {
        return "", fmt.Errorf("crypto: %w", err)
    }
    nonceSize := gcm.NonceSize()
    if len(ciphertext) < nonceSize {
        return "", errors.New("crypto: ciphertext too short")
    }
    nonce, ciphertext := ciphertext[:nonceSize], ciphertext[nonceSize:]
    plaintext, err := gcm.Open(nil, nonce, ciphertext, nil)
    if err != nil {
        return "", fmt.Errorf("crypto: decryption failed: %w", err)
    }
    return string(plaintext), nil
}

func GenerateKey() string {
    k := make([]byte, 32)
    if _, err := rand.Read(k); err != nil {
        panic("crypto: failed to generate key: " + err.Error())
    }
    return base64.StdEncoding.EncodeToString(k)
}
```

- [ ] **Step 2: Add test file**

Create `services/go/internal/crypto/crypto_test.go`:

```go
package crypto

import (
    "testing"
)

func TestEncryptDecryptRoundtrip(t *testing.T) {
    key := GenerateKey()
    if err := Init(key); err != nil {
        t.Fatalf("Init failed: %v", err)
    }
    plaintext := "my-super-secret-api-key-12345"
    cipher, err := Encrypt(plaintext)
    if err != nil {
        t.Fatalf("Encrypt failed: %v", err)
    }
    if cipher == "" || cipher == plaintext {
        t.Fatal("Encrypt should produce different output from input")
    }
    decrypted, err := Decrypt(cipher)
    if err != nil {
        t.Fatalf("Decrypt failed: %v", err)
    }
    if decrypted != plaintext {
        t.Fatalf("Roundtrip failed: got %q, want %q", decrypted, plaintext)
    }
}

func TestEncryptWithoutInit(t *testing.T) {
    key = nil
    _, err := Encrypt("test")
    if err == nil {
        t.Fatal("Expected error when not initialized")
    }
}

func TestInitInvalidKey(t *testing.T) {
    if err := Init("not-valid-base64!!"); err == nil {
        t.Fatal("Expected error for invalid base64 key")
    }
    if err := Init("dG9vLXNob3J0"); err == nil {
        t.Fatal("Expected error for short key")
    }
}
```

- [ ] **Step 3: Run tests**

```bash
cd services/go && go test ./internal/crypto/ -v
```

Expected: all 3 tests PASS

- [ ] **Step 4: Commit**

```bash
git add services/go/internal/crypto/
git commit -m "feat: add AES-256-GCM crypto package for secret encryption"
```

---

### Task A2: Initialize crypto and add ENCRYPTION_KEY to config

**Files:**
- Modify: `services/go/internal/config/config.go`
- Modify: `services/go/cmd/server/main.go` (startup sequence)

- [ ] **Step 1: Add ENCRYPTION_KEY to config.go**

In `config.go`, add to the Config struct and Load function:

```go
type Config struct {
    // ... existing fields ...
    EncryptionKey string
}

func Load() *Config {
    cfg := &Config{
        // ... existing defaults ...
        EncryptionKey: os.Getenv("ENCRYPTION_KEY"),
    }
    if cfg.EncryptionKey == "" {
        log.Fatal("ENCRYPTION_KEY environment variable is required")
    }
    return cfg
}
```

- [ ] **Step 2: Initialize crypto in main.go**

In `cmd/server/main.go`, in the startup sequence after config load:

```go
if err := crypto.Init(cfg.EncryptionKey); err != nil {
    log.Fatalf("Failed to initialize crypto: %v", err)
}
```

- [ ] **Step 3: Run go build**

```bash
cd services/go && go build ./cmd/server/
```

Expected: no compile errors

- [ ] **Step 4: Commit**

```bash
git add services/go/internal/config/config.go services/go/cmd/server/main.go
git commit -m "feat: add ENCRYPTION_KEY config and crypto initialization"
```

---

### Task A3: Encrypt broker API secrets

**Files:**
- Modify: `services/go/internal/api/handler/broker.go` (save and read functions)

- [ ] **Step 1: Replace sprintf JSON construction with structured + encrypted**

In `broker.go`, find the credentials save logic (~line 155). Replace:

```go
// OLD:
body := fmt.Sprintf(`{"broker_credentials":{"%s":{"api_key":"%s","api_secret":"%s"}}}`,
    req.BrokerID, req.APIKey, req.APISecret)
```

With:

```go
// NEW:
import "encoding/json"
import "github.com/astockpursue/go-core/internal/crypto"

encryptedSecret, err := crypto.Encrypt(req.APISecret)
if err != nil {
    c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to encrypt credentials"})
    return
}

credential := map[string]interface{}{
    "api_key":    req.APIKey,
    "api_secret": encryptedSecret,
}
brokerCreds := map[string]interface{}{
    req.BrokerID: credential,
}
settings := map[string]interface{}{
    "broker_credentials": brokerCreds,
}
body, _ := json.Marshal(settings)
```

- [ ] **Step 2: Fix the read path to decrypt**

In the broker credentials read function, after `json.Unmarshal`:

```go
if creds, ok := settings["broker_credentials"].(map[string]interface{}); ok {
    for brokerID, v := range creds {
        if cred, ok := v.(map[string]interface{}); ok {
            if encryptedSecret, ok := cred["api_secret"].(string); ok {
                decrypted, err := crypto.Decrypt(encryptedSecret)
                if err != nil {
                    // log and skip this broker if decryption fails
                    continue
                }
                cred["api_secret"] = decrypted
            }
        }
    }
}
```

- [ ] **Step 3: Run go build**

```bash
cd services/go && go build ./cmd/server/
```

Expected: no compile errors

- [ ] **Step 4: Commit**

```bash
git add services/go/internal/api/handler/broker.go
git commit -m "fix: encrypt broker API secrets with AES-256-GCM, use json.Marshal"
```

---

### Task A4: User isolation — extract user_id from JWT

**Files:**
- Modify: `services/go/internal/api/middleware/auth.go` (store user_id in context)
- Modify: `services/go/internal/api/handler/settings.go` (use JWT user_id)
- Modify: `services/go/internal/api/handler/broker.go` (same)
- Audit: `services/go/internal/api/handler/scheduler.go`, `backtest.go`

- [ ] **Step 1: Store user_id in gin context during JWT auth**

In `middleware/auth.go`, in the JWT validation success path:

```go
// After successful JWT validation:
if claims, ok := token.Claims.(jwt.MapClaims); ok {
    if sub, ok := claims["sub"].(string); ok {
        // user_id is stored as string in JWT, convert to int for handlers
        if uid, err := strconv.Atoi(sub); err == nil {
            c.Set("user_id", uid)
        }
    }
}
```

- [ ] **Step 2: Rewrite getUserID in settings.go**

```go
func (h *SettingsHandler) getUserID(c *gin.Context) int {
    if uid, exists := c.Get("user_id"); exists {
        return uid.(int)
    }
    return 0 // Will cause 401 in calling handler
}
```

- [ ] **Step 3: Add user_id check in handlers that use it**

In `broker.go` and `settings.go`, add at the start of write handlers:

```go
userID := h.getUserID(c)
if userID == 0 {
    c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
    return
}
```

- [ ] **Step 4: Audit other handlers**

```bash
cd services/go && grep -rn "user_id.*=.*1\|userID.*=.*1" internal/api/handler/
```

Replace any remaining hardcoded `1` with `h.getUserID(c)`. Check:
- `scheduler.go` — job queries should filter by user_id
- `backtest.go` — backtest queries should filter by user_id

- [ ] **Step 5: Run go build**

```bash
cd services/go && go build ./cmd/server/
```

- [ ] **Step 6: Commit**

```bash
git add services/go/internal/api/middleware/auth.go services/go/internal/api/handler/settings.go services/go/internal/api/handler/broker.go services/go/internal/api/handler/scheduler.go services/go/internal/api/handler/backtest.go
git commit -m "fix: extract user_id from JWT claims, remove hardcoded user_id=1"
```

---

### Task A5: Auth default-deny

**Files:**
- Modify: `services/go/internal/api/middleware/auth.go`

- [ ] **Step 1: Rewrite middleware to never fall through**

Replace the `if apiKey != ""` / `else c.Next()` logic:

```go
func AuthMiddleware(cfg *config.Config) gin.HandlerFunc {
    return func(c *gin.Context) {
        path := c.Request.URL.Path

        // Public routes
        if strings.HasPrefix(path, "/api/auth/") || path == "/api/health" {
            c.Next()
            return
        }

        authHeader := c.GetHeader("Authorization")
        if authHeader == "" {
            c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "missing Authorization header"})
            return
        }

        token := strings.TrimPrefix(authHeader, "Bearer ")
        if token == authHeader {
            c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid Authorization format, expected Bearer token"})
            return
        }

        // Try API Key first
        if cfg.APIKey != "" && token == cfg.APIKey {
            c.Set("auth_method", "apikey")
            c.Next()
            return
        }

        // Try JWT
        if cfg.JWTSecret != "" {
            claims, err := validateJWT(token, cfg.JWTSecret)
            if err == nil {
                c.Set("auth_method", "jwt")
                c.Set("user_id", claims.UserID)
                c.Set("username", claims.Username)
                c.Next()
                return
            }
        }

        c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid or expired token"})
    }
}
```

Key change: the old `c.Next()` without auth check is completely removed.

- [ ] **Step 2: Run go build**

```bash
cd services/go && go build ./cmd/server/
```

- [ ] **Step 3: Commit**

```bash
git add services/go/internal/api/middleware/auth.go
git commit -m "fix: auth middleware always requires valid credentials, never falls through"
```

---

### Task A6: Pipeline per-run and date validation

**Files:**
- Modify: `services/go/internal/engine/pipeline.go` (add NewPipeline factory)
- Modify: `services/go/internal/engine/backtest.go` (use factory per run)
- Modify: `services/go/cmd/server/main.go` (use factory for live trading)
- Modify: `services/go/internal/api/handler/scheduler.go` (validate dates)

- [ ] **Step 1: Add NewPipeline factory in pipeline.go**

```go
func NewPipeline(portfolio *Portfolio, signalAdapter SignalAdapter, riskManager *RiskManager, oms *OrderManager, marketCfg MarketConfig) *Pipeline {
    return &Pipeline{
        Portfolio:     portfolio,
        SignalAdapter: signalAdapter,
        RiskManager:   riskManager,
        OMS:          oms,
        MarketConfig:  marketCfg,
        LastBars:      make(map[string]Bar),
        // initialize other fields to safe defaults
    }
}
```

- [ ] **Step 2: Use factory in backtest.go Run()**

```go
func (br *BacktestRunner) Run(ctx context.Context, cfg BacktestConfig) (*BacktestResult, error) {
    pipeline := NewPipeline(
        br.portfolio.Clone(),
        br.signalAdapter,
        br.riskManager,
        br.oms.Clone(),
        cfg.MarketConfig,
    )
    br.pipeline = pipeline
    // ... rest of Run logic unchanged
}
```

- [ ] **Step 3: Use factory in main.go for live trading**

```go
livePipeline := engine.NewPipeline(portfolio, signalAdapter, riskManager, oms, liveMarketCfg)
liveRunner := engine.NewLiveTradingRunner(livePipeline, feedClient)
```

- [ ] **Step 4: Fix date validation in scheduler.go**

In `runOnce()` and `executeRun()`, replace `start, _ := time.Parse(...)`:

```go
start, err := time.Parse("2006-01-02", job.StartDate)
if err != nil {
    c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("invalid start date %q: expected YYYY-MM-DD", job.StartDate)})
    return
}
end, err := time.Parse("2006-01-02", job.EndDate)
if err != nil {
    c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("invalid end date %q: expected YYYY-MM-DD", job.EndDate)})
    return
}
```

- [ ] **Step 5: Run go build**

```bash
cd services/go && go build ./cmd/server/
```

- [ ] **Step 6: Commit**

```bash
git add services/go/internal/engine/pipeline.go services/go/internal/engine/backtest.go services/go/cmd/server/main.go services/go/internal/api/handler/scheduler.go
git commit -m "fix: per-run pipeline instances, validate backtest dates"
```

---

## Stream B: Python Research (2 tasks)

### Task B1: Fix CPU_POOL race condition

**Files:**
- Modify: `services/python/src/workflow/workflow_engine.py` (lines 34-45)

- [ ] **Step 1: Move CPU_POOL assignment inside the lock**

In `workflow_engine.py`, change:

```python
# OLD:
_CPU_POOL = None
_CPU_POOL_LOCK = asyncio.Lock()

async def _get_cpu_pool():
    global _CPU_POOL
    if _CPU_POOL is None:
        _CPU_POOL = ProcessPoolExecutor(max_workers=4)
    return _CPU_POOL
```

To:

```python
_CPU_POOL = None
_CPU_POOL_LOCK = asyncio.Lock()

async def _get_cpu_pool():
    global _CPU_POOL
    if _CPU_POOL is not None:
        return _CPU_POOL
    async with _CPU_POOL_LOCK:
        if _CPU_POOL is None:  # double-check under lock
            _CPU_POOL = ProcessPoolExecutor(max_workers=4)
        return _CPU_POOL
```

- [ ] **Step 2: Run workflow tests**

```bash
cd services/python && python -m pytest tests/workflow/test_workflow_engine.py -v
```

Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add services/python/src/workflow/workflow_engine.py
git commit -m "fix: protect CPU_POOL creation with asyncio.Lock to prevent race"
```

---

### Task B2: gRPC serve() return named types

**Files:**
- Modify: `services/python/src/grpc/server.py` (serve function and __main__)

- [ ] **Step 1: Define GrpcServerHandles dataclass and update serve()**

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class GrpcServerHandles:
    server: grpc.Server
    signal_servicer: Optional[object] = None
    data_servicer: Optional[object] = None
    factor_servicer: Optional[object] = None
    llm_servicer: Optional[object] = None
    analysis_servicer: Optional[object] = None
    workflow_servicer: Optional[object] = None

def serve(...) -> GrpcServerHandles:
    # ... existing setup code ...
    return GrpcServerHandles(
        server=server,
        signal_servicer=signal_servicer,
        data_servicer=data_servicer,
        factor_servicer=factor_servicer,
        llm_servicer=llm_servicer,
        analysis_servicer=analysis_servicer,
        workflow_servicer=workflow_servicer,
    )
```

- [ ] **Step 2: Update __main__ to use named fields**

```python
if __name__ == "__main__":
    handles = serve()
    print(f"gRPC server started on port {PORT}")
    handles.server.wait_for_termination()
```

- [ ] **Step 3: Run tests to verify**

```bash
cd services/python && python -m pytest tests/ -k "grpc" -v --timeout=10
```

- [ ] **Step 4: Commit**

```bash
git add services/python/src/grpc/server.py
git commit -m "refactor: return named GrpcServerHandles from serve() instead of tuple"
```

---

## Stream C: Next.js Frontend (5 tasks)

### Task C1: Fix PnL display bug

**Files:**
- Modify: `frontend/components/financial/PositionTable.tsx`

- [ ] **Step 1: Remove Math.abs from PnL percentage**

Locate the PnL percentage display line (~line 167):

```tsx
// OLD:
{formatPercent(Math.abs(pos.pnl_pct || 0))}

// NEW:
{formatPercent(pos.pnl_pct || 0)}
```

- [ ] **Step 2: Verify formatPercent handles negatives**

Check `lib/utils.ts` that `formatPercent` adds a leading `-` for negative values. If it uses `Number.toFixed(2)` directly it's fine (JavaScript handles negative numbers in toFixed). If there's a custom formatter, verify:

```ts
export function formatPercent(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}
```

If formatPercent only handles positive formatting, add:

```ts
export function formatPercent(value: number): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}
```

- [ ] **Step 3: Run type check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/components/financial/PositionTable.tsx
git commit -m "fix: remove Math.abs from PnL percentage display"
```

---

### Task C2: Dashboard zero-division guard

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Add cash guard**

In `app/page.tsx`, line ~55, change:

```tsx
// OLD:
const change = (portfolio.total_value - portfolio.cash) / portfolio.cash * 100;

// NEW:
const change = portfolio.cash > 0
  ? ((portfolio.total_value - portfolio.cash) / portfolio.cash * 100)
  : 0;
```

- [ ] **Step 2: Optional UX enhancement**

If you want to show "N/A" instead of "0%" when cash is zero:

```tsx
{portfolio.cash > 0
  ? `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`
  : 'N/A'}
```

- [ ] **Step 3: Run type check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "fix: guard against zero division when cash is 0"
```

---

### Task C3: BFF Proxy error handling

**Files:**
- Modify: `frontend/lib/bff-proxy.ts`

- [ ] **Step 1: Add try-catch around fetch**

```typescript
export async function bffProxy(req: NextRequest, method: string): Promise<NextResponse> {
  const url = `${API_BASE}${req.nextUrl.pathname.replace('/api/', '/api/v1/')}${req.nextUrl.search}`;

  const headers: Record<string, string> = {};
  const authHeader = req.headers.get('authorization');
  if (authHeader) headers['Authorization'] = authHeader;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  try {
    const body = method === 'GET' || method === 'DELETE' ? undefined : await req.text();
    const res = await fetch(url, {
      method,
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: body || undefined,
      signal: controller.signal,
    });

    const contentType = res.headers.get('content-type') || 'application/json';
    let data: unknown;
    try {
      data = await res.json();
    } catch {
      data = await res.text();
    }

    return NextResponse.json(data, { status: res.status });
  } catch (err: unknown) {
    if (err instanceof Error && err.name === 'AbortError') {
      return NextResponse.json(
        { error: 'Backend request timed out', code: 'BACKEND_TIMEOUT' },
        { status: 504 }
      );
    }
    return NextResponse.json(
      { error: 'Backend unavailable', code: 'BACKEND_UNREACHABLE' },
      { status: 502 }
    );
  } finally {
    clearTimeout(timeout);
  }
}
```

- [ ] **Step 2: Run type check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/bff-proxy.ts
git commit -m "fix: add error handling to BFF proxy for network failures and timeouts"
```

---

### Task C4: Settings partial save

**Files:**
- Modify: `frontend/app/settings/page.tsx`

- [ ] **Step 1: Change saveSection to re-fetch before PUT**

```typescript
async function saveSection(sectionName: string) {
  setSavingSection(sectionName);
  try {
    // Re-fetch current state to avoid overwriting other sections
    const res = await fetch('/api/settings');
    if (!res.ok) throw new Error('Failed to fetch current settings');
    const currentSettings = await res.json();

    // Merge only the changed section
    const merged = { ...currentSettings };
    switch (sectionName) {
      case 'profile':
        merged.profile = { ...currentSettings.profile, ...profileForm };
        break;
      case 'broker':
        merged.broker_credentials = { ...currentSettings.broker_credentials, ...brokerForm };
        break;
      // ... handle other sections
    }

    const putRes = await fetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(merged),
    });

    if (!putRes.ok) throw new Error('Failed to save settings');
    toast.success(`${sectionName} settings saved`);
  } catch (err) {
    toast.error(err instanceof Error ? err.message : 'Save failed');
  } finally {
    setSavingSection(null);
  }
}
```

- [ ] **Step 2: Run type check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/settings/page.tsx
git commit -m "fix: re-fetch settings before PUT to prevent concurrent overwrites"
```

---

### Task C5: JWT type safety

**Files:**
- Create: `frontend/types/next-auth.d.ts`
- Modify: `frontend/lib/auth.config.ts`
- Modify: `frontend/lib/auth-client.ts`

- [ ] **Step 1: Create NextAuth type augmentation**

Create `frontend/types/next-auth.d.ts`:

```typescript
import { DefaultSession, DefaultUser } from "next-auth";
import { DefaultJWT } from "next-auth/jwt";

declare module "next-auth" {
  interface User extends DefaultUser {
    accessToken?: string;
  }
  interface Session extends DefaultSession {
    accessToken?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT extends DefaultJWT {
    accessToken?: string;
  }
}
```

- [ ] **Step 2: Remove as any from auth.config.ts**

In `lib/auth.config.ts`, change:

```typescript
// OLD:
jwt({ token, user }) {
  if (user) {
    token.accessToken = (user as any).accessToken;
  }
  return token;
}
```

To:

```typescript
jwt({ token, user }) {
  if (user) {
    token.accessToken = user.accessToken;
  }
  return token;
}
```

Also fix session callback:

```typescript
session({ session, token }) {
  if (token.accessToken) {
    session.accessToken = token.accessToken;
  }
  return session;
}
```

- [ ] **Step 3: Remove as any from auth-client.ts**

In `lib/auth-client.ts`, change:

```typescript
// OLD:
const accessToken = (session as any)?.accessToken;

// NEW:
const accessToken = session?.accessToken;
```

- [ ] **Step 4: Run type check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors (all `as any` casts removed, types properly resolved)

- [ ] **Step 5: Commit**

```bash
git add frontend/types/next-auth.d.ts frontend/lib/auth.config.ts frontend/lib/auth-client.ts
git commit -m "fix: add NextAuth type augmentation, remove as any casts"
```

---

## Execution Strategy

Three streams (A: Go, B: Python, C: Frontend) are fully independent. Dispatch all tasks in parallel for fastest execution. Within each stream, tasks have sequential dependencies (e.g., A1 crypto must complete before A3 broker encryption), so each stream should be executed sequentially by its agent.
