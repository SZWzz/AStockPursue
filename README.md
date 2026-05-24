# AStockPursue — AI 量化交易研究平台

基于 [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License) 二次开发。

## 功能

- **AI 智能体对话** — 自然语言驱动策略生成、回测、分析，SSE 实时流式输出
- **策略实验室** — SignalEngine 合约编辑器，多标的组合回测，AI 生成策略自动保存
- **指标实验室** — Python 指标 IDE（Monaco 编辑器），沙箱安全执行，代码质量分析
- **Alpha 因子库** — 450+ 量化因子（Alpha101 / GTJA191 / Qlib158）
- **自选股面板** — 实时价格 + 涨跌幅（Tushare 优先），点击触发 AI 分析
- **相关性矩阵** — A 股 / 港股 / 美股 / 加密货币交叉相关性，支持 AI 分析 + 保存到会话
- **用户系统** — JWT 登录 / 注册，独立 LLM 和数据源配置，密钥 AES-256-GCM 加密
- **用户管理** — Admin 面板查看所有用户 LLM / Tushare 配置状态
- **PostgreSQL 持久化** — 会话历史、回测结果、指标 / 策略云端同步，全文搜索
- **11 个 LLM 供应商** — OpenAI / OpenRouter / DeepSeek / Moonshot / MiniMax / 智谱 / 通义千问 / Gemini / Groq / Ollama

## 技术栈

- **后端**：Python 3.11+ / FastAPI / LangChain / LangGraph / Pandas / PostgreSQL
- **前端**：React 19 / TypeScript / Tailwind CSS / ECharts / Monaco Editor
- **数据源**：Tushare / AKShare / yfinance / OKX / CCXT
- **部署**：Docker / Docker Compose

## 前置要求

- **PostgreSQL 14+** — 存储用户、会话、回测结果、自选股等数据
- **Docker & Docker Compose** — 容器化部署
- （可选）Tushare Token — A 股数据

## 快速开始

```bash
git clone https://github.com/SZWzz/AStockPursue
cd AStockPursue
bash setup.sh                # 可选择自动部署 PostgreSQL
docker compose up -d --build
```

如选择自动部署 PG：`docker compose -f docker-compose.yml -f docker-compose.pg.yml up -d --build`

访问 `http://localhost:8899`，admin / admin123 登录，在设置中配置 LLM 和数据源即可使用。

## 项目结构

```
AStockPursue/
├── agent/             # Python 后端
│   ├── backtest/      #   多市场回测引擎
│   ├── src/lab/       #   策略 / 指标实验室
│   ├── src/auth/      #   JWT 认证
│   ├── src/db/        #   PostgreSQL 连接池 + AES 加密
│   ├── src/api/       #   FastAPI 路由
│   └── migrations/    #   数据库迁移
├── frontend/          # React 前端
│   └── src/
│       ├── pages/     #   页面组件
│       ├── components/#   通用组件
│       ├── stores/    #   Zustand 状态管理
│       └── lib/       #   工具函数 + i18n
├── setup.sh           # 一键初始化脚本
└── docker-compose.yml
```

## License

MIT License. 本项目基于 [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS) 开发。

策略模板 `agent/src/lab/templates.json` 源自 [QuantDinger](https://github.com/QuantDinger/QuantDinger) (Apache License 2.0)。
