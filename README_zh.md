<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-009688?style=flat&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-14+-4169E1?style=flat&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat" alt="License">
  <img src="https://img.shields.io/badge/Factors-450+-orange?style=flat" alt="Alpha Factors">
  <img src="https://img.shields.io/badge/Data_Loaders-23-blue?style=flat" alt="数据加载器">
  <img src="https://img.shields.io/badge/Version-2026.5.30-blueviolet?style=flat" alt="版本">
</p>

<h1 align="center">AStockPursue</h1>
<p align="center"><strong>AI 驱动的量化交易研究平台</strong></p>
<p align="center"><sub><a href="README.md">English</a></sub></p>

---

基于 [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License) 二次开发。

## 功能

<table>
<tr><td width="50%">

### 交易引擎
- **统一交易引擎** — 回测和模拟盘共享 `TradingEngine.on_bar()` 执行管道，SignalEngine 策略一次编写、两个场景运行
- **模拟盘交易** — 三栏布局（策略库 + 代码编辑器 + K 线图），K 线实时交易标记叠加，月度收益热力图，克隆运行，数据源标识
- **前瞻性偏差防护** — 渐进式信号生成 + 数据截断 + bar 内止损检测 + 开盘价涨跌停判断 + 幸存者偏差警告

### AI 智能体
- **AI 对话** — 自然语言驱动策略生成、回测、分析，SSE 实时流式输出，89 个技能包覆盖量化全领域
- **AI 代码生成** — 代码编辑器下方可折叠对话面板，输入需求直接生成代码并写入编辑器，自动保存同步列表
- **MCP Server** — 31 个 MCP 工具暴露给 Claude Desktop / Cursor，管理员设置面板

### 策略 & 指标开发
- **策略实验室** — SignalEngine 合约编辑器，K 线实时回测含基准对比（β / 信息比率 / 超额收益），可配置滑点，10 个策略模板，回测历史记录
- **指标实验室** — Python 指标 IDE (Monaco)，沙箱安全执行，代码质量分析，Alpha Zoo 因子一键转换
- **自定义模式** — 无代码可视化构建器，下拉框/滑块配置入场出场规则和风控参数，一键编译为代码

</td><td width="50%">

### 因子 & 数据
- **Alpha 因子库** — 450+ 量化因子 (Alpha101 / GTJA191 / Qlib158 / Academic)，支持用户自定义提升
- **多数据源** — A股/港股/美股/加密货币/期货/外汇/指数/大宗商品，23 个数据源，A 股 8 源回退链 (`mootdx→tushare→eastmoney→tencent→futu→baidu→twelvedata→akshare`)
- **PG 缓存 + Parquet 存储** — 三级数据访问 (缓存 → 本地存储 → API)，增量更新，健康度感知自动路由
- **非 OHLCV 数据** — 龙虎榜 / 限售解禁 / 融资融券 / 大宗交易 / 资金流 / 强势股题材归因 / 北向资金 / 市场情绪 / 基本面 / 新闻聚合
- **相关性矩阵** — 多市场交叉相关性 (Pearson/Spearman)，AI 分析 + 保存到会话

### 平台能力
- **用户系统** — JWT 登录/注册，独立 LLM/数据源/Skill 配置，PBKDF2 密码哈希，管理员面板
- **PostgreSQL 持久化** — 会话历史、回测结果、策略/指标云端同步，全文搜索，自动增量迁移
- **暗色模式** — 亮/暗主题切换，4 级表面层级 CSS 变量
- **红涨绿跌** — `html[lang="zh"]` 自动切换中国行情颜色惯例
- **中英双语** — 全站 i18n 覆盖，自动检测浏览器语言
- **圆角卡片 UI** — 页面分隔采用 `rounded-2xl` 圆角卡片 + 间距布局，视觉柔和现代
- **11 个 LLM 供应商** — OpenAI / OpenRouter / DeepSeek / Moonshot / MiniMax / 智谱 / 通义千问 / Gemini / Groq / Ollama

</td></tr>
</table>

## 技术栈

| 层级 | 技术 |
|------|------|
| **后端** | Python 3.11+ · FastAPI · LangChain · Pandas · NumPy · SciPy · PostgreSQL · DuckDB · Pydantic |
| **前端** | React 19 · TypeScript · Tailwind CSS · ECharts · Monaco Editor · Zustand · Vite |
| **数据源** | Tushare · MooTDX · EastMoney · AKShare · Baidu · Tencent · yfinance · OKX · CCXT · Twelve Data · Finnhub · CoinGecko · Futu · Global Indices · Commodities · THS · Northbound · Tiingo |
| **交易** | OMS（6 状态订单生命周期）· 富途券商 · 风控管道 · WebSocket 行情 · 告警通知（Webhook/邮件） |
| **优化** | 网格/随机/贝叶斯搜索 · Walk-Forward · 蒙特卡洛 · Black-Litterman · VaR/CVaR · 压力测试 |
| **MCP** | FastMCP · 31 工具暴露 |
| **部署** | Docker · Docker Compose |

## 快速开始

```bash
git clone https://github.com/SZWzz/AStockPursue.git
cd AStockPursue
bash setup.sh                    # 可选择自动部署 PostgreSQL
docker compose up -d --build     # 启动服务
```

> 如需自动部署 PostgreSQL：`docker compose --profile pg up -d --build`

访问 `http://localhost:8899`，`admin` / `admin123` 登录，在设置中配置 LLM 和数据源即可。

## 项目结构

```
AStockPursue/
├── agent/                     # Python 后端
│   ├── api_server.py          #   FastAPI 主入口 (v1 API)
│   ├── mcp_server.py          #   MCP Server (31 工具)
│   ├── backtest/              #   多市场回测引擎 + 23 加载器 + DataStore
│   │   ├── loaders/            #     23 个数据源 (mootdx/eastmoney/tushare/...)
│   │   ├── optimizers/         #     5 个投资组合优化器 (MV/RP/MD/EV/BL)
│   │   ├── data_store.py       #     统一数据中心 (缓存 → 存储 → API)
│   │   ├── portfolio_risk.py   #     VaR/CVaR/Kelly/集中度
│   │   ├── stress_test.py      #     6 种预设 + 自定义压力场景
│   │   └── report.py           #     PDF 报告生成
│   ├── papertrade/            #   模拟盘引擎 + 调度器 + 风控
│   ├── src/
│   │   ├── agent/             #   SkillsLoader + ContextBuilder
│   │   ├── api/               #   FastAPI 路由 (12 模块)
│   │   ├── auth/              #   JWT 认证 + 用户配置加密存储
│   │   ├── db/                #   PG 连接池 + AES 加密 + 自动迁移
│   │   ├── factors/           #   Alpha 因子注册表 + zoo (4 系列)
│   │   ├── lab/               #   策略/指标实验室 (编译器/仓库/沙箱/质量分析)
│   │   ├── session/           #   会话管理 (PG + 文件双存储)
│   │   ├── skills/            #   89 个技能包 (SKILL.md)
│   │   ├── swarm/             #   多智能体协作
│   │   ├── tools/             #   MCP 工具实现
│   │   ├── notify/            #   告警引擎 (webhook/邮件, 5 类告警)
│   │   ├── optimize/          #   参数优化 (网格/随机/贝叶斯 + 滚动优化)
│   │   └── trading/           #   统一引擎 (OMS + 券商/WS 行情/风控管道)
│   └── migrations/            #   数据库迁移 (增量)
├── frontend/                  # React 前端
│   └── src/
│       ├── pages/             #   页面 (Agent/PTP/IndicatorLab/StrategyLab/AlphaZoo/Settings...)
│       ├── components/        #   组件 (chat/indicator-lab/paper-trading/charts/layout)
│       ├── stores/            #   Zustand 状态管理
│       ├── hooks/             #   自定义 Hooks (SSE/暗色模式/回测)
│       └── lib/               #   工具 + i18n (150+ 键) + API 客户端
├── setup.sh                   # 一键初始化
├── docker-compose.yml         # 部署配置 (含 PG profile)
├── CHANGELOG.md               # 变更日志
├── README.md                  # 英文文档
└── README_zh.md               # 中文文档
```

## License

MIT License. 基于 [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS) 开发。

策略模板 `agent/src/lab/templates.json` 源自 [QuantDinger](https://github.com/QuantDinger/QuantDinger) (Apache License 2.0)。
