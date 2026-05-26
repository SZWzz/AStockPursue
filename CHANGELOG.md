# Changelog

## 2026.5.26

### Added

- **自定义模式（可视化策略/指标构建器）** — 策略实验室和指标实验室新增「自定义模式」按钮，弹出 VisualBuilder 模态面板，通过下拉框/滑块/开关可视化配置入场/出场规则、风控参数，编译为 Python 代码并加载到编辑器。策略实验室新增 `/v1/strategy-lab/compile` 端点，compiler 新增 `compile_signal_engine()` 函数
- **AI 对话面板** — 代码编辑器下方新增可折叠 AiChatPanel，用户输入自然语言描述，AI 流式生成代码直接写入编辑器，完成后自动保存并同步右侧列表。后端内置策略/指标合约系统提示词，无需用户手动编写
- **圆角卡片式页面布局** — 新增 `.section-card` CSS 类，页面分隔从硬边框 (`border-b`/`border-l`) 改为 `rounded-2xl border shadow-sm` 圆角卡片 + `gap-3 p-3` 间距，视觉更柔和

### Changed

- **AI Generate 按钮移除** — 页面头部的「AI 生成」按钮已由 AiChatPanel 替代，减少按钮拥挤
- **侧边栏折叠状态持久化** — 两个实验室的侧边栏折叠状态写入 localStorage，切换页面不再丢失
- **侧边栏列表滚动位置保持** — 点击列表项后不再跳回顶部，useLayoutEffect 自动恢复滚动位置
- **两个实验室标签汉化** — ChartPanel 中 Symbol→标的、Start→开始、End→结束、Source→数据源、Interval→周期、Load Data→加载数据、初始资金→ptInitialCapital（支持中英切换）
- **回测「Equity & Drawdown」汉化** — 硬编码英文替换为 i18n `equityDrawdown` 键（净值与回撤）
- **会话列表空标题** — 新建会话不再显示裸 hex id（`c50f2760bf14`），改为「未命名 #c50f2760」
- **未输入标的前端禁用回测按钮** — ChartPanel 中 symbol 为空时「加载数据」和「运行回测」按钮置灰不可点击
- **相关性矩阵移除「API 文档与指南」按钮**
- **策略实验室默认代码模板汉化** — docstring、注释从英文翻译为中文
- **i18n 新增 ~30 个键** — aiChat*、customMode、visualBuilder*、chartLoadData、unnamedSession、cancel 等

### Fixed

- **Alpha 因子库调用报错修复** — indicator_lab_routes.py 生成的代码中 `df["close"]`（Series）改为 `df[["close"]]`（单列 DataFrame），修复 `'Series' object has no attribute 'columns'` 错误，alpha 因子的 `compute()` 函数不再崩溃

- **回测引擎前瞻性偏差（4 项改进）** — 审计发现策略可通过 `generate()` 访问未来数据，导致回测虚高
  - **Fast 模式渐进式信号生成** — `_run_fast()` 将一次性 `generate(data_map)` 替换为逐 bar 扩展窗口调用，策略在时点 T 只能看到 `data[0..T]`，从根源消除未来数据泄漏
  - **Simulation 模式数据截断** — `on_bar_batch()` 重排序：先 `generate()` 再追加新 bar，策略看不到当前 bar 数据，与 `_align()` shift(1) 语义一致
  - **止损/止盈支持 bar 内高低价** — `RiskPipeline` 新增 `check_position_intraday()` 方法，使用 bar high/low 检测止损/止盈在 bar 内触及，跳空以开盘价成交；优先级：止损 > 追迹止损 > 止盈
  - **开盘价涨跌停判断** — `ChinaAEngine.can_execute()` 新增 open-based 涨跌停检查，开盘即封板时直接阻止交易，避免用收盘价判断但开盘价执行的时机不一致
- **MCP 服务器设计缺陷（5 项修复）**
  - `run_swarm` 移除 360×5s 轮询阻塞，立即返回 run_id，通过 `get_swarm_status`/`get_run_result` 异步查询
  - `write_file`/`read_file` 新增 `run_dir` 参数，默认工作目录 `~/.AStockPursue/workspace/`，修复文件操作完全失效的问题
  - `_run_sync` 替换为持久后台事件循环 `_get_mcp_loop()`，避免每次 MCP 调用创建新线程
  - `_unresolved` 返回格式从 `[code]` 升级为 `[{code, reason}]`，不再静默吞掉错误原因
  - MCP 配置文件写入后 `chmod 0o600`，防止凭证泄露

### Changed

- **Lab 模块重组** — `sandbox.py` 移至 `src/security/`，`repository.py`/`pg_repository.py` 移至 `src/lab/storage/`，`alpha_bench_store.py` 新建于 `src/db/`
- **Docker Compose 合并** — `docker-compose.pg.yml` 合并入 `docker-compose.yml`，通过 `--profile pg` 按需启动 PostgreSQL
- **API 版本化** — 所有路由挂载 `/v1` 前缀，前端 `request()` 统一拼接 `/v1` 前缀
- **前端类型拆分** — API 合约类型从 `lib/api.ts` 提取到独立 `types/api.ts`
- **i18n 新增 AlphaZoo/IndicatorLab 相关 key**
- **前端 UX 全面优化**
  - **回测指标卡片化** — ChartPanel 回测指标从 K 线图底部文字条移至图表上方网格卡片，不会被工具栏按钮遮挡
  - **权益曲线 Y 轴修复** — EquityChart grid 边距从 8px 增至 60px，containLabel 不再与绘图区域重叠
  - **模拟盘代码/预览分离** — PaperTrading `codes` 状态拆分为 `deployCodes`（部署弹窗）和 `previewSymbol`（右侧预览），互不污染
  - **模拟盘快速部署** — 策略库卡片新增「快速部署」按钮，一键填入代码 + 打开部署弹窗
  - **模拟盘克隆修复** — 克隆从 `/v1/runs/{runId}/config` API 读取原始 codes
  - **模拟盘风控保存** — 风控 tab 新增「保存风控配置」按钮，调用 `PUT /v1/runs/{runId}/risk`
  - **模拟盘 SSE 切换** — 切换运行实例时自动断开旧 SSE 连接，避免事件串扰
  - **模拟盘 K 线高度自适应** — 选中运行后 K 线图 220→320px，权益曲线 ResizeObserver 动态撑满
  - **策略实验室移除空壳 Monitor tab** — 删除无实际功能的运行监控面板及跨页面耦合
  - **策略实验室 AI 取消** — 代码生成按钮旁新增取消按钮（AbortController），可中断长时间 SSE 流
  - **策略实验室批量删除** — 删除策略前弹出 confirm 确认，防止误删
  - **useBacktest hook 提取** — PaperTrading/StrategyLab/IndicatorLab 共享回测状态管理，减少 ~200 行重复代码
  - **自选股搜索输入** — WatchlistPanel 纯文本输入替换为 StockInput 组件，支持代码/名称/拼音搜索
  - **自选股实时价格** — 新增 10 秒轮询自动刷新价格，无需手动点刷新
  - **免费数据源卡片** — Settings 页面免费数据源区域加边框卡片 + 内层描边，层级分明

## 2026.5.25

### Added

- **TradingEngine — 统一回测和实盘执行引擎** — 新建 `agent/src/trading/` 包（6 个模块，~1100 行），回测和模拟盘共享同一套 `on_bar()` 管道，SignalEngine 策略一次编写、两个场景运行
  - `TradingEngine` — 统一 `on_bar(bar, ts) → BarResult` 管道：market hooks → 信号生成 → 优化器 → 风控检查 → 状态机约束 → 撮合执行 → 权益快照
  - `SignalAdapter` — 自动检测 batch/tick 模式，batch 模式等价于 `_align()` shift(1)，tick 模式委托 `TickHandler.on_bar()`
  - `BacktestDriver` — 快速模式（预计算权重，回测结果 100% 向后兼容）+ 模拟模式（逐 bar 增量生成，匹配实盘行为）
  - `LiveDriver` — 从 `PaperTradingScheduler` 提取异步实盘循环，连续错误熔断 + 心跳 + 种子历史数据
  - `OptimizerAdapter` — 滚动窗口在线组合优化（Phase 2），支持风险平价等优化器
  - `RiskPipeline` — 从 `papertrade/risk_manager.py` 迁移，止损/止盈/追迹止损/日内亏损限制
  - `FlatStateMachine` — 从 `papertrade/state_machine.py` 迁移，强制 flat→long→flat→short 状态转换
- **回测模拟模式** — `BacktestDriver` 新增 simulation 模式，逐 bar 通过完整 signal pipeline，用于验证策略在真实环境中不会出现未来函数
- **状态代理模式** — `TradingEngine` 通过 property 代理将 capital/positions/trades 读写穿透到 `BaseEngine`，确保 `CryptoEngine.on_bar()` 等子类 hook 看到一致状态

### Changed

- **回测执行路径重组** — `BaseEngine._execute_bars()` / `_rebalance()` / `run_backtest()` 委托给 `BacktestDriver`；`backtest/runner.py` 直接使用 `BacktestDriver.run()`
- **模拟盘调度器简化** — `PaperTradingScheduler` 删除内联轮询循环，委托给 `LiveDriver.run()`，调度器只保留 SSE 推送 + DB 持久化
- **papertrade/ 向后兼容** — `engine.py` / `tick_handler.py` / `risk_manager.py` / `state_machine.py` 改为 re-export，所有外部 import 路径不受影响
- **api_server.py 拆分** — 2650 行巨型文件拆分为 6 个路由模块（runs/sessions/settings/auth/system）+ 共享工具 common.py，缩减 88%
- **API 版本化** — 所有路由挂载 `/v1` 前缀，为未来 API 变更预留空间
- **Docker Compose 合并** — `docker-compose.pg.yml` 合并入 `docker-compose.yml`，通过 `--profile pg` 按需启动 PostgreSQL
- **Lab/ 模块重组** — `sandbox.py` 移至 `src/security/`，`repository.py`/`pg_repository.py` 移至 `src/lab/storage/`，职责更清晰
- **前端类型拆分** — API 合约类型从 `lib/api.ts`（508 行）提取到独立 `types/api.ts`（~290 行）
- **SSE 管理统一** — 提取 `lib/sseClient.ts` 共享工具（LRU 去重 + 指数退避重连），`useSSE` hook 和 `paperTradingStore` 统一使用
- **前端 request() 去重** — `services/paperTrading.ts` 删除重复的 `request()` 实现，改用 `lib/api.ts` 导出

### Fixed

- **user_id 硬编码** — 26 处 `auth.get("user_id", 1)` 防御性回退替换为 `auth["user_id"]`，由 `require_auth` 保证存在
- **auth 端点速率限制** — `/api/auth/login` 和 `/register` 增加内存滑动窗口限流（5 次/分钟），防暴力破解

### Added

- **前端测试基础设施** — vitest + testing-library + jsdom，3 个测试文件 17 个测试用例（api/apiAuth/StockInput）

## 2026.5.24 (evening)

### Added

- **Skill 管理** — Settings 页面新增「Skill 管理」区块，按类别分组展示 87 个技能包，每用户可独立启用/禁用，下次 AI 对话生效，互不影响
- **MCP 服务设置（admin）** — Settings 页面新增「MCP 服务设置」区块，仅管理员可见，显示服务状态/传输模式/端口/Shell 工具开关，自动生成 Claude Desktop 配置示例
- **Skill 导入安装** — 支持上传 .zip 文件导入自定义 Skill 到 `~/.AStockPursue/skills/{user_id}/`，每用户隔离，管理员可查看全局
- **模拟盘策略库** — 左侧面板新增「策略库」tab，可从策略实验室 / AI 聊天会话导入策略代码，一键部署到模拟盘
- **模拟盘代码编辑器** — 用 Monaco Editor 替换纯文本 textarea，语法高亮 + 代码补全
- **模拟盘 K 线预览** — 右侧面板输入标的代码即可预览 K 线图（即使未创建运行），复用 CandlestickChart
- **模拟盘部署前验证** — 点部署自动调 `/strategy-lab/verify` 验证代码，不通过则弹错误提示，不创建运行
- **模拟盘自动启动** — 部署弹窗新增「部署后自动启动」checkbox，默认勾选
- **模拟盘 K 线交易标记** — SSE `"trade"` 事件新增 `entry_time`/`exit_time`，前端实时叠加 BUY/SELL 箭头到 K 线图
- **模拟盘持仓实时更新** — SSE `"bar"` 事件新增 `positions` 数组，前端无需轮询即可实时刷新持仓表
- **模拟盘快速回测** — 右侧面板「快速回测」按钮，用当前代码 + 标的直接跑历史回测，指标条即时显示
- **模拟盘收益统计卡片** — 4 列网格显示当日收益/累计收益/年化收益/最大回撤，前端实时计算
- **模拟盘月度收益热力图** — 红色=盈利/绿色=亏损，深浅代表幅度，一目了然
- **模拟盘运行日志** — SSE `"signal"` 事件实时推送信号触发记录 + 成交记录
- **模拟盘信号统计** — 做多/做空信号数、胜率、总交易、持仓一览
- **模拟盘克隆运行** — PaperTradingCard 新增「复制」按钮，一键克隆策略 + 配置
- **模拟盘右侧 Tab 切换** — 持仓/成交/日志/统计/风控 5 个 tab
- **回测指标条** — ChartPanel 回测完成后在 K 线图上方显示总收益/年化/夏普/最大回撤/胜率/交易/终值/盈亏比/基准/超额
- **初始资金输入框** — ChartPanel 控制栏新增初始资金输入框，回测时随请求发送
- **设置页面免费数据源状态** — 展示 AKShare/YFinance/Tencent/CCXT/CoinGecko/Futu/Global Indices/Commodities 8 个免费数据源的可用/不可用状态
- **设置页面移除 env_path** — 不再显示「保存至: agent/.env」，token 已完全走数据库 + 中间件注入
- **红涨绿跌全项目覆盖** — 新增 `--up`/`--down` CSS 变量，`html[lang="zh"]` 自动切换红涨绿跌，14 个前端文件 + 4 个后端文件全面替换方向性颜色
- **i18n 新增 60+ 键** — 覆盖 Agent 首页、RunDetail 面板、Compare 指标表、模拟盘全套、Skill 管理、MCP 设置
- **股票搜索增强** — 腾讯行情 API（qt.gtimg.cn）动态补全 A 股/港股代码，美股/加密货币自由输入兜底
- **StockInput 自由输入** — Enter/失焦自动接受不在搜索列表里的股票代码（如 AAPL.US、BTC-USDT）

### Changed

- **Token 集中加载** — `load_user_config()` 移入 `require_auth` 鉴权中间件，所有鉴权端点自动注入用户数据源凭证
- **模拟盘三栏布局** — 从两栏改为三栏（策略库/运行列表 | 代码编辑器 | K 线图 + 运行状态）
- **回测报告卡片始终显示** — SSE 实时路径去掉 `hasMetrics` 门槛，回测完成即显示「查看完整报告」链接
- **AI 对话跨页面保持运行** — 切换到其他页面不再断开 SSE，后端 agent 继续执行，切回自动重连
- **JSON 解析错误信息改进** — 显示请求路径 + 响应内容前 150 字符 + HTML 提示
- **数据源下拉列表补齐** — 前端从 4 项扩充到 13 项，与后端 LOADER_REGISTRY 完全对齐
- **Favicon 重设计** — 蓝色圆角背景 + 上升柱形图 + 趋势箭头
- **沙箱 import 白名单扩充** — 新增 `typing`/`re`/`warnings`/`dataclasses`/`enum`/`abc` 6 个安全标准库
- **沙箱注入安全 sys** — `sys.maxsize`/`float_info`/`version_info` 等只读属性直接注入，AI 代码无需 `import sys`
- **回测 interval 正则扩展** — 后端验证增加 `1W`/`4W`，前端下拉同步补上
- **SkillsLoader 每用户隔离** — 支持 `user_id` + `disabled_skills` 参数，用户技能目录 `~/.AStockPursue/skills/{user_id}/`
- **数据库自动增量迁移** — `init_database()` 自动执行 `migrations/` 目录下所有 `.sql` 文件

### Fixed

- **TUSHARE_TOKEN 配置被反转清除** — Settings 保存时条件取反，真实 token 反而被 `os.environ.pop` 删除
- **Tencent loader 大小写** — `normalize_cn_code`/`normalize_hk_code` 返回大写代码，API 只接受小写
- **fetch_ohlcv 最小行数阈值** — `>=30` 行要求导致 1 个月内约 21 个交易日的数据被丢弃，改为 `>=5`
- **策略沙箱 `__import__` 缺失** — `_execute_strategy_code` 手工构建 `__builtins__` 漏掉 `__import__` 和 `__build_class__`
- **`indicator_series` 嵌套结构** — 后端返回 `{symbol: {name: points}}` 嵌套格式，CandlestickChart 期望 `{name: points}`，未提取第一层导致 `.map()` 崩溃
- **回退链 loader 初始化异常未捕获** — `_fetch_auto` legacy fallback 和 runtime fallback 中 `LoaderCls()` 无 try/catch
- **admin 路由路径不匹配** — 后端 `/api/admin/users`，前端调 `/admin/users`，SPA catch-all 返回 index.html
- **回测历史不记录** — ChartPanel 替换旧弹窗后 localStorage 写入逻辑丢失
- **ChartPanel 不显示策略名称** — 新增 `title` prop，从侧边栏/模板/AI 生成/保存时自动设置
- **StockInput 不允许自由输入代码** — Enter/失焦仅接受搜索结果，不在列表里的美股/加密货币无法输入

## 2026.5.24

### Added

- **股票自动联想** — A股/港股/指数 智能搜索，支持代码/名称/拼音，指标实验室、策略实验室、相关性矩阵全接入
- **Alpha Zoo → 指标实验室转换** — 内置因子一键转换为指标格式，支持直接回测
- **策略实验室 PG 优先** — 自动检测 PostgreSQL 可用性，优先使用 PG 存储，fallback 到文件系统
- **Alpha Zoo 合并扫描** — 同时扫描内置 zoo 和 `~/.AStockPursue/zoo/`，指标实验室提升的因子可在大盘中显示
- **国际化补齐** — Login、PostLoginSetup、UserManagement、Correlation、WelcomeScreen 全部接入 i18n（46 个新 key）
- **多用户并发安全加固** — 文件存储原子写入（`mkstemp` + `os.replace`）+ JSONL 追加文件锁（`fcntl.flock`）+ 仓库单例双重检查锁
- **模拟盘交易** — 完整 Paper Trading 引擎，SignalEngine 策略驱动，SSE 实时行情推送，风控管理（止损/止盈/追迹止损/日内止损），权益曲线可视化，持仓/成交记录，PG 持久化
- **多数据源扩展** — 新增 Tencent（A股/港股）、Global Indices（全球指数）、Commodities（大宗商品）、CoinGecko（加密货币）、Twelve Data（全球全市场）、Finnhub（美股）6 个数据加载器
- **非 OHLCV 数据支持** — 市场情绪（VIX/DXY/Yield Curve）、基本面增强（PE/PB/ROE）、新闻聚合（搜索+财经日历）3 类新数据能力
- **Twelve Data / Finnhub / Tiingo API 配置** — Settings 页面新增付费 API 密钥配置区，后端加密存储 + 环境变量注入
- **数据路由策略重写** — SKILL.md 全面升级，OHLCV / 非OHLCV 数据源矩阵、分市场优先级决策树、index/commodity 新市场类型
- **新工具 + 技能包** — 市场概览、新闻聚合、市场情绪 3 个新工具，对应 6 个新技能包（coingecko/commodities/fundamentals-enhanced/global-indices/news-aggregation/sentiment/tencent/twelvedata）

### Changed

- **全局 UI 重构** — 字号体系（text-xs→text-sm）、间距系统、按钮层级（btn-primary/secondary/ghost/outline）、卡片阴影、Tab 选中态
- **侧边栏重设计** — 品牌 Logo 橙色圆角底色、导航项 rounded-lg 激活态、会话列表呼吸感、Footer 排版优化
- **页面头部统一** — page-header 组件类、图标底色块、描述副文字
- **回退链全面增强** — A股增加 tencent/twelvedata，美股增加 twelvedata/finnhub，港股增加 tencent，加密货币增加 coingecko，新增 index/commodity 市场类型
- **Tailwind 配置增强** — boxShadow CSS 变量（亮/暗自适应）、fade-in/slide-in-right/scale-in 动画
- **IndicatorLab 页面** — 按钮体系替换、Tab 样式统一、空态引导、Alpha Zoo 标签页
- **StrategyLab 页面** — 同上 + 通知卡片/运行日志/历史记录样式升级
- **Agent 聊天页** — 空态居中 Logo、输入框圆角阴影、发送按钮 active:scale 反馈
- **Settings 页面** — 卡片 shadow-sm、表单输入框 padding 增大、保存按钮 btn-md
- **BacktestPanel / StrategyBacktestPanel** — StockInput 替换、模态框 backdrop-blur、按钮 btn 体系
- **Correlation 页面** — StockInput 多选替换、raw fetch 切换为 api 模块
- **UserManagement** — 原生 confirm()→内联确认按钮、raw fetch→api 模块、i18n 全接入

### Fixed

- **密码哈希升级** — SHA256→PBKDF2-HMAC-SHA256（600,000 迭代），向后兼容旧格式
- **JWT_SECRET 持久化** — 从 $JWT_SECRET 或 `runtime_root/.jwt_secret` 读取，解决多 worker/重启 密钥不一致
- **Pickle 缓存安全** — SHA256 完整性校验→HMAC-SHA256 签名（防篡改）
- **代码保存安全校验** — Indicator/Strategy Lab 的 `/save` 接口增加 `validate_code_safety()`
- **静默错误吞没** — backtest_store 4 方法、PgSessionStore 3 方法从 silence→raise
- **死代码移除** — strategy_lab_routes 永真 `has_return` 变量
- **子进程崩溃诊断** — sandbox.py 非零 exit code 时提供更详细错误
- **函数去重** — `_extract_meta_from_code`、`_extract_code_from_response` 统一从 repository.py 导入
- **user_id 硬编码** — Session 模型增加 user_id 字段，PgSessionStore 动态读取
- **module_path 泄露** — alpha 详情 API 移除内部路径
- **ARIA 无障碍** — ConnectionBanner/PostLoginSetup/Login/RunDetail/Correlation 全补全 role/aria-*/htmlFor
- **WelcomeScreen 颜色提取** — 字符串 split 解析→显式 textColor 字段

## 2026.5.24 (earlier)

- **PostgreSQL 自动部署** — `setup.sh` 可选择自动部署 PG 16 Alpine 容器（`docker-compose.pg.yml`），无需手动安装
- **相关性矩阵增强** — 结果 localStorage 持久化、保存到会话、AI 分析按钮
- **回测跳转修复** — Lab 回测后使用 `useNavigate` 客户端路由，解决 401 鉴权问题
- **自选股价格优化** — A 股优先 Tushare，不再依赖 yfinance
- **WatchlistPanel 鉴权修复** — 所有 fetch 调用添加 JWT 认证头

### Changed

- **页面标题 + 描述** — "AStockPursue — AI 量化交易研究平台"
- **登录页汉化** — 全中文界面，移除无效的 Skip 按钮
- **LLM 配置弹窗** — 供应商扩展到 10 个，全中文
- **用户管理增强** — 新增 Tushare 配置状态列
- **示例面板汉化** — 15 个 i18n key 中英双语
- **pyproject.toml** — 更新 authors、urls、dependencies、keywords
- **项目文件更新** — LICENSE、NOTICE、CONTRIBUTING、SECURITY、MANIFEST、CHANGELOG

### Fixed

- **JWT 鉴权合并** — 三个鉴权函数合并为 `require_auth`，Lab 路由补鉴权
- **SSE 事件流鉴权** — 支持 JWT query string，修复登录后无法对话
- **策略自动保存** — 修复 `save_strategy` 名称参数，AI 生成的策略正确显示
- **`logger` 未定义** — `service.py` 添加 logging import
- **JWT_SECRET 持久化** — `.env` 添加固定密钥，解决重启后 token 失效
- **`require_auth` 返回值** — 修复返回 None 导致 `auth.get()` 空指针

## 2026.5.23 — Initial Release

AStockPursue 基于 [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License) 二次开发。
