# AStockPursue 架构统一实施计划

> 2026-06-07 | 基于 optimization-suggestions.md 的重新规划，融入 n8n 工作流视角

---

## 目录

1. [现状审计](#1-现状审计)
2. [Phase 0：回测结果持久化（消灭「跑完就丢」）](#phase-0回测结果持久化消灭跑完就丢)
3. [Phase 1：Service 层统一（消除逻辑双轨）](#phase-1service-层统一消除逻辑双轨)
4. [Phase 2：导航重构（清晰用户心智）](#phase-2导航重构清晰用户心智)
5. [Phase 3：工作流桥接（「导出为工作流」）](#phase-3工作流桥接导出为工作流)
6. [Phase 4：工作流功能补全（新增节点）](#phase-4工作流功能补全新增节点)
7. [Phase 5：增量缓存 + 引擎增强](#phase-5增量缓存--引擎增强)
8. [Phase 6：体验优化 + 渐进收编](#phase-6体验优化--渐进收编)
9. [总时间线](#总时间线)

---

## 1. 现状审计

### 1.1 双轨问题：页面 API vs 工作流节点

页面调用 API → Service/函数，节点直接内联逻辑。**同一个功能有两套实现**：

```
Screener:
  API (screener_routes)   → ScreenerEngine ✅ (多条件过滤、安全白名单、预设管理)
  Node (ScreenerNode)     → sort_values + head  (简单排名，无白名单)

Correlation:
  API (system_routes)     → backtest/correlation.py (独立函数)
  Node (CorrelationNode)  → panel.corr() (内联 pandas)

Sentiment:
  API (news_routes)       → SentimentAnalyzer (NLP、缓存、多源)
  Node (sentiment_nodes)  → 内联逻辑 (简化版)

Indicator/TA:
  API (indicator_lab)     → 完整 lab 系统 (编译、验证、沙箱)
  Node (IndicatorNode)    → 内联 RSI/SMA/BB (内置预设)
```

### 1.2 已有 Service Engine（状态良好）

| Engine | API 调用 | 节点调用 | 状态 |
|---|---|---|---|
| `RegimeEngine` | ✅ | ✅ regime_nodes.py | 完成 |
| `AttributionEngine` | ✅ | ✅ analysis_nodes.py | 完成 |
| `StatisticalTestEngine` | ✅ | ✅ comparison_nodes.py | 完成 |
| `OptionsPricingEngine` | ✅ | ✅ options_nodes.py | 完成 |
| `SchedulerEngine` | ✅ | ✅ scheduler_engine.py | 完成 |

### 1.3 已有 Service 但节点未使用（需修复）

| Engine | API 用 | 节点用 | 问题 |
|---|---|---|---|
| **ScreenerEngine** | ✅ | ❌ | ScreenerNode 有内联简化版 |
| **SentimentAnalyzer** | ✅ | ❌ | sentiment_nodes 有内联版 |

### 1.4 完全缺失 Service（需新增）

| 领域 | 现状 |
|---|---|
| **Correlation** | API 用 `backtest/correlation.py` 独立函数，节点用内联 pandas |
| **Indicator/TA** | API 走 indicator_lab 沙箱系统，节点内联简化版 |

### 1.5 工作流节点覆盖度

| 状态 | 页面数 | 说明 |
|---|---|---|
| ✅ 有对应节点 | 16 | Compare, Correlation, AlphaZoo, IndicatorLab, StrategyLab, PaperTrading, Trading, FactorMining, Screener, Attribution, Options, Sentiment, Scheduler, Agent, RunDetail, Marketplace |
| 🔴 缺失节点 | 2 | Dashboard（本就该独立）、实时行情订阅（LiveDataNode） |
| N/A | 6 | Login, Settings, Projects, DataSourceStatus, Docs, UserManagement |

### 1.6 optimization-suggestions.md 建议 vs 现状对照

| 建议 | 现状 | 修正方向 |
|---|---|---|
| 1.1 参数扫描 | `GridSearchOptimizer` + `ExperimentNode` 已存在 | 只需前端 heatmap 可视化 |
| 1.2 Walk-Forward | `WalkForwardAnalyzer` + `WalkForwardNode` 已存在 | 增加因子重选维度 |
| 1.3 结果对比 | `ComparisonNode` + Compare 页面已存在 | 增加逐笔交易 diff |
| 1.10 一致性校验 | 无 | **新增 ConsistencyCheckNode** |
| 1.5 市场环境分段 | `RegimeNode` + `RegimeEngine` 已存在 | 完善策略族推荐 |
| 1.7 换手率约束 | 无 | **新增 TurnoverConstraintNode** |
| 1.4 成本模型 | 无 | **新增 CostModelNode** |
| 2.3 增量缓存 | 无 | **WorkflowEngine 层增加节点级缓存** |
| 2.7 实盘偏差 | 无 | **新增 LiveMonitorNode** |

### 1.7 回测结果存储现状（🔴 严重缺失）

**表面上有，实际上几乎不可用**。数据库表和 CRUD 函数都已存在，但绝大部分回测路径没有调用。

#### 已有设施

```
PG 数据库:
  vt_backtest_runs     — 回测运行记录（id, config, metrics, status...）
  vt_backtest_equity   — 权益曲线时序数据
  vt_backtest_trades   — 逐笔交易记录

backtest_store.py:
  save_backtest_result()   — 存入 PG
  list_backtest_runs()     — 列出历史
  get_backtest_run()       — 查看单次详情（含权益+交易）
  delete_backtest_run()    — 删除

API 端点（system_routes.py）:
  GET  /api/backtest-history         — 列表接口
  GET  /api/backtest-history/{id}    — 详情接口
  DELETE /api/backtest-history/{id}  — 删除接口
```

#### 谁在调用 save_backtest_result()？

| 回测入口 | 是否存 PG | 结果去哪了 |
|---|---|---|
| **StrategyLab 页面** | ✅ 是（via `lab/strategy_backtest_bridge.py`） | PG |
| **IndicatorLab 页面** | ✅ 是（via `lab/backtest_bridge.py`） | PG |
| **BacktestDriver.run()** | ❌ 否 | 仅写 CSV 到 `run_dir/artifacts/` |
| **BacktestNode（工作流）** | ❌ 否 | 仅 WorkflowStore（不存 trades/equity） |
| **GridSearchOptimizer** | ❌ 否 | 临时目录 `tempfile.mkdtemp`（会被系统回收） |
| **WalkForwardAnalyzer** | ❌ 否 | 临时目录 `tempfile.mkdtemp`（会被系统回收） |
| **ExperimentNode（工作流）** | ❌ 否 | 结果内嵌在 WorkflowStore 的 run JSON 中 |

#### 前端现状

| 前端 | 现状 |
|---|---|
| **回测历史列表页** | **不存在**。没有页面调用 `/api/backtest-history` |
| **RunDetail 页面** | 从文件系统 `RUNS_DIR` 读取（`/runs/{id}`），不走 PG |
| **StrategyLab 页面** | 用 `localStorage` 存了个本地历史（`strategy-lab-backtest-history`），换个浏览器就没了 |
| **api.ts** | 没有 `listBacktestHistory` / `getBacktestHistory` 的客户端函数 |

#### 问题根因

```
用户跑一次回测 → BacktestDriver 写入 run_dir → 返回 metrics dict
                                               ↓
                                     [断链] 从不调用 save_backtest_result()
                                               ↓
                                     PG 表永远是空的（除了从 StrategyLab 跑的）
                                     GridSearch 的临时目录被 OS 清理
                                     前端看不到任何历史
```

这是最影响日常使用的缺陷——**跑完回测就丢了，没法回溯、没法对比、没法复盘**。

---

## Phase 0：回测结果持久化（消灭「跑完就丢」）

**目标**：所有回测路径的结果自动存入 PG，前端有统一的历史浏览页面。

**工期**：5-7 天

### 0.1 BacktestDriver 自动写入 PG

在 `_run_fast()` 和 `_run_simulation()` 的 `_write_artifacts()` 之后，增加 DB 写入：

```python
# backend/src/trading/backtest_driver.py

def run(self, config, loader, signal_engine, run_dir, market_engine,
        bars_per_year=252, *, simulation_mode=False) -> dict:
    ...
    if simulation_mode:
        metrics = self._run_simulation(...)
    else:
        metrics = self._run_fast(...)

    # ── 新增：自动持久化到 PG ──────────────────────────────────
    self._persist_to_db(
        config=config,
        metrics=metrics,
        run_dir=run_dir,
        engine=engine,
    )

    return metrics

def _persist_to_db(self, config, metrics, run_dir, engine):
    """将回测结果写入 vt_backtest_runs 表。"""
    try:
        from src.db.backtest_store import save_backtest_result

        # 从 artifacts 读取权益和交易数据
        artifacts = run_dir / "artifacts"
        equity_curve = self._read_equity_for_db(artifacts / "equity.csv")
        trades = self._read_trades_for_db(artifacts / "trades.csv")

        run_name = config.get("run_name", run_dir.name)
        run_type = config.get("run_type", "strategy")

        save_backtest_result(
            run_name=run_name,
            run_type=run_type,
            config={k: v for k, v in config.items()
                    if not callable(v) and not str(type(v)).startswith("<class")},
            metrics=metrics,
            equity_curve=equity_curve,
            trades=trades,
            status="success",
            user_id=config.get("user_id", 1),
        )
        logger.info("Backtest persisted to PG: %s", run_name)
    except Exception as e:
        logger.warning("Failed to persist backtest to PG (non-fatal): %s", e)
```

### 0.2 GridSearch / WalkForward / BacktestNode 自动继承

因为 `GridSearchOptimizer._run_single()` 和 `WalkForwardAnalyzer._evaluate()` 内部都调用 `BacktestDriver.run()`，只需要在 `BacktestDriver.run()` 中加 `_persist_to_db()`，**所有路径自动覆盖**：

```
BacktestDriver.run()  ← _persist_to_db() 加在这里
  ├── BacktestNode（工作流）        ← ✅ 自动继承
  ├── GridSearchOptimizer           ← ✅ 自动继承
  ├── WalkForwardAnalyzer           ← ✅ 自动继承
  ├── StrategyLab bridge            ← ✅ 自动继承（不再需要 bridge 自己调 save）
  └── 任何直接调用 BacktestDriver 的代码 ← ✅ 自动继承
```

**注意**：GridSearch 和 WalkForward 会产生大量中间回测（几十到几百次）。全部存 PG 会造成噪音。需要增加一个策略：

```python
# GridSearchOptimizer 中
def _run_single(self, config, strategy_code, params):
    config["_db_persist"] = "minimal"  # 只存 metrics，不存 equity/trades
    config["_db_tags"] = ["grid_search", f"combo_{idx}"]
    ...

# BacktestDriver._persist_to_db() 中
if config.get("_db_persist") == "minimal":
    equity_curve = None   # 跳过权益时序数据
    trades = None         # 跳过交易明细
```

### 0.3 前端：回测历史页面（新增）

```tsx
// frontend/src/pages/BacktestHistory.tsx (新文件)

function BacktestHistory() {
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [sortBy, setSortBy] = useState<"sharpe" | "date" | "return">("date");

  useEffect(() => {
    api.listBacktestHistory(100, 0).then(setRuns);
  }, []);

  const sorted = [...runs].sort((a, b) => {
    if (sortBy === "sharpe") return (b.metrics?.sharpe || 0) - (a.metrics?.sharpe || 0);
    if (sortBy === "return") return (b.metrics?.total_return || 0) - (a.metrics?.total_return || 0);
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  return (
    <div>
      <h1>回测历史</h1>
      {/* 排序切换 + 标签筛选 + 搜索 */}
      <table>
        <thead>
          <tr>
            <th>名称</th><th>日期</th><th>Sharpe</th>
            <th>年化收益</th><th>最大回撤</th><th>胜率</th><th>标签</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(run => (
            <tr key={run.id} onClick={() => navigate(`/runs/${run.id}`)}>
              <td>{run.run_name}</td>
              <td>{formatDate(run.created_at)}</td>
              <td className={run.metrics?.sharpe > 1 ? "text-up" : ""}>
                {run.metrics?.sharpe?.toFixed(2)}
              </td>
              ...
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

### 0.4 RunDetail 页面适配 PG

```python
# backend/src/api/runs_routes.py — 增加 PG 回退

@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run_result(run_id: str):
    # 优先尝试 PG
    try:
        from src.db.backtest_store import get_backtest_run
        pg_run = get_backtest_run(run_id)
        if pg_run:
            return build_response_from_pg(pg_run)
    except Exception:
        pass

    # 回退到文件系统（兼容旧 run_id）
    run_dir = RUNS_DIR / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return build_response_from_run_dir(run_dir)
```

### 0.5 补充 `api.ts` 客户端函数

```typescript
// frontend/src/lib/api.ts 新增
listBacktestHistory: (limit = 50, offset = 0) =>
  request<{ runs: BacktestRun[]; total: number }>(
    `/api/backtest-history?limit=${limit}&offset=${offset}`
  ),

getBacktestHistory: (id: string) =>
  request<BacktestRun>(`/api/backtest-history/${id}`),

deleteBacktestHistory: (id: string) =>
  request(`/api/backtest-history/${id}`, { method: "DELETE" }),
```

### 0.6 自动标签（Auto-tagging）

在 `BacktestDriver._persist_to_db()` 中根据 config 自动生成标签：

```python
def _auto_tags(config: dict, metrics: dict) -> list[str]:
    tags = []
    # 市场
    market = config.get("market", "unknown")
    tags.append(f"market:{market}")
    # K线周期
    interval = config.get("interval", "1D")
    tags.append(f"interval:{interval}")
    # 策略来源
    if config.get("_db_tags"):
        tags.extend(config["_db_tags"])
    else:
        tags.append("source:backtest_driver")
    # 性能标签
    sharpe = metrics.get("sharpe_ratio", 0)
    if sharpe > 2:
        tags.append("perf:excellent")
    elif sharpe > 1:
        tags.append("perf:good")
    elif sharpe > 0:
        tags.append("perf:positive")
    else:
        tags.append("perf:negative")
    return tags
```

### 0.7 DB 表增强（微调）

```sql
-- 增加 tags 列（如果还没有）
ALTER TABLE vt_backtest_runs ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}';
CREATE INDEX IF NOT EXISTS idx_bt_runs_tags ON vt_backtest_runs USING GIN(tags);

-- 增加 user_id 索引（已有但确认）
CREATE INDEX IF NOT EXISTS idx_bt_runs_user ON vt_backtest_runs(user_id, created_at DESC);

-- 增加 sharpe 排序索引（列表页按 Sharpe 排序高频使用）
CREATE INDEX IF NOT EXISTS idx_bt_runs_sharpe ON vt_backtest_runs((metrics->>'sharpe_ratio'));
```

### 0.8 侧边栏入口

在 Phase 2 的侧边栏重组中，历史页面已经预留了位置：

```
├── 🔧 策略研发
│   ├── ...
│   ├── 回测历史      ← BacktestHistory 页面（新增）
│   └── ...
```

---

## Phase 1：Service 层统一（消除逻辑双轨）

**目标**：每个计算能力有且仅有一个 Service Engine，页面 API 和工作流节点都调用它。

**工期**：5-7 天

### 1.1 新增 `CorrelationEngine`

```python
# backend/src/services/correlation_engine.py (新文件)
class CorrelationEngine:
    """Cross-asset correlation computation — single source of truth.

    Used by: GET /correlation API + CorrelationNode + CrowdingNode
    """

    def compute_matrix(
        self,
        panel: pd.DataFrame,
        method: str = "pearson",       # pearson | spearman
        lookback: int = 60,
        min_overlap_pct: float = 0.5,
    ) -> CorrelationResult:
        """Compute pairwise correlation matrix from price/factor panel."""
        ...

    def compute_summary(self, matrix: np.ndarray, labels: list[str]) -> CorrelationSummary:
        """Mean/max/min correlation + top pairs."""
        ...
```

**改造范围**：

| 文件 | 改动 |
|---|---|
| `backend/src/services/correlation_engine.py` | **新增** |
| `backend/src/api/system_routes.py:91` | `compute_correlation_matrix()` → `CorrelationEngine` |
| `backend/src/workflow/nodes/correlation_nodes.py` | 删除内联 pandas，调用 `CorrelationEngine` |
| `backend/backtest/correlation.py` | 保留函数签名但内部委托给 `CorrelationEngine`（向后兼容） |

### 1.2 新增 `IndicatorEngine`

```python
# backend/src/services/indicator_engine.py (新文件)
class IndicatorEngine:
    """Technical indicator computation — single source of truth.

    Used by: IndicatorLab API + IndicatorNode
    """

    # 内置指标（纯计算，不涉及沙箱）
    def rsi(self, close: pd.DataFrame, period: int = 14) -> pd.DataFrame: ...
    def macd(self, close: pd.DataFrame, fast: int, slow: int, signal: int) -> MACDResult: ...
    def bollinger(self, close: pd.DataFrame, window: int, num_std: float) -> BollingerResult: ...
    def atr(self, high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame, period: int) -> pd.DataFrame: ...
    def sma(self, close: pd.DataFrame, window: int) -> pd.DataFrame: ...
    def ema(self, close: pd.DataFrame, span: int) -> pd.DataFrame: ...
```

**改造范围**：

| 文件 | 改动 |
|---|---|
| `backend/src/services/indicator_engine.py` | **新增** |
| `backend/src/workflow/nodes/indicator_nodes.py` | 删除内联 RSI/SMA/BB 计算，调用 `IndicatorEngine` |
| `backend/src/api/indicator_lab_routes.py` | `/generate` 端点内部调用 `IndicatorEngine`（保持沙箱层在外围） |

**注意**：IndicatorLab 的沙箱编译/验证逻辑（`backend/src/lab/`、`backend/src/security/sandbox.py`）保持不变——它处理用户自定义代码，与内置指标是两个层次。

### 1.3 ScreenerNode 接入 ScreenerEngine

```python
# ScreenerNode.execute() 改为：
async def execute(self, inputs: dict, config: dict) -> dict:
    from src.services.screener_engine import ScreenerEngine

    engine = ScreenerEngine()
    factor_data = inputs.get("factor_data")
    codes = inputs.get("codes", [])

    if config.get("mode") == "filter":
        result = engine.run_multi_condition(codes, factor_data, config.get("conditions", []))
    else:
        result = engine.rank_by_factor(codes, factor_data, top_n=int(config.get("top_n", 20)))

    return {"filtered_codes": result.codes, "scores": result.scores}
```

### 1.4 Sentiment 节点接入 SentimentAnalyzer

```python
# sentiment_nodes.py 中的节点改为：
async def execute(self, inputs: dict, config: dict) -> dict:
    from src.services.sentiment_analyzer import SentimentAnalyzer

    analyzer = SentimentAnalyzer()
    ...
```

### 1.5 统一后的架构

```
                  ┌──────── Service Layer（唯一逻辑来源）────────┐
                  │  RegimeEngine        AttributionEngine       │
                  │  StatisticalTestEngine  ScreenerEngine       │
                  │  SentimentAnalyzer     OptionsPricingEngine  │
                  │  CorrelationEngine ← NEW  IndicatorEngine ← NEW │
                  │  SchedulerEngine       VersionControlService │
                  └──────────────────┬───────────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
     ┌────API 层────┐      ┌────节点 层────┐      ┌──未来扩展──┐
     │ screener route│     │ ScreenerNode  │      │ CLI 工具    │
     │ correlation   │     │ CorrelationNode│     │ CI runner   │
     │ indicator-lab │     │ IndicatorNode │      │ cron jobs   │
     │ news/sentiment│     │ SentimentNodes│      │             │
     └───────────────┘     └───────────────┘      └─────────────┘
```

---

## Phase 2：导航重构（清晰用户心智）

**目标**：用户在侧边栏一眼就能区分「我要快速看个东西」vs「我要构建自动化管线」。

**工期**：2-3 天

### 2.1 侧边栏重组

```
之前（扁平列表）：                    之后（分组）：
├── Dashboard                       ├── 📊 总览
├── Agent                           │   └── Dashboard
├── StrategyLab                     │
├── AlphaZoo                        ├── ⚡ 快速探索（一次性分析）
├── IndicatorLab                    │   ├── 选股器        Screener
├── Screener                        │   ├── 相关性分析    Correlation
├── Correlation                     │   ├── 情绪分析      Sentiment
├── Sentiment                       │   ├── 期权分析      Options
├── Options                         │   └── 数据源状态    DataSourceStatus
├── Attribution                     │
├── FactorMining                    ├── 🔧 策略研发（工作流驱动）
├── Compare                         │   ├── 工作流画布    Workflow ← 核心入口
├── PaperTrading                    │   ├── 因子工坊      AlphaZoo
├── Trading                         │   ├── 指标工坊      IndicatorLab
├── Scheduler                       │   ├── 策略工坊      StrategyLab
├── Marketplace                     │   ├── 回测对比      Compare
├── Workflow                        │   ├── 归因分析      Attribution
├── DataSourceStatus                │   ├── 因子挖掘      FactorMining
├── Projects                        │   ├── 模拟交易      PaperTrading
├── Settings                        │   └── 实盘交易      Trading
│                                   │
                                    ├── ⏱ 自动化
                                    │   ├── 调度管理      Scheduler
                                    │   └── 策略市场      Marketplace
                                    │
                                    └── ⚙️ 系统
                                        ├── 项目管理      Projects
                                        ├── 设置           Settings
                                        └── 用户管理      UserManagement
```

### 2.2 工作流节点面板增强

在节点面板中，对有独立页面的节点加导航徽标：

```
节点面板
├── 📥 数据
│   ├── OHLCV Loader
│   └── ...
├── 📊 因子原子
│   ├── MA
│   ├── EMA
│   └── ...
├── 🎯 信号
│   ├── HoldSignal
│   ├── RankSelect
│   └── ...
├── 📈 分析
│   ├── Correlation  [在快速探索中打开 →]  ← 单击跳转到 /correlation
│   ├── Screener     [在快速探索中打开 →]
│   ├── Regime
│   ├── Attribution
│   └── Comparison
└── ...
```

实现：在 `NodeDefinition` 中新增可选字段 `quick_tool_route: str | None`。

### 2.3 面包屑导航

```
工作流画布顶部：
Workflow > My Momentum Strategy > [BacktestNode] ← 可点击

每个节点右键菜单增加：
  «在快速探索中打开»
  «查看节点文档»
  «复制节点»
```

---

## Phase 3：工作流桥接（「导出为工作流」）

**目标**：在快速探索页面得到满意结果后，一键导出为工作流节点继续编排。

**工期**：3-5 天

### 3.1 API：从页面配置创建预配置工作流

```python
# backend/src/api/workflow_routes.py 新增端点

@router.post("/workflows/from-page")
async def create_workflow_from_page(req: PageExportRequest, auth=Depends(require_auth)):
    """将快速探索页面的配置导出为工作流。

    POST /workflows/from-page
    {
        "source_page": "screener",
        "config": {"mode": "rank", "top_n": 47},
        "result_snapshot": {...},     // 可选：缓存当前结果
        "project_id": "proj_abc123"
    }
    → 创建 workflow，预配置对应节点，跳转到 Canvas
    """
    node_config = _page_config_to_node(req.source_page, req.config)

    workflow = {
        "nodes": [{
            "id": "n1",
            "node_type": _page_to_node_type(req.source_page),
            "label": f"从{req.source_page}导入",
            "config": node_config,
            "position": {"x": 100, "y": 100},
        }],
        "edges": [],
    }

    wf_id = store.create_workflow(req.project_id, workflow, auth["user_id"])
    return {"workflow_id": wf_id, "redirect": f"/workflow/{req.project_id}/{wf_id}"}
```

### 3.2 页面映射表

```python
PAGE_TO_NODE = {
    "screener":     "screener",
    "correlation":  "correlation",
    "sentiment":    "sentiment_analyzer",
    "options":      "options_analysis",
    "indicator_lab": "indicator",
}
```

### 3.3 前端实现

每个快速探索页面结果区增加按钮：

```tsx
// 通用组件：ExportToWorkflowButton
function ExportToWorkflowButton({ sourcePage, config, resultSnapshot }) {
  const handleExport = async () => {
    const { workflow_id } = await api.createWorkflowFromPage({
      source_page: sourcePage,
      config,
      result_snapshot: resultSnapshot,
      project_id: currentProjectId,
    });
    navigate(`/workflow/${currentProjectId}/${workflow_id}`);
  };

  return (
    <Button variant="outline" onClick={handleExport}>
      <WorkflowIcon /> 导出为工作流节点
    </Button>
  );
}
```

### 3.4 交互流程

```
用户在 Screener 页面：
  1. 设置条件 → 点「运行选股」
  2. 看到 47 只股票的结果
  3. 想继续回测 → 点「导出为工作流节点」
  4. 自动跳转到 Canvas，ScreenerNode 已预配置好放在画布上
  5. 用户从 ScreenerNode 输出端口拖线 → 自动弹出「接下来可以接什么？」
     → 推荐：BacktestNode, StrategyNode, ExportNode
  6. 用户选择 BacktestNode，自动连好线
  7. 配置回测参数 → 运行 → 得到回测结果
```

---

## Phase 4：工作流功能补全（新增节点）

**目标**：补上 optimization-suggestions.md 中真正缺失的能力，以节点形式实现。

**工期**：7-10 天

### 4.1 ConsistencyCheckNode（P0 — ~50 行）

```python
# backend/src/workflow/nodes/comparison_nodes.py 新增

@register_node
class ConsistencyCheckNode(BaseNode):
    """Compare fast-mode vs simulation-mode backtest results.

    Inputs:
      - fast_result/BACKTEST_RESULT: Fast mode backtest result
      - sim_result/BACKTEST_RESULT:  Simulation mode backtest result

    Outputs:
      - consistency_report/PARAMS: Divergence report
      - is_consistent/PARAMS: bool + threshold check
    """
    node_type = "consistency_check"
    category = "validation"
    label = "Consistency Check"
    description = "Verify fast-mode and simulation-mode backtest results match"
    icon = "CheckCircle"

    config_schema = {
        "return_threshold": {"title": "Return Diff Threshold", "type": "number", "default": 0.01},
        "sharpe_threshold": {"title": "Sharpe Diff Threshold", "type": "number", "default": 0.1},
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        fast = inputs.get("fast_result", {})
        sim = inputs.get("sim_result", {})

        fast_m = fast.get("metrics", {}) if isinstance(fast, dict) else {}
        sim_m = sim.get("metrics", {}) if isinstance(sim, dict) else {}

        return_diff = abs(fast_m.get("total_return", 0) - sim_m.get("total_return", 0))
        sharpe_diff = abs(fast_m.get("sharpe", 0) - sim_m.get("sharpe", 0))

        is_consistent = (
            return_diff <= config.get("return_threshold", 0.01) and
            sharpe_diff <= config.get("sharpe_threshold", 0.1)
        )

        report = {
            "return_diff": round(return_diff, 6),
            "sharpe_diff": round(sharpe_diff, 6),
            "is_consistent": is_consistent,
            "verdict": "PASS" if is_consistent else "FAIL — possible look-ahead bias or pipeline bug",
        }

        return {
            "consistency_report": report,
            "is_consistent": {"pass": is_consistent, **report},
        }
```

**典型接线**：

```
[DataLoadNode] ─┬─→ [StrategyNode] ─→ [BacktestNode(fast)] ─┐
                │                                              ├→ [ConsistencyCheckNode]
                └─→ [StrategyNode] ─→ [BacktestNode(sim)]  ──┘
```

### 4.2 TurnoverConstraintNode（P1 — ~80 行）

```python
# backend/src/workflow/nodes/signal_nodes.py 新增

@register_node
class TurnoverConstraintNode(BaseNode):
    """Limit portfolio turnover between rebalance periods.

    Inputs:
      - target_weights/SIGNAL: Unconstrained target weights
      - current_weights/SIGNAL (optional): Current portfolio weights

    Outputs:
      - constrained_weights/SIGNAL: Turnover-limited weights
    """
    node_type = "turnover_constraint"
    category = "risk"
    label = "Turnover Limit"
    description = "Cap single-period turnover to avoid excessive trading costs"
    icon = "Gauge"

    config_schema = {
        "max_turnover": {"title": "Max Turnover", "type": "number", "default": 0.5,
                         "minimum": 0.05, "maximum": 1.0},
        "turnover_cost_bps": {"title": "Turnover Cost (bps)", "type": "number", "default": 10,
                              "minimum": 0, "maximum": 100},
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        target = _to_weight_dict(inputs.get("target_weights", {}))
        current = _to_weight_dict(inputs.get("current_weights", {}))
        max_to = float(config.get("max_turnover", 0.5))

        constrained = {}
        turnover_total = 0.0

        for code, tw in target.items():
            cw = current.get(code, 0.0)
            diff = tw - cw
            if abs(diff) > max_to:
                diff = max_to * (1 if diff > 0 else -1)
            constrained[code] = cw + diff
            turnover_total += abs(diff)

        cost_estimate = turnover_total * float(config.get("turnover_cost_bps", 10)) / 10000

        return {
            "constrained_weights": constrained,
            "turnover_report": {
                "total_turnover": round(turnover_total, 4),
                "cost_estimate_pct": round(cost_estimate, 6),
                "constrained": len(constrained),
            },
        }
```

### 4.3 CostModelNode（P2 — ~100 行）

```python
# backend/src/workflow/nodes/trading_nodes.py 新增

@register_node
class CostModelNode(BaseNode):
    """Estimate trading costs including impact, commissions, and slippage.

    Inputs:
      - trades/PARAMS: Trade list from backtest
      - ohlcv_data/DF_OHLCV (optional): For impact estimation

    Outputs:
      - cost_report/PARAMS: Detailed cost breakdown
      - adjusted_returns/PARAMS: Returns net of costs
    """
    node_type = "cost_model"
    category = "analysis"
    label = "Cost Model"
    description = "Estimate total trading costs: commission + slippage + market impact"
    icon = "Receipt"

    config_schema = {
        "commission_bps": {"title": "Commission (bps)", "type": "number", "default": 3},
        "stamp_duty_bps": {"title": "Stamp Duty (bps, sell only)", "type": "number", "default": 5},
        "impact_model": {"title": "Impact Model", "type": "string",
                         "enum": ["none", "almgren_chriss_simple", "square_root"], "default": "almgren_chriss_simple"},
        "daily_volume_pct": {"title": "Max Daily Volume %", "type": "number", "default": 5,
                             "description": "Maximum participation rate for impact estimation"},
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        trades = inputs.get("trades", [])
        ohlcv = inputs.get("ohlcv_data", {})

        from src.services.cost_engine import CostEngine
        engine = CostEngine()
        report = engine.analyze(trades, ohlcv, config)

        return {"cost_report": report.model_dump()}
```

### 4.4 LiveDataNode（P2 — 实时行情订阅）

```python
# backend/src/workflow/nodes/data_nodes.py 新增

@register_node
class LiveDataNode(BaseNode):
    """Subscribe to real-time market data via WebSocket/SSE.

    Differs from OHLCVLoaderNode (static historical data) — this node
    emits a streaming output that downstream nodes can react to bar-by-bar.

    Inputs:
      - codes/STOCK_LIST: Stock codes to subscribe

    Outputs:
      - live_bars/DF_OHLCV (streaming): Real-time bar data
    """
    node_type = "live_data"
    category = "data"
    label = "Live Data Feed"
    description = "Subscribe to real-time market data stream"
    icon = "Radio"

    config_schema = {
        "source": {"title": "Source", "type": "string",
                   "enum": ["futu", "tdx", "sina", "eastmoney"], "default": "eastmoney"},
        "interval": {"title": "Interval", "type": "string",
                     "enum": ["tick", "1m", "5m", "15m", "60m", "1D"], "default": "1m"},
    }
```

### 4.5 LiveMonitorNode（P3 — 实盘偏差监控）

```python
# backend/src/workflow/nodes/comparison_nodes.py 新增

@register_node
class LiveMonitorNode(BaseNode):
    """Track divergence between live trading signals and backtest expectations.

    Inputs:
      - live_signal/SIGNAL: Real-time trading signals
      - backtest_signal/SIGNAL: Expected signals from backtest at same timestamp

    Outputs:
      - divergence_report/PARAMS: Signal divergence metrics
      - alert/PARAMS (optional): Triggered alerts
    """
    node_type = "live_monitor"
    category = "monitoring"
    label = "Live Monitor"
    description = "Track live vs backtest signal divergence"
    icon = "Activity"

    config_schema = {
        "signal_diff_threshold": {"title": "Signal Diff Threshold", "type": "number", "default": 0.2},
        "alert_on_divergence": {"title": "Alert on Divergence", "type": "boolean", "default": True},
    }
```

### 4.6 完整节点目录（Phase 4 完成后）

```
backend/src/workflow/nodes/
├── data_nodes.py          ← +LiveDataNode
├── factor_atoms.py
├── indicator_nodes.py     ← 改用 IndicatorEngine
├── signal_nodes.py        ← +TurnoverConstraintNode
├── strategy_nodes.py      (BacktestNode, WalkForwardNode, ExperimentNode)
├── regime_nodes.py
├── analysis_nodes.py      (AttributionNode)
├── comparison_nodes.py    ← +ConsistencyCheckNode, +LiveMonitorNode
├── correlation_nodes.py   ← 改用 CorrelationEngine
├── sentiment_nodes.py     ← 改用 SentimentAnalyzer
├── trading_nodes.py       ← +CostModelNode
├── thin_nodes.py          (ScreenerNode ← 改用 ScreenerEngine, PaperTradingNode)
├── options_nodes.py
├── mining_nodes.py
├── output_nodes.py
├── notify_nodes.py
├── sector_nodes.py
├── alpha_nodes.py
├── control_nodes.py
└── experiment_nodes.py
```

---

## Phase 5：增量缓存 + 引擎增强

**目标**：加速策略研反馈循环，实现在工作流中「改一个参数 → 只重跑受影响节点」。

**工期**：5-7 天

### 5.1 WorkflowEngine 节点级缓存

```python
# backend/src/workflow/workflow_engine.py 增强

class WorkflowEngine:
    def __init__(self, ...):
        ...
        self._node_cache: Dict[str, dict] = {}  # cache_key → {outputs, timestamp}

    async def _execute_with_limits(self, nid: str, node: WorkflowNodeData):
        # 计算缓存 key：node_type + config + inputs_hash + version
        cache_key = self._compute_cache_key(nid, node)

        if cache_key in self._node_cache:
            cached = self._node_cache[cache_key]
            # 检查上游输入是否变化
            if not self._inputs_changed(nid, cached["input_hashes"]):
                self._results[nid] = cached["outputs"]
                self._node_status[nid] = NodeStatus.CACHED
                await self._emit("node_cached", {"node_id": nid})
                return

        # 正常执行...
        result = await self._execute_node(node, inputs)
        # 存入缓存
        self._node_cache[cache_key] = {
            "outputs": result,
            "input_hashes": self._compute_input_hashes(nid),
            "timestamp": time.time(),
            "version": node_class.version,
        }
```

**缓存层级**（对应 optimization-suggestions 的 2.3）：

```
Layer 1: 原始数据      — DataStore 已有 ✅
Layer 2: 信号序列      — 工作流节点缓存（新增）
Layer 3: 对齐权重矩阵  — 工作流节点缓存（新增）
Layer 4: 执行结果      — 工作流节点缓存（新增，命中时跳过 BacktestNode）
```

**用户可见的效果**：工作流运行时，未变更的节点显示 `[cached]` 状态标签，只重新执行下游受影响的节点。

### 5.2 节点 version 机制（已有基础，增强）

```python
class BaseNode:
    version: int = 1  # 已有字段

    # 增强：config_hash 纳入缓存 key
    def config_fingerprint(self, config: dict) -> str:
        """Stable hash of node config, excluding volatile fields."""
        stable = {k: v for k, v in config.items()
                  if k not in ("_timestamp", "_run_id")}
        return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()[:16]
```

### 5.3 预置工作流模板扩展

```python
# backend/src/workflow/templates/registry.py 新增模板

TEMPLATES += [
    {
        "id": "full_research_pipeline",
        "name": "🔬 Full Research Pipeline",
        "description": "数据加载 → 选股 → 回测(fast+sim) → 一致性校验 → 对比 → 归因",
        "nodes": [
            # OHLCVLoaderNode → ScreenerNode → StrategyNode →
            #   BacktestNode(fast) ┐
            #   BacktestNode(sim)  ├→ ConsistencyCheckNode → AttributionNode
        ],
    },
    {
        "id": "walkforward_validation",
        "name": "✅ Walk-Forward Validation",
        "description": "Regime检测 → WalkForwardNode(多窗口参数优化) → OOS评估",
        "nodes": [
            # RegimeNode → WalkForwardNode → ComparisonNode
        ],
    },
    {
        "id": "live_monitoring",
        "name": "📡 Live Trading Monitor",
        "description": "实时数据 → 信号生成 → 实盘执行 + 偏差监控",
        "nodes": [
            # LiveDataNode → StrategyNode → BrokerNode
            #                          → LiveMonitorNode
        ],
    },
]
```

---

## Phase 6：体验优化 + 渐进收编

**目标**：根据使用数据决定哪些独立页面收编为工作流快捷入口。

**工期**：持续进行

### 6.1 使用数据埋点

在以下位置增加匿名事件追踪（可选，需用户同意）：

```python
# 追踪事件
"page:screener:export_to_workflow"    # 从 Screener 页面导出为工作流
"page:correlation:export_to_workflow" # 从 Correlation 页面导出为工作流
"workflow:node:open_quick_tool"       # 从节点徽标跳转到独立页面
"workflow:template:use"               # 使用预置模板
"workflow:node:cached"                # 节点缓存命中
```

### 6.2 收编决策标准

| 导出率 | 行动 |
|---|---|
| < 20% | 保持现状（独立页面 + 工作流节点共存） |
| 20-60% | 优化「导出为工作流」体验，增加快捷入口 |
| > 60% | 将独立页面变为工作流模板的快捷入口（页面 = 预配置单节点工作流） |

### 6.3 前端体验增强（对应 2.4）

| 增强项 | 实现方式 |
|---|---|
| **参数扫描 heatmap** | `ExperimentNode` 输出增加 `heatmap_data` 端口 → 前端 `HeatmapChart` 组件 |
| **实时回测进度** | `BacktestNode` 已有 progress callback → WebSocket 推送到 Canvas |
| **权益曲线实时绘制** | `ChartDataNode` 增加 streaming 输出模式 |
| **月度收益热力图** | `ChartDataNode` 增加 `calendar_heatmap` 图表类型 |

---

## 总时间线

```
Week 1 (Day 1-5):   Phase 0 — 回测结果持久化
  Day 1-2:   BacktestDriver._persist_to_db() + 所有路径自动覆盖
  Day 3-4:   前端 BacktestHistory 页面 + 路由 + api.ts
  Day 5:     RunDetail 适配 PG + 自动标签 + 集成测试

Week 2 (Day 6-10):  Phase 1 — Service 层统一
  Day 6-7:   CorrelationEngine + 改造 CorrelationNode/API
  Day 8-9:   IndicatorEngine + 改造 IndicatorNode
  Day 10:    ScreenerNode → ScreenerEngine, Sentiment 节点 → SentimentAnalyzer

Week 3 (Day 11-15): Phase 2 + Phase 3 — 导航重构 + 工作流桥接
  Day 11-12: 侧边栏重组 + 面包屑导航（含回测历史入口）
  Day 13-14: 「导出为工作流」API + 前端按钮组件
  Day 15:    集成测试 + 端到端验证

Week 4 (Day 16-22): Phase 4 — 新节点
  Day 16:    ConsistencyCheckNode
  Day 17-18: TurnoverConstraintNode + CostModelNode
  Day 19-20: LiveDataNode + LiveMonitorNode
  Day 21-22: 新模板 + 集成测试

Week 5 (Day 23-29): Phase 5 — 增量缓存
  Day 23-25: WorkflowEngine 节点缓存
  Day 26-27: 缓存失效策略 + 测试
  Day 28-29: 性能基准测试 + 优化

Week 6+ (持续):     Phase 6 — 体验优化 + 渐进收编
  Week 6:    使用数据埋点 + Heatmap 可视化
  Week 7+:   根据数据决定收编策略 + 持续迭代
```

### 里程碑

```
[W1 结束] ✅ 历史可见 — 所有回测自动存入 PG，前端可浏览/排序/筛选
[W2 结束] ✅ 双轨消除 — 所有计算逻辑统一到 Service 层
[W3 结束] ✅ 导航清晰 — 用户能区分「探索」和「编排」，可一键导出到工作流
[W4 结束] ✅ 节点补全 — 一致性校验/换手率/成本模型/实时监控全部可用
[W5 结束] ✅ 缓存生效 — 迭代速度提升 60-80%
[W7 结束] ✅ 体验闭环 — 基于使用数据的收编决策 + 可视化增强
```

---

## 附录 A：与 optimization-suggestions.md 的差异总结

| 原建议 | 本计划修正 |
|---|---|
| 新建 `backtest/sweep.py` | **不建**，已有 `GridSearchOptimizer` + `ExperimentNode` |
| 新建 `backtest/walkforward.py` | **不建**，已有 `WalkForwardAnalyzer` + `WalkForwardNode` |
| 新建 `backtest/compare.py` | **不建**，已有 `ComparisonNode` + Compare 页面 |
| 新建 `backtest/regime.py` | **不建**，已有 `RegimeEngine` + `RegimeNode` |
| 新建 `backtest/attribution.py` | **不建**，已有 `AttributionEngine` + `AttributionNode` |
| 参数扫描 Heatmap | 作为 `ExperimentNode` 输出增强，工作流模板内实现 |
| 结果数据库 | **Phase 0 核心内容**：`backtest_store` 已有但无人调用，修复后自动覆盖所有回测路径 |
| Pre-commit | 作为 `ConsistencyCheckNode` 在工作流中实现，CI 跑工作流 |
| 一致性校验 | 新增 `ConsistencyCheckNode`（~50行），而非独立脚本 |
| 换手率约束 | 新增 `TurnoverConstraintNode`，嵌入信号→回测管线 |
| 成本模型 | 新增 `CostModelNode`，嵌入交易→分析管线 |
| 增量缓存 | 在 `WorkflowEngine` 层面实现节点级缓存 |
| 实盘偏差 | 新增 `LiveMonitorNode`，作为监控工作流的一部分 |

## 附录 B：不做的事项（与 NautilusTrader 差距）

| 能力 | 理由 |
|---|---|
| Rust 核心重写 | 日频策略 Python 够用，工作流系统已经解决了编排问题 |
| L2/L3 订单簿模拟 | 组合策略不需要逐笔撮合 |
| 9 种订单类型 | 权重→仓位模型更直接 |
| Streaming 数据加载 | A 股日频数据量不大，全量加载可接受 |
| Tick 级延迟模拟 | 日频策略不需要 |

**AStockPursue 的护城河**：中国市场适配 + n8n 风格工作流 + 因子挖掘管线 + 组合优化。不需要成为 NautilusTrader。
