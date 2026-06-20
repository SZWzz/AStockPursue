# P0-P2 前端功能缺口修复设计

> 日期：2026-06-20 | 状态：已确认

## 根因与修复

### P0-1: Python gRPC 不可用 → Factors/Workflow/Agent/Signal 不可用

**根因**: Python gRPC 未启动，Go dial 失败 → factor/workflow/signal handler 为 nil → 路由不注册。

**修复**: main.go 改为即使 gRPC dial 失败也注册路由（handler 内部调用时返回友好错误），同时加 dev.sh 一键启动 Python gRPC。

### P0-2: Screener/Market 数据响应 18 秒

**根因**: Sina/Tencent loader 不支持历史数据但仍被优先尝试，每个 symbol 穿透 4 层 fallback。

**修复**: loader registry 标记 Sina/Tencent 为 realtime-only，历史查询跳过它们。增加种子数据预加载数量（5→12 只）。

### P1-1: Workflow 无列表/保存端点

**根因**: Go 只有 `POST /execute` 和 `GET /node/:id`。

**修复**: 
- `GET /api/v1/workflow` → 返回内存工作流列表
- `POST /api/v1/workflow` → 创建/更新工作流（接受 nodes/edges JSON）

### P1-2: Strategy Lab 代码未发给 API

**根因**: BacktestPanel handleRun 只发 symbol/date，不发 code。

**修复**: POST body 增加 `code` 字段。

### P2-1: Dashboard KPI 硬编码

**修复**: KPI 卡片从 `/api/v1/portfolio` 读取真实数据。

### P2-2: Trading PriceTicker 假数据

**修复**: PriceTicker 从 `/api/v1/market/bars` 获取最新价。
