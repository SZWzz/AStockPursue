<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-14+-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/因子库-450+-orange?style=flat-square" alt="因子数">
  <img src="https://img.shields.io/badge/数据源-23-blue?style=flat-square" alt="数据源">
  <img src="https://img.shields.io/badge/AI技能-89-purple?style=flat-square" alt="AI 技能">
  <img src="https://img.shields.io/badge/工作流节点-58-teal?style=flat-square" alt="工作流节点">
  <img src="https://img.shields.io/badge/i18n-4_语言-06b6d4?style=flat-square" alt="i18n">
  <img src="https://img.shields.io/badge/版本-v2026.6.6-blueviolet?style=flat-square" alt="版本">
</p>

<h1 align="center">🚀 AStockPursue</h1>
<p align="center"><strong>AI 驱动的量化研究工作流平台</strong></p>
<p align="center">
  <sub>n8n 风格的可视化管道编辑器 — 拖拽、连线、一键运行完整量化研究流程</sub>
  <br>
  <sub><a href="README.md">📖 English</a> · <a href="CHANGELOG.md">📋 变更日志</a></sub>
</p>

---

基于 [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License) 二次开发。

> ⚠️ **免责声明**：本软件**仅供研究学习使用**，不构成任何投资建议。作者和贡献者对使用本软件所产生的任何交易损失不承担任何责任。**历史业绩不代表未来表现。投资有风险，交易需谨慎。**

## ✨ 架构设计

AStockPursue 是一个 **n8n 风格的可视化工作流平台**，专为量化研究设计。不用在 19 个独立页面间跳来跳去，整条研究管道在一个画布上组装完成：

```
项目  ──▶  工作流画布  ──▶  执行与分析
                │
                ├── 股票池 ──▶ 行情加载 ──▶ Alpha因子 ──▶ 策略 ──▶ 回测 ──▶ 归因
                │                                                                    │
                ├── 市场状态 ──▶ 实验管线 ──▶ 评分节点 ──▶ 策略进化                   │
                │       │               │                                     │      │
                │       └── 状态识别     └── 变体→批量回测→排名                ──┘      │
                │                                                                     │
                └── 对话输入 ──▶ AI Agent ──▶ 策略 ──▶ 回测 ──▶ 通知推送 ──▶ 模拟盘
                                                                             │
                                                                   Telegram/邮件/钉钉
```

**所有工具**（策略实验室、因子挖掘、筛选器等）都化为画布上的**类型化节点**，双击即可打开全屏编辑器深入使用。

## ✨ 核心功能

### 🎨 可视化工作流引擎
- **58 种类型化节点**覆盖 10 个类别 — 数据加载、因子计算、策略构建、回测、归因、筛选、模拟盘、AI Agent、市场状态识别、策略进化、实验管线、通知推送、券商连接
- **拖拽连线画布** — 可视化组装研究管道，连线时实时校验类型兼容性
- **并发执行** — Kahn 算法 + asyncio 并行调度互不依赖的节点，按资源画像（CPU/IO）做信号量控制
- **运行时快照** — 每次运行捕获完整 DAG 状态，历史结果永远可复现
- **节点级执行** — 单独运行任一节点查看中间产出，确认后再继续
- **错误恢复** — 失败节点重试、跳过非关键错误、断点续跑
- **版本历史** — 一键恢复工作流到任意历史运行状态

### 🤖 AI Agent（89 项技能）
- **自然语言 → 策略代码** — 「帮我写一个沪深300动量策略」直接生成并回测完整 SignalEngine
- **AgentNode 画布节点** — AI 是工作流中的一个节点：接收提示词+上下文，产出代码+分析+因子建议
- **ReAct 循环** — 89 个技能包全覆盖：A 股、加密货币、期权、宏观、风控、因子分析、市场微观结构
- **11 种 LLM 提供商** — OpenAI · Anthropic · DeepSeek · Gemini · 月之暗面 · 智谱 · Grok · Ollama · MiniMax · 通义千问 · OpenRouter

### 📊 交易引擎
- **统一 bar-by-bar 管道** — 回测和实盘共用同一执行引擎
- **9 种市场引擎** — A 股（T+1、涨跌停）、美股/港股、加密货币永续、外汇、期货（中国+全球）、期权
- **风控管道** — 止损、追踪止损、止盈、日内最大亏损、仓位限制
- **多券商支持** — 富途（A股/港股/美股）、Binance + OKX（加密货币永续）通过 ccxt 统一 API。Fernet 加密存储凭证
- **实盘交易** — 实时 WebSocket 行情、OMS 订单管理、BrokerNode 画布集成
- **内联通知** — 止损/止盈触发时自动推送 Telegram、Discord、飞书、邮件、Webhook

### 🧬 Alpha 工厂
- **450+ 预置因子** — alpha101（101个）、gtja191（191个）、qlib158（158个）、学术因子、用户挖掘
- **GP 进化引擎** — 遗传规划 + 复合适应度（IC × 复杂度 × 正交性）、FDR 校正、滚动窗口验证
- **LLM 因子挖掘** — 从研报提取公式、候选人辩论、GP+LLM 混合流水线

### 🔍 研究工具
- **智能筛选器** — 多条件股票筛选（AND / 排名 / 评分模式），整合 Alpha Zoo 因子
- **业绩归因** — Brinson 分解、因子暴露、行业归因
- **策略对比** — 统计检验（配对 t、自助法、White 现实检验）、权益曲线叠加
- **新闻情绪** — 多源聚合（东方财富、华尔街见闻、新浪、雪球），中文 NLP 评分
- **实验管线** — 市场状态→变体生成→批量回测→评分→排名→最优策略 闭环。网格/随机搜索 + 7 维多因子评分（A-E 评级）
- **市场状态识别** — 规则型分类（牛市/熊市/震荡/高波动）含策略族推荐，A 股特有状态检测（涨停潮/阴跌/轮动）
- **策略进化引擎** — 5 代迭代优化（网格→扰动→交叉→LLM→WalkForward），含过拟合检测和早停
- **AI 反思学习** — Agent 分析决策 7 天后验证实际收益率，形成反馈闭环

### 🏗 平台特性
- **多用户隔离** — JWT 认证，用户级数据、券商凭证、通知配置独立
- **定时任务** — Cron 自动回测、数据健康检查、自选股提醒、工作流定时调度
- **策略市场** — 发布、浏览、安装、评分社区策略
- **版本控制** — 策略完整差异历史，一键回滚
- **国际化** — English、简体中文、日本語、한국어（浏览器语言自动检测）

## 🛠 技术栈

| 层 | 技术 |
|------|------|
| **前端** | React 19, TypeScript, @xyflow/react（画布）, Zustand（状态）, ECharts, Monaco Editor, Tailwind CSS |
| **后端** | Python 3.11+, FastAPI, asyncio, PostgreSQL, psycopg2 |
| **AI/ML** | PyTorch, scikit-learn, SnowNLP, pgvector, LangChain |
| **数据** | pandas, NumPy, Parquet, DuckDB, PostgreSQL 缓存, Redis L0 缓存 |
| **基础设施** | Docker Compose, Nginx, Redis, SSE 流式推送, JWT 认证, GitHub Actions CI/CD |

## 🚀 快速开始

```bash
# 完整部署（Redis + PG + 后端 + MCP + 前端）
docker compose up -d --build              # 后端 (8899) + MCP (8900) + Redis (6379)
docker compose --profile pg up -d --build # 同时部署 PostgreSQL
docker compose --profile frontend up -d   # 前端开发服务器 (5899)

# 后端开发
cd backend && pip install -r requirements.txt
cp .env.example .env
python api_server.py --port 8899          # FastAPI 服务器

# 前端开发
cd frontend && npm install && npx vite --port 5899

# 测试
cd backend && python -m pytest tests/ -x -q
cd frontend && npx tsc --noEmit && npx vitest run
```

## 📁 项目结构

```
astockpursue/
├── backend/                         # Python 后端
│   ├── api_server.py              # FastAPI 入口
│   ├── src/
│   │   ├── workflow/              # ★ 工作流引擎（n8n 风格）
│   │   │   ├── schema.py          #   类型化端口、DAG 模型
│   │   │   ├── node_base.py       #   BaseNode 抽象类
│   │   │   ├── node_registry.py   #   节点类型注册中心（58 节点）
│   │   │   ├── workflow_engine.py #   Kahn + asyncio 并发执行器
│   │   │   ├── workflow_store.py  #   PostgreSQL 持久化
│   │   │   └── nodes/             #   16 个节点模块
│   │   │       ├── data_nodes.py  #     股票池、行情加载
│   │   │       ├── alpha_nodes.py #     Alpha 因子计算
│   │   │       ├── strategy_nodes.py #  策略生成、回测、进化
│   │   │       ├── analysis_nodes.py #  归因分析
│   │   │       ├── thin_nodes.py  #     筛选器、模拟盘
│   │   │       ├── control_nodes.py #   ChatInput、Agent、IF
│   │   │       ├── experiment_nodes.py # 实验管线、评分、排名
│   │   │       ├── regime_nodes.py #    市场状态识别
│   │   │       ├── notify_nodes.py #    通知推送
│   │   │       └── trading_nodes.py #   下单、券商、基本面
│   │   ├── trading/               # 交易引擎 + 券商适配器
│   │   │   └── brokers/           #   富途、Binance、OKX 适配器
│   │   ├── factors/               # Alpha Zoo + GP 进化引擎
│   │   ├── optimize/              # 网格/贝叶斯/随机/滚动窗口/进化
│   │   ├── cache/                 # Redis L0 缓存层
│   │   ├── notify/                # 通知引擎 + 多渠道
│   │   ├── services/              # 市场状态、评分、反思、筛选等
│   │   ├── backend/                 # ReAct Agent 循环、工具、记忆
│   │   ├── skills/                # 89 个领域技能包
│   │   └── api/                   # FastAPI 路由模块（26 个路由）
│   ├── backtest/                  # 数据存储、加载器、市场引擎
│   └── migrations/                # PostgreSQL 迁移脚本（15 个）
├── frontend/                      # React TypeScript 前端
│   └── src/
│       ├── workflow/              # ★ 工作流画布 + Store
│       │   ├── canvas/            #   @xyflow/react DAG 编辑器
│       │   ├── store/             #   Zustand 状态管理
│       │   └── types/             #   TypeScript 类型定义
│       ├── pages/                 # 页面组件
│       ├── components/            # 共享 UI 组件
│       ├── stores/                # Zustand stores
│       └── lib/                   # API 客户端、i18n（中/英/日/韩）、工具
├── .github/workflows/             # CI/CD（Docker 自动发布）
└── docs/                          # 文档
```

## 📄 许可证

MIT License。基于 [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License) 二次开发。
