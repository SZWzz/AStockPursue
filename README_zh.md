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
  <img src="https://img.shields.io/badge/MCP工具-35-teal?style=flat-square" alt="MCP 工具">
  <img src="https://img.shields.io/badge/版本-2026.6.1-blueviolet?style=flat-square" alt="版本">
</p>

<h1 align="center">🚀 AStockPursue</h1>
<p align="center"><strong>AI 驱动的量化交易研究平台</strong></p>
<p align="center">
  <sub>自然语言 → 策略生成 → 回测 → 优化 → 模拟盘 — 一站式量化交易</sub>
  <br>
  <sub><a href="README.md">📖 English</a> · <a href="CHANGELOG.md">📋 变更日志</a></sub>
</p>

---

基于 [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License) 二次开发。

> ⚠️ **免责声明**：本软件**仅供研究学习使用**，不构成任何投资建议、理财建议、交易建议或其他任何形式的建议。作者和贡献者对使用本软件所产生的任何交易损失、经济损失或法律后果不承担任何责任。**历史业绩不代表未来表现。投资有风险，交易需谨慎。**

## ✨ 功能

<table>
<tr>
<td width="50%" valign="top">

### 🤖 AI 智能体
- **自然语言策略生成** — 用中英文描述交易想法，AI 自动生成 SignalEngine 代码、运行回测、实时迭代优化
- **SSE 实时流式** — 观察 AI 思考链、工具调用、逐步生成结果全过程
- **89 个技能包** — 覆盖 A 股/加密货币/期权/宏观/风险管理/因子分析/行为金融/市场微观结构等全领域
- **多智能体集群** — 29 个预设团队（量化策略台/宏观论坛/行业轮动等）协同研究
- **持久化记忆** — 基于文件的跨会话记忆系统
- **11 个 LLM 供应商** — OpenAI · OpenRouter · DeepSeek · Moonshot · MiniMax · 智谱 · 通义千问 · Gemini · Groq · Ollama · Anthropic

### 📊 交易 Dashboard 🆕
- **统一交易界面** — 左侧：搜索框 + 自选股 · 右侧：K 线 / 分时图 + 多功能面板
- **股票搜索框** — 自选股顶部内嵌代码/名称/拼音搜索，选中即加入列表，10 秒自动刷新实时价格
- **A 股分时图** — 基于通达信 MooTDX 的每分钟价格轨迹，成交量柱、昨收虚线、午休遮罩、十字光标悬浮提示
- **K 线 / 分时一键切换** — 图表区模式切换，分时模式下显示日期选择器
- **OMS 下单面板** — 市价/限价委托，活跃订单 + 历史订单，一键撤单
- **券商面板** — 富途 OpenD 连接状态、账户信息、持仓表格
- **通知面板** — 按渠道启用/禁用，增删 Webhook/邮件/短信，支持测试发送
- **优化面板** — 网格/随机/贝叶斯搜索，SSE 进度条，结果展示
- **指数滚动条** — 可自定义的顶部指数行情条 + 编辑弹窗

### 🔐 多用户隔离
- **订单 PG 持久化** — `vt_trading_orders` 表，`user_id` 外键，参数化 SQL 防注入，服务重启数据不丢失
- **券商上下文隔离** — 按 `user_id` 缓存独立 `OpenSecTradeContext`，不同用户可连接不同 FutuOpenD 实例
- **WS 订阅隔离** — 每个用户独立的标的订阅集合
- **配置按用户分离** — 通知/指数/优化任务全部校验 ownership

</td>
<td width="50%" valign="top">

### 📈 交易引擎
- **统一交易引擎** — 回测和模拟盘共享同一套 `TradingEngine.on_bar()` 管道，SignalEngine 策略一次编写、两个场景运行
- **模拟盘交易** — 三栏布局（策略库 + 代码编辑器 + K 线图），K 线实时交易标记叠加，月度收益热力图，克隆运行，SSE 实时行情
- **前瞻性偏差防护** — 渐进式信号生成 + 数据截断 + bar 内止损检测 + 开盘价涨跌停判断 + 幸存者偏差警告
- **6 状态 OMS** — PENDING → SUBMITTED → PARTIAL → FILLED / CANCELLED / REJECTED 完整订单生命周期
- **富途券商接入** — 下单/撤单/查单/查持仓/查账户，通过 FutuOpenD 直连
- **告警通知系统** — Webhook（企业微信/钉钉/Discord/Slack）+ SMTP 邮件，止损/止盈/日亏损/回撤/异常 5 类告警

### 🧪 策略 & 指标开发
- **策略实验室** — SignalEngine 合约编辑器，K 线回测含基准对比（β / 信息比率 / 超额收益），可配置滑点，10 个策略模板，回测历史记录
- **指标实验室** — Python 指标 IDE (Monaco)，沙箱安全执行，代码质量分析，Alpha Zoo 因子一键转换
- **自定义模式** — 无代码可视化构建器，下拉框/滑块配置入场出场规则和风控参数，一键编译为代码

### 🧬 因子 & 数据
- **Alpha 因子库** — 450+ 量化因子，4 大家族（Alpha101 / GTJA191 / Qlib158 / Academic），支持用户自定义提升，IC/IR 基准评分
- **23 个数据源** — A 股 / 港股 / 美股 / 加密货币 / 期货 / 外汇 / 指数 / 大宗商品全覆盖
- **A 股 8 源智能回退链** — `mootdx → tushare → eastmoney → tencent → futu → baidu → twelvedata → akshare`，数据范围不足时自动触发回退
- **各源历史深度指南** — mootdx ~2-3年（最快），eastmoney ~10+年（免费长历史），tencent ~10+年（实时行情），tushare 1990-至今（需 Token）
- **三级数据访问** — PG 缓存 → Parquet 本地存储 → API 实时拉取，增量更新 + 健康度感知自动路由
- **非 OHLCV 数据** — 龙虎榜 / 限售解禁 / 融资融券 / 大宗交易 / 资金流（分钟+120日日级） / 强势股题材归因 / 北向资金 / 市场情绪
- **相关性矩阵** — 多市场交叉相关性 (Pearson/Spearman)，AI 分析 + 保存到会话

### 🏗 平台能力
- **用户系统** — JWT 登录/注册，独立 LLM/数据源/Skill 配置，PBKDF2 密码哈希，管理员面板
- **PostgreSQL 持久化** — 会话、消息、回测、策略、指标、订单 — PG 全量持久化，全文搜索，自动增量迁移
- **暗色模式** — 亮/暗主题，CSS 变量表面层级系统
- **红涨绿跌** — `html[lang="zh"]` 自动切换中国行情颜色惯例
- **中英双语** — 170+ i18n 翻译键全覆盖，自动检测浏览器语言
- **圆角卡片 UI** — `rounded-2xl` 圆角卡片 + 间距布局，视觉柔和现代
- **MCP Server** — 31 个 MCP 工具暴露给 Claude Desktop / Cursor 集成
- **移动端适配** — 自适应侧边栏、底部导航栏、触控友好输入框

</td>
</tr>
</table>

### 🧬 AI 因子挖掘 — Phase C: LLM+GP+FactorKB 三位一体 *(重大升级)*
- **遗传规划引擎** — 27 算子 × 3 级渐进解锁（基础→进阶→另类），锦标赛选择，子树交叉变异，混合骨架初始化（30%已知结构+40%变异+30%随机）
- **乘性复合适应度** — `IC × 成本惩罚 × 正交化 × A股特化 × 稳定性 × 复杂度折扣`，一个维度差直接归零
- **A 股特化惩罚** — T+1 日内信号×0.5、年化换手>200×→×0.3、小盘极端暴露×0.7
- **FDR 每代校正** — Benjamini-Hochberg 多重检验校正（q=0.05），每代对全种群执行
- **FactorKB 知识库** — 因子注册/公式哈希去重/语义标签搜索/生命周期状态机（发现→验证→批准→模拟盘→生产→淘汰→归档）
- **LLM 指导进化** — 每 5 代 LLM 分析种群，7 种干预动作（种子注入/主题重定向/变异率调整/去重）；消融实验框架（Baseline vs LLM vs Placebo）验证 LLM 真实贡献
- **表达式树单一真相源** — `formula_hash`/`normalized_formula`/SignalEngine 代码均从同一棵树派生，杜绝公式不一致
- **Walk-Forward 24 窗** — Purged 交叉验证，5 天间隔防止信息泄露，半年度样本外
- **PAPER_TRADING 门禁** — 模拟盘≥21 个交易日验证，换手偏差<1.5×，Sharpe>0.5，正收益
- **三层安全防线** — AST 白名单 → 类型签名校验 → 运行时熔断（512MB/30s）
- **模拟盘验证** — 因子入库前必须通过模拟盘≥21 交易日验证
- **MCP 工具** — `factor_kb_search` / `factor_review` / `factor_mining_start_gp` / `factor_kb_list`
- **演化直播图表** — SSE 实时推送每代 IC 曲线 + KB 注册统计 + 算子解锁进度

### 🔍 智能选股筛选器 *(新增)*
- **多条件筛选** — 450+ Alpha Zoo 因子 + 11 个技术指标作为可筛选字段
- **白名单校验** — 字段名和运算符严格白名单验证，防止注入
- **参数化 SQL** — 安全的 `%s` 占位符查询；`statement_timeout` 超时保护
- **AI 推荐预设** — 基于近期 IC 排名的 Top-N 因子组合
- **批量操作** — 加自选股、导出 CSV、等权组合回测

### 📊 绩效归因 *(新增)*
- **Brinson 归因** — 超额收益分解为配置效应 + 选择效应 + 交互效应（按行业）
- **因子归因** — Alpha Zoo 因子截面回归，因子贡献分解
- **行业归因** — 申万一级行业分类，行业 P&L + 集中度 HHI
- **时间序列分解** — 组合收益的趋势/季节/残差分解

### 🔬 策略量化对比 *(新增)*
- **统计检验** — 配对 t 检验、Bootstrap Sharpe 置信区间（万次采样）、White's Reality Check
- **滚动 Sharpe** — 稳定性分析，双曲线叠加可视化
- **CAPM/FF3 回归** — Jensen's α（含 t 检验）、β、R²
- **收益曲线叠加** — 多策略同图对比

### ⏰ 定时任务 *(新增)*
- **Cron 引擎** — 6 种任务类型：自动回测、数据健康检查、自选股预警、信号报告、因子挖掘、筛选器
- **任务管理面板** — 创建/编辑/暂停/恢复/删除，执行历史 + 日志查看
- **可视化 Cron 构建器** — 下拉菜单式 cron 表达式构建，预览未来执行时间
- **通知集成** — 任务结果通过 webhook/邮件推送

### 📰 新闻情绪分析 *(新增)*
- **中文 NLP** — SnowNLP 情绪打分 + 关键词兜底；0-1 分数 + 正面/中性/负面标签
- **独立舆情页面** — 热门话题排行（情绪加权热度条）、市场情绪仪表盘（VIX/DXY/收益率差/恐慌贪婪指数）、SSE 实时直播资讯流
- **个股情绪聚合** — 单只股票情绪均值/标准差/新闻数量/热度分，基于 DuckDuckGo/Finnhub 实时新闻动态计算
- **热门主题** — 关键词匹配提取（10 大类别：货币政策、新能源、半导体、医药、房地产、AI 等），情绪加权热度排行
- **SSE 实时推送** — 跨工作进程实时新闻推送，基于 PostgreSQL LISTEN/NOTIFY（SSEBus）；支持全市场或单只股票订阅，前端自动重连
- **交易面板增强** — 资讯 Tab 显示单条情绪评分徽章、个股情绪摘要栏（均值/标准差/数量/热度）、SSE 实时指示灯；新文章自动前置插入并 URL 去重

### 🔄 策略版本管理 *(新增)*
- **自动版本记录** — 每次保存生成新版本，含与前版 unified diff
- **Diff 查看器** — ± 行语法着色对比
- **版本对比** — 任选两个版本生成差异
- **一键回退** — 回退到任意历史版本（创建新版本记录）

### 🛒 策略市场 *(新增)*
- **发布/浏览/安装** — 公开发布策略，按市场/分类浏览，一键安装到策略实验室
- **五星评分** — 每用户单次评分，显示均分
- **热度排行** — 安装次数排名

### 📈 期权分析 *(新增)*
- **Black-Scholes 定价** — 解析解 + 完整 Greeks（Δ, Γ, Θ, ν, ρ）
- **二叉树模型** — Cox-Ross-Rubinstein n 步格点定价
- **隐含波动率** — Newton-Raphson 迭代求解
- **波动率曲面** — 跨行权价/到期日的波动率微笑/偏斜

### 🚀 实盘交易桥接 *(新增)*
- **Pre-Flight 检查** — 5 步验证：券商连接、风控配置、策略绩效、仓位限制、账户余额
- **纸盘→实盘提升** — 验证通过的策略一键提升到实盘，附带风控限制
- **强制提升模式** — 受信策略跳过检查

### 🎓 入门向导 *(新增)*
- **6 步引导** — 欢迎 → LLM 配置 → 数据源 → 自选股 → 首个策略 → 完成
- **自动检测** — 检查已有配置，自动跳过已完成步骤
- **可跳过** — 一键跳过，localStorage 记���状态

| 层级 | 技术 |
|-------|-------|
| **后端** | Python 3.11+ · FastAPI · LangChain · Pandas · NumPy · SciPy · PostgreSQL · DuckDB · Pydantic |
| **前端** | React 19 · TypeScript · Tailwind CSS · ECharts · Monaco Editor · Zustand · Vite |
| **数据源** | MooTDX · Tushare · EastMoney · AKShare · Baidu · Tencent · yfinance · OKX · CCXT · Twelve Data · Finnhub · CoinGecko · Futu · Global Indices · Commodities · THS · Northbound · Tiingo |
| **交易** | 统一引擎 · OMS（6 状态）· 富途券商 · 风控管道 · WebSocket 行情 · 告警引擎（Webhook/邮件） |
| **优化** | 网格/随机/贝叶斯搜索 · Walk-Forward · 蒙特卡洛 · Bootstrap · Black-Litterman · VaR/CVaR · 压力测试 |
| **MCP** | FastMCP · 31 工具暴露 |
| **部署** | Docker · Docker Compose |

## 🚀 快速开始

```bash
git clone https://github.com/SZWzz/AStockPursue.git
cd AStockPursue
bash setup.sh                    # 可选择自动部署 PostgreSQL
docker compose up -d --build     # 启动服务
```

> 如需自动部署 PostgreSQL：`docker compose --profile pg up -d --build`

访问 `http://localhost:8899`，`admin` / `admin123` 登录，在设置中配置 LLM 和数据源即可使用。

## 📁 项目结构

```
AStockPursue/
├── agent/                          # Python 后端
│   ├── api_server.py               #   FastAPI 主入口 (v1 API, 14 个路由模块)
│   ├── mcp_server.py               #   MCP Server (31 个工具)
│   ├── backtest/                   #   多市场回测引擎
│   │   ├── engines/                #     各市场引擎 (A股/美股/港股/加密货币/期货)
│   │   ├── loaders/                #     23 个数据源加载器
│   │   ├── optimizers/             #     5 个组合优化器 (MV/RP/MD/EV/BL)
│   │   ├── data_store.py           #     三级数据中心 (缓存 → 存储 → API)
│   │   ├── portfolio_risk.py       #     VaR/CVaR/Kelly/集中度
│   │   ├── stress_test.py          #     6 种预设 + 自定义压力场景
│   │   └── report.py               #     HTML→PDF 报告生成
│   ├── papertrade/                 #   模拟盘引擎 + 调度器 + 风控
│   ├── src/
│   │   ├── agent/                  #   SkillsLoader + ContextBuilder
│   │   ├── api/                    #   14 个 FastAPI 路由模块
│   │   ├── auth/                   #   JWT 认证 + 用户配置加密存储
│   │   ├── db/                     #   PG 连接池 + AES 加密 + 自动迁移
│   │   ├── factors/                #   Alpha 因子注册表 + 4 系列因子库
│   │   ├── lab/                    #   策略/指标实验室 (编译器/仓库/沙箱/质量分析)
│   │   ├── session/                #   会话管理 (PG + 文件双存储)
│   │   ├── skills/                 #   89 个 AI 技能包 (SKILL.md)
│   │   ├── swarm/                  #   多智能体协作预设
│   │   ├── tools/                  #   MCP 工具实现
│   │   ├── notify/                 #   告警引擎 (webhook/邮件, 5 类告警)
│   │   ├── optimize/               #   参数优化 (网格/随机/贝叶斯 + 滚动优化)
│   │   ├── trading/                #   统一引擎 (OMS + 券商/WS 行情/风控管道)
│   │   └── shadow_account/         #   交易日志分析 + 影子账户
│   └── migrations/                 #   数据库迁移 (增量 SQL)
├── frontend/                       # React 前端
│   └── src/
│       ├── pages/                  #   14 个页面 (Agent/Trading/PTP/IndicatorLab/StrategyLab/...)
│       ├── components/             #   7 个组件组 (chat/trading/paper-trading/charts/...)
│       ├── stores/                 #   Zustand 状态管理 (5 个 store)
│       ├── services/               #   API 服务层
│       ├── hooks/                  #   自定义 Hooks (SSE/暗色模式/回测)
│       └── lib/                    #   工具 + i18n (170+ 键) + API 客户端 + 图表主题
├── setup.sh                        # 一键初始化脚本
├── docker-compose.yml              # 部署配置 (含 PG profile)
├── CHANGELOG.md                    # 详细变更日志
├── README.md                       # 英文文档
└── README_zh.md                    # 中文文档
```

## 📄 License

MIT License。基于 [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS) 开发。

策略模板 `agent/src/lab/templates.json` 源自 [QuantDinger](https://github.com/QuantDinger/QuantDinger) (Apache License 2.0)。
