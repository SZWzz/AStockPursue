# Changelog

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
