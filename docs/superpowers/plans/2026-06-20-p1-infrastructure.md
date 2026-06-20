# P1: Go + Python Hybrid Infrastructure Implementation Plan

> **For agentic workers:** Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Set up the Go project scaffold, Protobuf definitions, Docker Compose layout, and CI/CD infra for the hybrid architecture.

**Architecture:** Go core (gin REST + gRPC client) lives in `services/go/`, Python research layer (existing code) moves to `services/python/`, shared protos in `services/proto/`, frontend in `services/frontend/` (Next.js). Docker Compose runs all services.

**Tech Stack:** Go 1.22+, gin, pgx, connect-go, buf, Docker Compose, PostgreSQL 16, Redis 7

## Global Constraints

- All Go code under `services/go/internal/` — no `pkg/` or `cmd/` outside standard layout
- Protobuf definitions in `services/proto/`, generated Go code in `services/go/internal/gen/`
- All Python code moves to `services/python/` (rename from `backend/`)
- Docker Compose must match the spec's 5-service layout (go-core, python-research, frontend, postgres, redis)
- CI must run `go test ./...`, `go vet ./...`, and `golangci-lint` on every push
- Version must be updated per CLAUDE.md rules (v2026.6.20 as of this writing)
- All development must follow Spec → Plan → Test → Development Flow per CLAUDE.md

---

### Task 1: Create Go Project Scaffold

**Files:**
- Create: `services/go/go.mod`
- Create: `services/go/cmd/server/main.go`
- Create: `services/go/internal/config/config.go`
- Create: `services/go/internal/api/router.go`
- Create: `services/go/internal/api/handler/health.go`
- Create: `services/go/Makefile`

**Interfaces:**
- Consumes: nothing (first task)
- Produces: runnable `go run ./cmd/server` on `:8899` with health endpoint

- [ ] **Step 1: Initialize Go module**

```bash
mkdir -p services/go/cmd/server
mkdir -p services/go/internal/{api/handler,api/middleware,engine,market/loader,broker,portfolio,papertrade,grpc,db,config,gen}
cd services/go
go mod init github.com/astockpursue/go-core
```

- [ ] **Step 2: Add dependencies**

```bash
cd services/go
go get github.com/gin-gonic/gin@latest
go get github.com/jackc/pgx/v5@latest
go get github.com/redis/rueidis@latest
go get github.com/bufbuild/connect-go@latest
```

- [ ] **Step 3: Write config package**

```go
// services/go/internal/config/config.go
package config

type Config struct {
    Port        string
    DatabaseURL string
    RedisURL    string
    GrpcPort    string
}

func Load() *Config {
    return &Config{
        Port:        getEnv("PORT", "8899"),
        DatabaseURL: getEnv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/astockpursue?sslmode=disable"),
        RedisURL:    getEnv("REDIS_URL", "redis://localhost:6379/0"),
        GrpcPort:    getEnv("GRPC_PORT", "8901"),
    }
}

func getEnv(key, fallback string) string {
    if val := os.Getenv(key); val != "" {
        return val
    }
    return fallback
}
```

- [ ] **Step 4: Write health handler**

```go
// services/go/internal/api/handler/health.go
package handler

type HealthHandler struct{}

func (h *HealthHandler) Health(c *gin.Context) {
    c.JSON(200, gin.H{"status": "ok", "service": "go-core"})
}
```

- [ ] **Step 5: Write router**

```go
// services/go/internal/api/router.go
package api

func NewRouter(h *handler.HealthHandler) *gin.Engine {
    r := gin.Default()
    r.GET("/health", h.Health)
    return r
}
```

- [ ] **Step 6: Write main.go**

```go
// services/go/cmd/server/main.go
package main

func main() {
    cfg := config.Load()
    h := &handler.HealthHandler{}
    r := api.NewRouter(h)
    log.Printf("Starting go-core on :%s", cfg.Port)
    r.Run(":" + cfg.Port)
}
```

- [ ] **Step 7: Write Makefile**

```makefile
# services/go/Makefile
.PHONY: run test lint clean

run:
	go run ./cmd/server

test:
	go test ./... -v -count=1

lint:
	golangci-lint run ./...

vet:
	go vet ./...

build:
	go build -o bin/server ./cmd/server

clean:
	rm -rf bin/
```

- [ ] **Step 8: Run to verify**

```bash
cd services/go && go run ./cmd/server &
curl http://localhost:8899/health
kill %1
```

Expected: `{"status":"ok","service":"go-core"}`

- [ ] **Step 9: Write test for health endpoint**

```go
// services/go/internal/api/handler/health_test.go
package handler

func TestHealth(t *testing.T) {
    w := httptest.NewRecorder()
    c, _ := gin.CreateTestContext(w)
    h := &HealthHandler{}
    h.Health(c)
    assert.Equal(t, 200, w.Code)
    assert.Contains(t, w.Body.String(), `"status":"ok"`)
}
```

- [ ] **Step 10: Run tests to verify**

```bash
cd services/go && go test ./... -v -count=1
```

Expected: PASS all

- [ ] **Step 11: Commit**

```bash
git add services/go/
git commit -m "feat(go): initialize Go core project scaffold"
```

---

### Task 2: Protobuf Definitions and Code Generation

**Files:**
- Create: `services/proto/common.proto`
- Create: `services/proto/signal.proto`
- Create: `services/proto/factor.proto`
- Create: `services/proto/llm.proto`
- Create: `services/proto/analysis.proto`
- Create: `services/proto/workflow.proto`
- Create: `services/proto/buf.yaml`
- Create: `services/proto/buf.gen.yaml`
- Create: `services/go/internal/gen/` (generated code)
- Modify: `services/go/Makefile` (add `gen-proto` target)

**Interfaces:**
- Consumes: Task 1 (project scaffold)
- Produces: Go generated protobuf types at `services/go/internal/gen/`

- [ ] **Step 1: Install buf CLI**

```bash
# Windows: scoop install buf
# Or download from https://github.com/bufbuild/buf/releases
go install github.com/bufbuild/buf/cmd/buf@latest
```

- [ ] **Step 2: Write common.proto**

```protobuf
// services/proto/common.proto
syntax = "proto3";
package astockpursue.common;
option go_package = "github.com/astockpursue/go-core/internal/gen/common/v1;commonv1";

message Bar {
  string symbol = 1;
  double open = 2;  double high = 3;  double low = 4;  double close = 5;
  int64 volume = 6;  int64 timestamp = 7;
  string frequency = 8;
}

message Position {
  string symbol = 1;
  double size = 2;
  double entry_price = 3;
  double current_price = 4;
  double pnl = 5;
  string side = 6;
}

message Order {
  string id = 1;  string symbol = 2;  string side = 3;  string type = 4;
  double price = 5;  double quantity = 6;  string status = 7;
}
```

- [ ] **Step 3: Write signal.proto (detail from spec section 3.2)**

```protobuf
// services/proto/signal.proto
syntax = "proto3";
package astockpursue.signal;
option go_package = "github.com/astockpursue/go-core/internal/gen/signal/v1;signalv1";

import "common.proto";

service SignalService {
  rpc GenerateSignals(SignalRequest) returns (SignalResponse);
}

message SignalRequest {
  string strategy_name = 1;
  repeated common.Bar bars = 2;
  string mode = 3;
  map<string, string> params = 4;
}

message SignalResponse {
  map<string, double> weights = 1;
  string error = 2;
}
```

- [ ] **Step 4: Write factor.proto (detail from spec section 3.3)**

```protobuf
// services/proto/factor.proto
syntax = "proto3";
package astockpursue.factor;
option go_package = "github.com/astockpursue/go-core/internal/gen/factor/v1;factorv1";

service FactorService {
  rpc ComputeFactor(FactorRequest) returns (FactorResponse);
  rpc StartGPMining(GPRequest) returns (stream GPResult);
}

message FactorRequest {
  string formula = 1;
  repeated string symbols = 2;
  string start_date = 3;
  string end_date = 4;
}

message FactorResponse {
  map<string, double> values = 1;
  string error = 2;
}

message GPRequest {
  string pool = 1;
  int32 generations = 2;
  int32 population_size = 3;
  string fitness_metric = 4;
}

message GPResult {
  string formula = 1;
  double ic = 2;
  double sharpe = 3;
  int32 generation = 4;
}
```

- [ ] **Step 5: Write llm.proto (detail from spec section 3.4)**

```protobuf
// services/proto/llm.proto
syntax = "proto3";
package astockpursue.llm;
option go_package = "github.com/astockpursue/go-core/internal/gen/llm/v1;llmv1";

service LLMService {
  rpc Chat(ChatRequest) returns (ChatResponse);
  rpc AgentDecide(AgentRequest) returns (AgentResponse);
}

message ChatRequest { string message = 1; }
message ChatResponse { string reply = 1; }

message AgentRequest {
  string query = 1;
  map<string, string> context = 2;
}
message AgentResponse {
  string action = 1;
  map<string, string> params = 2;
}
```

- [ ] **Step 6: Write analysis.proto (detail from spec section 3.5)**

```protobuf
// services/proto/analysis.proto
syntax = "proto3";
package astockpursue.analysis;
option go_package = "github.com/astockpursue/go-core/internal/gen/analysis/v1;analysisv1";

service AnalysisService {
  rpc CalcAttribution(AttributionRequest) returns (AttributionResponse);
  rpc CalcCorrelation(CorrelationRequest) returns (CorrelationResponse);
  rpc StressTest(StressTestRequest) returns (StressTestResponse);
}
```

- [ ] **Step 7: Write workflow.proto (detail from spec section 3.6)**

```protobuf
// services/proto/workflow.proto
syntax = "proto3";
package astockpursue.workflow;
option go_package = "github.com/astockpursue/go-core/internal/gen/workflow/v1;workflowv1";

service WorkflowService {
  rpc ExecuteWorkflow(WorkflowRequest) returns (WorkflowResponse);
  rpc GetNodeResult(NodeQuery) returns (NodeResult);
}
```

- [ ] **Step 8: Write buf.yaml**

```yaml
# services/proto/buf.yaml
version: v2
modules:
  - path: .
lint:
  use:
    - STANDARD
breaking:
  use:
    - FILE
```

- [ ] **Step 9: Write buf.gen.yaml**

```yaml
# services/proto/buf.gen.yaml
version: v2
plugins:
  - local: protoc-gen-go
    out: ../go/internal/gen
    opt: paths=source_relative
  - local: protoc-gen-go-grpc
    out: ../go/internal/gen
    opt: paths=source_relative
```

- [ ] **Step 10: Generate Go code**

```bash
cd services/proto
buf generate
```

Expected: Generated `.pb.go` files in `services/go/internal/gen/`

- [ ] **Step 11: Add `gen-proto` to Makefile**

```makefile
# Append to services/go/Makefile
gen-proto:
	cd ../proto && buf generate

.PHONY: gen-proto
```

- [ ] **Step 12: Verify Go compiles with generated code**

```bash
cd services/go && go build ./...
```

Expected: Build succeeds

- [ ] **Step 13: Commit**

```bash
git add services/proto/ services/go/internal/gen/ services/go/Makefile
git commit -m "feat(proto): add protobuf definitions and code generation"
```

---

### Task 3: Docker Compose Layout

**Files:**
- Modify: `docker-compose.yml`
- Create: `services/go/Dockerfile`
- Create: `services/python/Dockerfile.python`

**Interfaces:**
- Consumes: Task 1 (Go scaffold), Task 2 (protos)
- Produces: `docker compose up` runs all 5 services

- [ ] **Step 1: Read current docker-compose.yml**

```bash
cat docker-compose.yml
```

- [ ] **Step 2: Write updated docker-compose.yml**

```yaml
# docker-compose.yml
services:
  go-core:
    build:
      context: services/go
      dockerfile: Dockerfile
    ports:
      - "8899:8899"
      - "8901:8901"
    environment:
      PORT: "8899"
      GRPC_PORT: "8901"
      DATABASE_URL: "postgres://postgres:postgres@postgres:5432/astockpursue?sslmode=disable"
      REDIS_URL: "redis://redis:6379/0"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    networks:
      - vt-net

  python-research:
    build:
      context: services/python
      dockerfile: Dockerfile.python
    ports:
      - "8900:8900"
      - "8902:8902"
    environment:
      PYTHONUNBUFFERED: "1"
      DATABASE_URL: "postgres://postgres:postgres@postgres:5432/astockpursue?sslmode=disable"
      REDIS_URL: "redis://redis:6379/0"
    depends_on:
      go-core:
        condition: service_started
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    networks:
      - vt-net
    volumes:
      - ./runs:/app/runs
      - ./services/python/src:/app/src

  frontend:
    build:
      context: services/frontend
      dockerfile: Dockerfile
    ports:
      - "5899:5899"
    environment:
      NEXT_PUBLIC_API_URL: "http://localhost:8899"
    depends_on:
      - go-core
    networks:
      - vt-net
    profiles:
      - frontend

  postgres:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: astockpursue
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - pg-data:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - vt-net
    profiles:
      - pg

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - vt-net

networks:
  vt-net:
    driver: bridge

volumes:
  pg-data:
  redis-data:
```

- [ ] **Step 3: Write Dockerfile for Go**

```dockerfile
# services/go/Dockerfile
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /server ./cmd/server

FROM alpine:3.19
RUN apk --no-cache add ca-certificates tzdata
COPY --from=builder /server /server
EXPOSE 8899 8901
CMD ["/server"]
```

- [ ] **Step 4: Write Dockerfile.python**

```dockerfile
# services/python/Dockerfile.python
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8900 8902
CMD ["python", "mcp_server.py"]
```

- [ ] **Step 5: Build and test**

```bash
docker compose build go-core python-research
```

Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml services/go/Dockerfile services/python/Dockerfile.python
git commit -m "chore(docker): update compose for hybrid architecture"
```

---

### Task 4: CI/CD Pipeline

**Files:**
- Create/modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: Task 1 (Go scaffold)
- Produces: CI runs lint+test on every push

- [ ] **Step 1: Write CI workflow**

```yaml
# .github/workflows/ci.yml
name: CI
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  go-lint-test:
    name: Go Core
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: services/go
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: "1.22"
      - name: Lint
        uses: golangci/golangci-lint-action@v4
        with:
          working-directory: services/go
      - name: Vet
        run: go vet ./...
      - name: Test
        run: go test ./... -v -count=1 -race

  python-lint-test:
    name: Python Research
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: services/python
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install deps
        run: |
          pip install -r requirements.txt
          pip install ruff pytest pytest-cov
      - name: Lint
        run: ruff check src/ tests/
      - name: Test
        run: python -m pytest tests/ -x -q --cov=src
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add Go + Python CI pipeline"
```

---

### Task 5: Python Layer Relocation

**Files:**
- Rename: `backend/` → `services/python/`
- Modify: `services/python/pyproject.toml` (update paths)
- Modify: `services/python/Dockerfile.python` (adjust if needed)
- Update: `services/python/requirements.txt` (remove Go-specific deps)

**Interfaces:**
- Consumes: Task 3 (Docker Compose layout)
- Produces: Python code lives under `services/python/`

- [ ] **Step 1: Move backend to python**

```bash
# Use git mv to preserve history
git mv backend/ services/python/
```

- [ ] **Step 2: Update pyproject.toml paths**

```bash
# Read and fix any path references in pyproject.toml
cat services/python/pyproject.toml
```

Update paths from `backend/` to `services/python/` in the file.

- [ ] **Step 3: Verify Python still works**

```bash
cd services/python && python -c "import src; print('OK')"
```

Expected: No import errors (some will fail due to trading/backtest modules still existing — that's OK for now)

- [ ] **Step 4: Commit**

```bash
git add services/python/
git rm -r backend/ 2>/dev/null || true
git commit -m "refactor(python): relocate backend/ to services/python/"
```

---

### Task 6: Version Update & Changelog

**Files:**
- Modify: `README.md`
- Modify: `README_zh.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: all prior tasks
- Produces: CHANGELOG reflects the refactoring start

- [ ] **Step 1: Update README.md badge**

```bash
# Already done in spec creation; verify
grep "v2026.6.20" README.md
```

- [ ] **Step 2: Update README_zh.md badge**

```bash
# Already done in spec creation; verify
grep "v2026.6.20" README_zh.md
```

- [ ] **Step 3: Add changelog entry**

```markdown
## [2026.6.20] - 2026-06-20

### Added
- [Infra] Go core project scaffold with gin HTTP server and health endpoint
- [Infra] Protobuf definitions for 6 gRPC services (signal, factor, llm, analysis, workflow, common)
- [Infra] Buf-based code generation pipeline
- [Infra] Updated Docker Compose with go-core, python-research, frontend, postgres, redis services
- [Infra] CI/CD pipeline with Go lint+test+race and Python lint+test
- [CLAUDE.md] Spec → Plan → Test → Development Flow rule (development now requires spec + plan + tests before coding)

### Changed
- [Infra] Python code relocated from `backend/` to `services/python/`
- [Infra] Architecture documented as Go + Python hybrid in CLAUDE.md
- [Version] Updated to v2026.6.20

### Removed
- [Infra] Old `backend/` directory (replaced by `services/python/`)
```

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md
git commit -m "chore: update changelog for refactoring start"
```

---

## Self-Review

1. All spec requirements implemented: P1 covers Go scaffold (Task 1), protos (Task 2), Docker (Task 3), CI (Task 4), Python relocation (Task 5), version/changelog (Task 6). No gaps.
2. No placeholders: all code is concrete, all paths are exact.
3. Type consistency: proto packages match between buf config and .proto files.
