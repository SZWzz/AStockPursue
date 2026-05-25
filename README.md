# AStockPursue — AI 量化交易研究平台

基于 [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License) 二次开发。

## 功能

- **统一交易引擎** — 回测和模拟盘共享 `TradingEngine.on_bar()` 执行管道，SignalEngine 策略一次编写、两个场景运行，杜绝回测/实盘行为不一致
- **AI 智能体对话** — 自然语言驱动策略生成、回测、分析，SSE 实时流式输出，87 个技能包覆盖量化全领域，切页不中断
- **策略实验室** — SignalEngine 合约编辑器，K 线图实时回测面板，10 个策略模板，AI 生成策略自动入库，回测历史记录
- **模拟盘交易** — 三栏布局（策略库 + 代码编辑器 + K 线图），实时交易标记叠加，持仓即时更新，月度收益热力图，运行日志 + 信号统计，克隆运行，部署前自动验证
- **指标实验室** — Python 指标 IDE（Monaco 编辑器），K 线图实时回测面板，沙箱安全执行，代码质量分析，Alpha Zoo 因子一键转换，安全 sys 注入
- **Alpha 因子库** — 450+ 量化因子（Alpha101 / GTJA191 / Qlib158），支持用户自定义提升
- **多数据源覆盖** — A股/港股/美股/加密货币/期货/外汇/指数/大宗商品，13 个数据源自动 fallback，Tencent 免费 A 股行情
- **非 OHLCV 数据** — 市场情绪（VIX/DXY/Yield Curve）、基本面增强（PE/PB/ROE）、新闻聚合
- **股票智能搜索** — 腾讯行情 API 动态补全 A 股/港股，美股/加密货币自由输入，代码/名称/拼音匹配
- **自选股面板** — 实时价格 + 涨跌幅（红涨绿跌），点击触发 AI 分析
- **相关性矩阵** — 多市场交叉相关性（Pearson/Spearman），AI 分析 + 保存到会话
- **用户系统** — JWT 登录 / 注册，独立 LLM / 数据源 / Skill 配置，PBKDF2 密码哈希
- **Skill 管理** — 87 个技能包可按用户启用/禁用，支持 ZIP 导入自定义 Skill，每用户独立隔离
- **MCP Server** — 22 个 MCP 工具暴露给 Claude Desktop / Cursor，管理员设置面板
- **用户管理** — Admin 面板查看所有用户，管理员可见全局 Skill 导入
- **PostgreSQL 持久化** — 会话历史、回测结果、策略/指标云端同步，全文搜索，自动增量迁移
- **中英双语** — 全站 i18n 覆盖，100+ 翻译 key，自动检测浏览器语言
- **暗色模式** — 亮/暗主题切换，4 级表面层级系统，CSS 变量驱动
- **红涨绿跌** — `html[lang="zh"]` 自动切换中国行情颜色惯例，K 线/权益/盈亏全覆盖
- **11 个 LLM 供应商** — OpenAI / OpenRouter / DeepSeek / Moonshot / MiniMax / 智谱 / 通义千问 / Gemini / Groq / Ollama

## 技术栈

- **后端**：Python 3.11+ / FastAPI / LangChain / Pandas / PostgreSQL / Pydantic
- **前端**：React 19 / TypeScript / Tailwind CSS / ECharts / Monaco Editor / Zustand
- **数据源**：Tushare / AKShare / yfinance / OKX / CCXT / Tencent / Twelve Data / Finnhub / CoinGecko / Futu / Global Indices / Commodities / Coingecko
- **MCP**：FastMCP / 22 工具暴露
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

如选择自动部署 PG：`docker compose --profile pg up -d --build`

访问 `http://localhost:8899`，admin / admin123 登录，在设置中配置 LLM 和数据源即可使用。

## 项目结构

```
AStockPursue/
├── agent/                  # Python 后端
│   ├── api_server.py       #   FastAPI 主入口
│   ├── mcp_server.py       #   MCP Server（22 工具）
│   ├── backtest/           #   多市场回测引擎 + 加载器注册表
│   ├── papertrade/         #   模拟盘引擎 + 调度器 + 风控（re-export 自 src/trading）
│   ├── src/
│   │   ├── agent/          #   SkillsLoader + ContextBuilder
│   │   ├── api/            #   FastAPI 路由
│   │   ├── auth/           #   JWT 认证 + 用户配置（Token/Skill）
│   │   ├── data/           #   股票代码静态数据
│   │   ├── db/             #   PostgreSQL 连接池 + AES 加密 + 自动迁移
│   │   ├── factors/        #   Alpha 因子注册表 + zoo 目录
│   │   ├── lab/            #   策略/指标实验室（仓库 / 沙箱 / 质量分析）
│   │   ├── session/        #   会话管理（文件 / PG 双存储）
│   │   ├── skills/         #   87 个技能包（SKILL.md）
│   │   ├── swarm/          #   多智能体协作
│   │   ├── tools/          #   22 个 MCP 工具
│   │   └── trading/        #   统一交易引擎（回测/实盘共享 on_bar 管道）
│   └── migrations/         #   数据库迁移（含增量）
├── frontend/               # React 前端
│   └── src/
│       ├── pages/          #   页面（Agent / PaperTrading / IndicatorLab / StrategyLab / AlphaZoo / Settings）
│       ├── components/     #   通用组件（chat / indicator-lab / paper-trading / charts）
│       ├── stores/         #   Zustand 状态管理
│       ├── hooks/          #   自定义 hooks（SSE / 暗色模式）
│       └── lib/            #   工具函数 + i18n（100+ 键）+ API 客户端
├── setup.sh                # 一键初始化脚本
├── docker-compose.yml      # 部署配置（含 PG profile）
├── CHANGELOG.md
└── README.md
```

## License

MIT License. 本项目基于 [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS) 开发。

策略模板 `agent/src/lab/templates.json` 源自 [QuantDinger](https://github.com/QuantDinger/QuantDinger) (Apache License 2.0)。
