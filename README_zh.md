<p align="center">
  <img src="https://img.shields.io/badge/Go-1.22+-00ADD8?style=for-the-badge&logo=go&logoColor=white" alt="Go">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Next.js-15-000000?style=for-the-badge&logo=nextdotjs&logoColor=white" alt="Next.js">
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/因子库-450+-orange?style=flat-square" alt="因子数">
  <img src="https://img.shields.io/badge/数据源-23-blue?style=flat-square" alt="数据源">
  <img src="https://img.shields.io/badge/AI技能-89-purple?style=flat-square" alt="AI 技能">
  <img src="https://img.shields.io/badge/工作流节点-58-teal?style=flat-square" alt="工作流节点">
  <img src="https://img.shields.io/badge/i18n-4_语言-06b6d4?style=flat-square" alt="i18n">
  <img src="https://img.shields.io/badge/版本-v2026.6.21-blueviolet?style=flat-square" alt="版本">
</p>

<h1 align="center">🚀 AStockPursue</h1>
<p align="center"><strong>AI 驱动的量化研究工作流平台</strong></p>
<p align="center">
  <sub>Go + Python 混合微服务架构 — 高性能交易引擎 × AI 研究层</sub>
  <br>
  <sub><a href="README.md">English</a> · <a href="CHANGELOG.md">变更日志</a></sub>
</p>

---

> **免责声明**：本软件**仅供研究学习使用**，不构成任何投资建议。作者和贡献者对使用本软件所产生的任何交易损失不承担任何责任。**历史业绩不代表未来表现。**

## 架构设计

AStockPursue 采用 **Go + Python 混合微服务架构**，通过 gRPC 通信：

```
前端 (Next.js, 端口 5899)
    │  REST JSON
Go 核心服务 (端口 8899)
    ├─ HTTP API (gin) — 交易、回测、认证、行情
    ├─ 交易引擎 — on_bar() 管线，8 种市场引擎
    ├─ 行情数据 — 多源加载器、三级存储、WebSocket 推送
    ├─ 券商网关 — Binance、Futu、OKX
    ├─ 组合/风控 — 仓位计算、保证金、止损
    └─ gRPC 客户端 ────────┐
    │  gRPC + Protobuf      │
Python 研究层 (端口 8900/8902)
    ├─ MCP Server — 22 工具、89 技能、swarm 预设
    ├─ 因子挖掘 — GP 进化、452 alpha zoo
    ├─ AI Agent — LLM agent、langgraph 循环、记忆
    ├─ 分析 — 归因、情绪、相关性
    ├─ 工作流引擎 — 25 节点类型、可视化管线
    └─ gRPC Server — factor, signal, LLM, analysis, workflow, data
    │  SQL + Pub/Sub
数据层
    PostgreSQL 16 + TimescaleDB + Redis 7
```

**设计理念**：Go 负责性能关键的交易执行和行情数据管道，Python 负责 AI/研究层（因子挖掘、LLM agent、工作流编排）。gRPC 通信保持边界清晰。

## 核心功能

### 交易引擎（Go）
- **统一 bar-by-bar 管线** — 回测和实盘共用同一执行引擎
- **8 种市场引擎** — A股（T+1、涨跌停）、美股/港股、加密货币永续、外汇、中国期货、全球期货、期权、复合
- **风控管线** — 止损、追踪止损、止盈、日内最大亏损、仓位限制
- **多券商** — 富途（A股/港股/美股）、Binance + OKX（加密货币），自注册模式
- **模拟交易** — 状态机（创建→运行→暂停→停止→错误），内存仓库
- **行情数据** — 8 个 A 股加载器 + gRPC 桥接，三级存储，WebSocket 实时推送

### AI Agent（89 项技能）
- **自然语言 → 策略代码** — 「帮我写一个沪深300动量策略」直接生成并回测完整 SignalEngine
- **ReAct 循环** — 89 个技能包全覆盖：A股、加密货币、期权、宏观、风控、因子分析
- **11 种 LLM** — OpenAI · Anthropic · DeepSeek · Gemini · 月之暗面 · 智谱 · Grok · Ollama · MiniMax · 通义千问 · OpenRouter

### Alpha 工厂
- **450+ 预置因子** — alpha101（101个）、gtja191（191个）、qlib158（158个）、学术因子、用户挖掘
- **GP 进化引擎** — 遗传规划 + 复合适应度（IC × 复杂度 × 正交性）、FDR 校正、滚动窗口验证
- **LLM 因子挖掘** — 从研报提取公式、候选人辩论、GP+LLM 混合流水线

### 可视化工作流引擎
- **58 种类型化节点** — 拖拽连线画布，实时类型校验
- **并发执行** — Kahn 算法 + asyncio 并行调度
- **运行时快照** — 每次运行捕获完整 DAG 状态，永远可复现

### 研究工具
- **智能筛选器** — 多条件股票筛选，整合 Alpha Zoo 因子
- **业绩归因** — Brinson、因子、行业分解
- **策略对比** — 统计检验（配对 t、自助法、White 现实检验）
- **新闻情绪** — 多源聚合，中文 NLP 评分
- **市场状态识别** — 规则型分类，含策略族推荐

### 平台特性
- **多用户隔离** — JWT 认证，用户级数据和券商凭证
- **定时任务** — Cron 自动回测、数据健康检查、自选股提醒
- **策略市场** — 发布、浏览、安装、评分社区策略
- **国际化** — English、简体中文、日本語、한국어

## 技术栈

| 层 | 技术 |
|------|------|
| **前端** | Next.js 15, React 19, TypeScript, Zustand, Recharts + D3, CodeMirror 6, Tailwind CSS 4, shadcn/ui |
| **Go 核心** | Go 1.22+, gin, pgx, rueidis, gRPC 客户端 |
| **Python 研究** | Python 3.11+, gRPC 服务端, PyTorch, scikit-learn, SnowNLP, pgvector, LangChain |
| **数据** | PostgreSQL 16 + TimescaleDB, Redis 7, pandas, NumPy, Parquet |
| **基础设施** | Docker Compose, JWT, SSE 流式推送, GitHub Actions CI/CD |

## 快速开始

```bash
# 完整部署
docker compose up -d --build              # Go 核心 (8899) + Python (8900/8902)
docker compose --profile pg up -d --build # 同时部署 PostgreSQL
docker compose --profile frontend up -d   # 前端开发服务器 (5899)

# Go 核心开发
cd services/go && go run ./cmd/server     # HTTP API + gRPC 客户端

# Python 研究层开发
cd services/python && pip install -r requirements.txt
python mcp_server.py                      # MCP (stdio/SSE, 端口 8900)
python -m src.grpc.server                 # gRPC 服务端 (端口 8902)

# 前端开发
cd frontend && npm run dev

# 测试
cd services/go && go test ./...           # Go 单元测试
cd services/python && python -m pytest tests/ -x -q # Python 测试
cd frontend && npx vitest                 # 前端测试
```

## 项目结构

```
astockpursue/
├── services/
│   ├── go/                         # Go 核心服务
│   │   ├── cmd/server/             #   入口（gin HTTP + gRPC 客户端）
│   │   ├── internal/
│   │   │   ├── api/handler/        #   REST 处理器（16 个端点）
│   │   │   ├── engine/             #   交易引擎（8 类型 + 管线 + 风控）
│   │   │   ├── market/             #   加载器、存储、行情推送
│   │   │   ├── broker/             #   Binance、OKX、Futu 网关
│   │   │   ├── portfolio/          #   仓位计算（等权/Kelly/风险平价）+ 保证金
│   │   │   ├── papertrade/         #   模拟交易引擎
│   │   │   └── db/                 #   PostgreSQL + TimescaleDB + Redis
│   │   └── Dockerfile
│   ├── python/                     # Python 研究层
│   │   ├── mcp_server.py           #   MCP 服务端（stdio/SSE）
│   │   ├── src/
│   │   │   ├── grpc/               #   gRPC 服务实现（6 个 service）
│   │   │   ├── factors/            #   Alpha Zoo + GP 进化引擎
│   │   │   ├── agent/              #   ReAct Agent 循环
│   │   │   ├── skills/             #   89 个技能包
│   │   │   ├── workflow/           #   可视化工作流引擎
│   │   │   ├── swarm/              #   多智能体编排
│   │   │   ├── tools/              #   MCP 工具实现
│   │   │   └── services/           #   分析、实盘桥接
│   │   ├── backtest/               #   加载器 + 数据存储（MCP 保留）
│   │   └── tests/
│   ├── proto/                      # 共享 Protobuf 定义
│   │   ├── signal.proto
│   │   ├── factor.proto
│   │   ├── llm.proto
│   │   ├── analysis.proto
│   │   ├── workflow.proto
│   │   └── data.proto
│   └── frontend/                   # Next.js 前端
│       ├── app/                    #   App Router 页面（27 页）
│       ├── components/             #   UI + 金融组件
│       ├── stores/                 #   Zustand 状态管理
│       └── lib/                    #   API 客户端、i18n、工具
├── docs/                           # 文档
├── docker-compose.yml
├── CHANGELOG.md
└── CLAUDE.md
```

## 许可证

MIT License。基于 [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License) 二次开发。
