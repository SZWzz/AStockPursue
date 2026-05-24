# AStockPursue — AI 量化交易研究平台

基于 [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License) 二次开发。

## 功能

- **AI 智能体对话** — 自然语言驱动策略生成、回测、分析，SSE 实时流式输出，策略自动保存至实验室
- **策略实验室** — SignalEngine 合约编辑器，多标的组合回测，AI 生成策略自动入库，PG/文件双存储
- **模拟盘交易** — 完整 Paper Trading 引擎，SignalEngine 策略驱动，SSE 实时行情，风控管理（止损/止盈/追迹止损），权益曲线可视化，持仓/成交记录
- **指标实验室** — Python 指标 IDE（Monaco 编辑器），沙箱安全执行，代码质量分析，Alpha Zoo 因子一键转换
- **Alpha 因子库** — 450+ 量化因子（Alpha101 / GTJA191 / Qlib158），支持用户自定义提升
- **多数据源覆盖** — A股/港股/美股/加密货币/期货/外汇/指数/大宗商品，Tencent/Global Indices/Commodities/CoinGecko/Twelve Data/Finnhub 等 10+ 加载器，自动 fallback 链
- **非 OHLCV 数据** — 市场情绪（VIX/DXY/Yield Curve）、基本面增强（PE/PB/ROE）、新闻聚合，支撑多维量化分析
- **股票自动联想** — A 股 / 港股 / 指数智能搜索，代码、名称、拼音匹配，回测 + 相关性矩阵全接入
- **自选股面板** — 实时价格 + 涨跌幅（Tushare 优先），点击触发 AI 分析
- **相关性矩阵** — 多市场交叉相关性计算（Pearson/Spearman），智能股票输入，AI 分析 + 保存到会话
- **用户系统** — JWT 登录 / 注册，独立 LLM 和数据源配置，PBKDF2 密码哈希
- **用户管理** — Admin 面板查看所有用户 LLM / Tushare 配置状态
- **PostgreSQL 持久化** — 会话历史、回测结果、指标 / 策略云端同步，全文搜索
- **中英双语** — 全站 i18n 覆盖，46+ 翻译 key，自动检测浏览器语言
- **暗色模式** — 亮/暗主题切换，4 级表面层级系统，CSS 变量驱动
- **11 个 LLM 供应商** — OpenAI / OpenRouter / DeepSeek / Moonshot / MiniMax / 智谱 / 通义千问 / Gemini / Groq / Ollama

## 技术栈

- **后端**：Python 3.11+ / FastAPI / LangChain / LangGraph / Pandas / PostgreSQL
- **前端**：React 19 / TypeScript / Tailwind CSS / ECharts / Monaco Editor / Zustand
- **数据源**：Tushare / AKShare / yfinance / OKX / CCXT / Tencent / Twelve Data / Finnhub / CoinGecko / Global Indices / Commodities
- **部署**：Docker / Docker Compose

## 前置要求

- **PostgreSQL 14+** — 存储用户、会话、回测结果、自选股等数据
- **Docker & Docker Compose** — 容器化部署
- （可选）Tushare Token — A 股数据

## 快速开始

```bash
git clone https://github.com/SZWzz/AStockPursue.git
cd AStockPursue
bash setup.sh                # 可选择自动部署 PostgreSQL
docker compose up -d --build
```

如选择自动部署 PG：`docker compose -f docker-compose.yml -f docker-compose.pg.yml up -d --build`

访问 `http://localhost:8899`，admin / admin123 登录，在设置中配置 LLM 和数据源即可使用。

## 项目结构

```
AStockPursue/
├── agent/                  # Python 后端
│   ├── api_server.py       #   FastAPI 主入口
│   ├── backtest/           #   多市场回测引擎
│   ├── src/
│   │   ├── api/            #   FastAPI 路由（indicator-lab / strategy-lab / alpha / stock）
│   │   ├── auth/           #   JWT 认证 + PBKDF2 密码哈希
│   │   ├── core/           #   核心引擎
│   │   ├── data/           #   股票代码静态数据
│   │   ├── db/             #   PostgreSQL 连接池 + AES 加密
│   │   ├── factors/        #   Alpha 因子注册表 + zoo 目录
│   │   ├── lab/            #   策略/指标实验室（仓库 / 沙箱 / 质量分析）
│   │   ├── session/        #   会话管理（文件 / PG 双存储）
│   │   └── tools/          #   工具集
│   └── migrations/         #   数据库迁移
├── frontend/               # React 前端
│   └── src/
│       ├── pages/          #   页面组件（Agent / IndicatorLab / StrategyLab / AlphaZoo / Correlation / Settings）
│       ├── components/     #   通用组件（chat / indicator-lab / layout / charts）
│       ├── stores/         #   Zustand 状态管理
│       ├── hooks/          #   自定义 hooks（SSE / 暗色模式）
│       └── lib/            #   工具函数 + i18n（中英双语）+ API 客户端
├── setup.sh                # 一键初始化脚本
├── docker-compose.yml      # 主部署配置
├── docker-compose.pg.yml   # PG 容器配置
└── CHANGELOG.md
```

## License

MIT License. 本项目基于 [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS) 开发。

策略模板 `agent/src/lab/templates.json` 源自 [QuantDinger](https://github.com/QuantDinger/QuantDinger) (Apache License 2.0)。
