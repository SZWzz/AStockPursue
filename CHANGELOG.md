# Changelog

## 2026.5.24

### Added

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

AStockPursue 基于 [AStockPursue](https://github.com/HKUDS/AStockPursue) (HKUDS, MIT License) 二次开发。
