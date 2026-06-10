# AStockPursue 全面增强实施计划

> **原则**：所有新增能力必须适配现有工作流引擎架构——即每个新功能都以**类型化工作流节点**的形式落地，通过画布拖拽组装，Kahn + asyncio 并发调度。

---

## 目录

1. [现状评估](#1-现状评估)
2. [架构适配原则](#2-架构适配原则)
3. [Phase 0：基础设施](#3-phase-0基础设施)
4. [Phase 1：通知系统升级](#4-phase-1通知系统升级)
5. [Phase 2：多券商实盘扩展](#5-phase-2多券商实盘扩展)
6. [Phase 3：实验管线节点](#6-phase-3实验管线节点)
7. [Phase 4：市场状态识别节点](#7-phase-4市场状态识别节点)
8. [Phase 5：策略进化引擎](#8-phase-5策略进化引擎)
9. [Phase 6：AI 反思与自学习](#9-phase-6ai-反思与自学习)
10. [Phase 7：i18n 与分发](#10-phase-7i18n-与分发)
11. [执行路线图](#11-执行路线图)
12. [文件变更清单](#12-文件变更清单)

---

## 1. 现状评估

### 1.1 你的绝对优势（保持并深化）

| 能力 | 状态 | 说明 |
|------|------|------|
| **工作流引擎** | 🟢🟢🟢🟢🟢 | n8n 风格 DAG 画布 + 20+节点 + Kahn并发 + 快照 + 断点续跑。行业独有 |
| **因子工厂** | 🟢🟢🟢🟢🟢 | 450+因子(alpha101+gtja191+qlib158+academic+mined) + GP进化 + LLM挖掘 |
| **回测引擎** | 🟢🟢🟢🟢🟢 | 统一 bar-by-bar 管道 + 9种市场引擎 + CompositeEngine |
| **A股/期货/期权** | 🟢🟢🟢🟢🟢 | T+1/涨跌停/中国期货/期权定价。国内外唯一 |
| **策略版本控制** | 🟢🟢🟢🟢 | 完整 diff 历史 + 回滚 |
| **前端** | 🟢🟢🟢🟢 | React 19 + Monaco + XYFlow + ECharts |

### 1.2 待补齐的能力缺口

| 能力 | 状态 | 优先级 | QuantDinger 对齐程度 |
|------|------|--------|---------------------|
| **通知推送** | 🟢🟢 (基础) | 🔴 P0 | 缺少 Telegram/多通道/方言检测 |
| **实盘券商** | 🟢 (仅富途) | 🔴 P0 | 缺 Binance/OKX 等加密交易所 |
| **Redis 缓存** | ❌ 无 | 🔴 P0 | 缺内存级缓存层 |
| **实验管线** | ❌ 无 | 🟡 P1 | Regime→Generate→Backtest→Score→Rank→Best |
| **市场状态识别** | ❌ 无 | 🟡 P1 | 规则型状态检测 + 策略族推荐 |
| **策略自动进化** | ⚠️ 有基础 | 🟡 P1 | Walk-Forward 有，缺进化循环 |
| **AI 反思学习** | ❌ 无 | 🟢 P2 | 分析记忆 + 反馈闭环 |
| **i18n 多语言** | 🟢🟢 (2种) | 🟢 P2 | 可扩展到 4-5 种 |
| **前端预构建分发** | ❌ 无 | 🟢 P2 | 目前需要 Node.js 开发环境 |

---

## 2. 架构适配原则

### 2.1 一切皆节点

AStockPursue 的核心设计哲学：**所有工具都是工作流画布上的类型化节点**。新增的每个能力都必须遵循这个原则：

```
新能力 → 新增一个或多个 BaseNode 子类 → 注册到 NodeRegistry → 画布可用
```

### 2.2 端口类型系统

现有端口类型（`backend/src/workflow/schema.py`）：

```python
class PortType(str, Enum):
    STOCK_LIST        # list[str]
    DATE_RANGE        # (start, end)
    PARAMS            # dict[str, Any]
    BOOL              # bool
    DF_OHLCV          # {code: DataFrame(o,h,l,c,v)}
    DF_FACTOR         # DataFrame: index=date, columns=codes
    DF_RETURNS        # DataFrame
    FACTOR_RESULT     # dict with IC stats
    SIGNAL            # dict[code, weight/Series]
    BACKTEST_RESULT   # backtest output dict
    ATTRIBUTION       # attribution dict
    TECHNICAL_INDICATOR
    CORRELATION_MATRIX
    SENTIMENT
    COMPARISON_RESULT
    ANY               # wildcard
```

新增能力需要新增的端口类型：

```python
    NOTIFY_CONFIG     # 通知配置 dict → Phase 1
    ORDER_RESULT      # 下单结果 dict → Phase 2
    REGIME_RESULT     # 市场状态 dict → Phase 4
    EXPERIMENT_RESULT # 实验输出 dict → Phase 3
    SCORE_RESULT      # 评分结果 dict → Phase 3
```

### 2.3 节点注册模式

每个新节点遵循现有模式（参考 `control_nodes.py` 的 `AgentNode`）：

```python
@register_node
class MyNewNode(BaseNode):
    node_type = "my_new_node"
    category = "analysis"    # 对应现有 9 个类别之一
    label = "My New Node"
    description = "..."
    icon = "IconName"
    resource_profile = "cpu_bound"  # 或 io_bound / default

    inputs = [
        BaseNode.in_port("input_name", PortType.XXX),
    ]
    outputs = [
        BaseNode.out_port("output_name", PortType.YYY),
    ]
    config_schema = { ... }

    async def execute(self, inputs: dict, config: dict) -> dict:
        # 实现逻辑
        return {"output_name": result}
```

### 2.4 交易引擎管道不变

`TradingEngine.on_bar()` 的 6 步管道**不被修改**，新增的券商、通知、实验能力工作在管道之外或作为管道配置输入：

```
on_bar(bar, ts)          ← 不变
  ├─ Gap/Suspension      ← 不变
  ├─ Market hooks        ← 新增 funding rate hooks (Phase 2)
  ├─ SignalAdapter       ← 不变
  ├─ OptimizerAdapter    ← 新增进化后的参数 (Phase 5)
  ├─ RiskPipeline        ← 触发通知 (Phase 1)
  └─ Record snapshot     ← 不变
```

---

## 3. Phase 0：基础设施

### 3.1 Redis 缓存层

**目标**：在 `data_store.py` 的三层缓存（PG → Parquet → API）之上增加 L0 内存缓存。

#### 3.1.0 为什么需要 Redis

当前数据加载路径：

```
请求行情 → PostgreSQL 缓存 → (miss) → Parquet 文件 → (miss) → 外部 API
```

每个 miss 都有磁盘 I/O 或网络延迟。增加 Redis 后：

```
请求行情 → Redis (L0, <1ms) → (miss) → PostgreSQL (L1) → (miss) → Parquet (L2) → (miss) → API (L3)
```

典型命中率：日内重复请求（回测调参、工作流节点间数据复用）命中率 > 80%。

#### 3.1.1 新建文件

```
backend/src/cache/__init__.py
backend/src/cache/redis_client.py
backend/src/cache/data_cache.py
```

#### 3.1.2 `redis_client.py` — 连接池管理

```python
"""Redis 连接池 — 单例，惰性初始化，自动重连。

设计原则：
  - 不依赖 Redis 启动：若 Redis 不可用，优雅降级到仅 PG+Parquet+API 三层
  - 连接池复用：避免每次请求都建连
  - Key 命名空间：as:cache:<entity>:<key>，避免与其他系统冲突
"""

import logging
import os
from typing import Optional
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_pool: Optional[aioredis.ConnectionPool] = None
_available: Optional[bool] = None


async def get_redis() -> Optional[aioredis.Redis]:
    """返回 Redis 客户端，若不可用则返回 None。"""
    global _pool, _available

    if _available is False:
        return None

    if _pool is None:
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        try:
            _pool = aioredis.ConnectionPool.from_url(
                f"redis://{host}:{port}",
                max_connections=20,
                socket_connect_timeout=2,
                socket_keepalive=True,
                retry_on_timeout=True,
            )
            # 验证连接
            r = aioredis.Redis(connection_pool=_pool)
            await r.ping()
            _available = True
            logger.info("Redis connected: %s:%s", host, port)
        except Exception as e:
            logger.warning("Redis unavailable (%s), cache disabled", e)
            _available = False
            _pool = None
            return None

    return aioredis.Redis(connection_pool=_pool)
```

#### 3.1.3 `data_cache.py` — 行情数据缓存装饰器

```python
"""行情数据 Redis 缓存 — L0 层。

Key 格式: as:cache:bars:{market}:{symbol}:{interval}:{start}:{end}
TTL: 根据粒度自动选择 (1m: 5min, 5m: 15min, 1d: 24h)
序列化: Parquet bytes → base64 (Redis 友好)
"""

import base64
import hashlib
import json
import logging
from datetime import datetime
from functools import wraps
from io import BytesIO
from typing import Optional

import pandas as pd

from .redis_client import get_redis

logger = logging.getLogger(__name__)

TTL_MAP = {"1m": 300, "5m": 900, "15m": 1800, "30m": 3600, "1h": 7200, "1d": 86400}


def _cache_key(market: str, symbol: str, interval: str, start: str, end: str) -> str:
    return f"as:cache:bars:{market}:{symbol}:{interval}:{start}:{end}"


def _ttl(interval: str) -> int:
    return TTL_MAP.get(interval, 3600)


async def cached_bars(market: str, symbol: str, interval: str,
                      start: str, end: str) -> Optional[pd.DataFrame]:
    """从 Redis 读取缓存的 OHLCV 数据。"""
    r = await get_redis()
    if r is None:
        return None
    key = _cache_key(market, symbol, interval, start, end)
    try:
        raw = await r.get(key)
        if raw:
            buf = BytesIO(base64.b64decode(raw))
            return pd.read_parquet(buf)
    except Exception:
        pass
    return None


async def cache_bars(market: str, symbol: str, interval: str,
                     start: str, end: str, df: pd.DataFrame) -> None:
    """将 OHLCV 数据写入 Redis 缓存。"""
    r = await get_redis()
    if r is None or df is None or df.empty:
        return
    key = _cache_key(market, symbol, interval, start, end)
    try:
        buf = BytesIO()
        df.to_parquet(buf, compression="zstd")
        await r.setex(key, _ttl(interval), base64.b64encode(buf.getvalue()))
    except Exception as e:
        logger.debug("Redis cache write failed: %s", e)
```

#### 3.1.4 修改 `data_store.py`

在 `DataStore.load_bars()` 方法中插入 Redis L0 层：

```python
# 在现有 load_bars() 开头增加:
cached = await cached_bars(market, symbol, interval, start_str, end_str)
if cached is not None:
    return cached

# 在现有 load_bars() 成功返回前增加:
await cache_bars(market, symbol, interval, start_str, end_str, df)
```

#### 3.1.5 docker-compose.yml 变更

```yaml
# 在 services 下新增:
redis:
  image: redis:7-alpine
  command: ["redis-server", "--maxmemory", "256mb", "--maxmemory-policy", "allkeys-lru"]
  ports:
    - "${REDIS_PORT:-127.0.0.1:6379}:6379"
  volumes:
    - redis-data:/data
  networks:
    - vt-net
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 5s
    retries: 3
  restart: unless-stopped

# 在 volumes 下新增:
redis-data:

# 在 astockpursue 服务的 environment 下新增:
- REDIS_HOST=redis
- REDIS_PORT=6379
```

---

## 4. Phase 1：通知系统升级

### 4.1 设计要点

**现状**：`backend/src/notify/channels.py` 有 webhook (wecom/dingtalk/generic) + email (SMTP)，`engine.py` 有 `NotifyEngine` 类。

**缺口**：无 Telegram、无 Discord、无多渠道并发、无模板化消息、无用户自定义通知配置界面。

**架构适配**：通知作为**工作流节点** `NotifyNode` 提供，同时在 `RiskPipeline` 中通过 `NotifyEngine` 内联触发。

### 4.2 消息模型升级

修改 `channels.py:Alert`，增加信号交易上下文：

```python
@dataclass
class Alert:
    """通知消息 — 支持系统告警和交易信号两类。"""
    title: str
    body: str
    level: str = "info"          # info | warning | critical | signal
    source: str = "system"       # system | risk | oms | papertrade | strategy
    # 交易信号上下文（可选）
    symbol: str = ""
    signal_type: str = ""        # buy | sell | stop_loss | take_profit
    price: float = 0.0
    quantity: float = 0.0
    metadata: dict | None = None
```

### 4.3 新增通道

```python
# channels.py 新增函数:

def send_telegram(alert: Alert, config: dict) -> bool:
    """通过 Telegram Bot API 发送通知。
    
    config 需包含: bot_token, chat_id
    消息格式: HTML (支持 <b>/<code>/<pre>)
    """

def send_discord(alert: Alert, config: dict) -> bool:
    """通过 Discord Webhook 发送 Embed 消息。"""

def send_webhook_feishu(alert: Alert, config: dict) -> bool:
    """飞书/Lark 自定义机器人 — msg_type=text。"""

# 增强现有 send_webhook，增加方言自动检测:
def _detect_dialect(url: str) -> str:
    """从 URL 自动检测 webhook 平台: feishu | dingtalk | wecom | slack | generic"""
    url_lower = url.lower()
    if "open.feishu.cn" in url_lower or "open.larksuite.com" in url_lower:
        return "feishu"
    if "oapi.dingtalk.com" in url_lower:
        return "dingtalk"
    if "qyapi.weixin.qq.com" in url_lower:
        return "wecom"
    if "hooks.slack.com" in url_lower:
        return "slack"
    if "discord.com/api/webhooks" in url_lower:
        return "discord"
    return "generic"
```

### 4.4 NotifyNode — 工作流集成

```python
# 新建文件: backend/src/workflow/nodes/notify_nodes.py

@register_node
class NotifyNode(BaseNode):
    """通知节点 — 在画布上触发多渠道通知。
    
    典型位置：工作流末尾，接收 BacktestResult 或 OrderResult，
    将关键指标推送到用户配置的通知渠道。
    
    输入端口:
      - backtest_result (可选): 自动提取核心指标
      - order_result (可选): 自动提取订单信息
      - custom_message (可选): Params 类型的自定义消息
      
    输出端口:
      - notify_status: 各渠道发送结果
    """
    node_type = "notify"
    category = "output"
    label = "Send Notification"
    description = "Push results to Telegram/Email/Webhook/Discord — auto-formats from upstream"
    icon = "Bell"
    resource_profile = "io_bound"

    inputs = [
        BaseNode.in_port("backtest_result", PortType.BACKTEST_RESULT, required=False),
        BaseNode.in_port("order_result", PortType.PARAMS, required=False),
        BaseNode.in_port("custom_message", PortType.PARAMS, required=False),
    ]
    outputs = [
        BaseNode.out_port("notify_status", PortType.PARAMS),
    ]
    config_schema = {
        "channels": {
            "title": "Channels",
            "type": "array",
            "items": {"type": "string", "enum": ["telegram", "email", "webhook", "discord"]},
            "default": ["telegram"],
        },
        "telegram_chat_id": {"title": "Telegram Chat ID", "type": "string", "default": ""},
        "email_to": {"title": "Email To", "type": "string", "default": ""},
        "webhook_url": {"title": "Webhook URL", "type": "string", "default": ""},
        "include_backtest_summary": {"title": "Include Backtest", "type": "boolean", "default": True},
        "include_equity_chart": {"title": "Include Chart", "type": "boolean", "default": False},
    }
```

### 4.5 RiskPipeline 内联通知

在 `risk_pipeline.py` 的止损/止盈/日内最大亏损触发点，通过现有 `NotifyEngine.alert()` 发送告警：

```python
# risk_pipeline.py 中 stop_loss 触发时:
self._notify.alert(Alert(
    title=f"止损触发: {symbol}",
    body=f"入场 {entry_price:.2f} → 出场 {current_price:.2f} ({pnl_pct:+.2%})",
    level="warning",
    source="risk",
    symbol=symbol,
    signal_type="stop_loss",
    price=current_price,
))
```

---

## 5. Phase 2：多券商实盘扩展

### 5.1 设计要点

**现状**：`backend/src/trading/brokers/futu_broker.py` 仅支持富途。

**目标**：增加加密交易所支撑（Binance、OKX），保持与现有 `TradingEngine.on_bar()` 管道的兼容。

**架构适配**：券商作为 `BrokerNode` 工作流节点 + 工厂模式创建 + TradingEngine 通过 `MarketHooks` 感知券商特性。

### 5.2 Broker 抽象层

```python
# 新建文件: backend/src/trading/brokers/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class BrokerOrder:
    order_id: str
    symbol: str
    side: str          # buy | sell
    order_type: str    # market | limit
    price: float
    quantity: float
    filled_qty: float = 0.0
    filled_price: float = 0.0
    status: str = "pending"  # pending | submitted | partial | filled | cancelled | rejected
    reject_reason: str = ""


@dataclass
class BrokerPosition:
    symbol: str
    quantity: float
    avg_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class BrokerBalance:
    total: float
    available: float
    frozen: float = 0.0
    currency: str = "USDT"


class BaseBroker(ABC):
    """券商/交易所抽象基类。
    
    每个具体实现负责:
      1. REST API 签名和请求
      2. 订单的创建/取消/查询
      3. 持仓/余额查询
      4. 手续费率查询
    """

    exchange_id: str = ""

    @abstractmethod
    async def place_order(self, symbol: str, side: str, order_type: str,
                          quantity: float, price: float = None) -> BrokerOrder: ...

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str = "") -> bool: ...

    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[BrokerPosition]: ...

    @abstractmethod
    async def get_positions(self) -> list[BrokerPosition]: ...

    @abstractmethod
    async def get_balance(self) -> BrokerBalance: ...

    @abstractmethod
    def get_fee_rate(self, symbol: str) -> dict[str, float]:
        """返回 {"maker": 0.0002, "taker": 0.0005}"""
        ...

    @abstractmethod
    async def test_connection(self) -> bool: ...
```

### 5.3 工厂模式

```python
# 新建文件: backend/src/trading/brokers/factory.py

from .base import BaseBroker
from .futu_broker import FutuBroker


_BROKER_REGISTRY: dict[str, type[BaseBroker]] = {}


def register_broker(cls: type[BaseBroker]):
    _BROKER_REGISTRY[cls.exchange_id] = cls
    return cls


def create_broker(exchange_id: str, config: dict) -> BaseBroker:
    """从配置创建券商实例。
    
    示例:
        broker = create_broker("binance", {
            "api_key": "...", "secret_key": "...",
            "testnet": True,
        })
    """
    cls = _BROKER_REGISTRY.get(exchange_id)
    if cls is None:
        raise ValueError(f"Unknown exchange: {exchange_id}. Available: {list(_BROKER_REGISTRY)}")
    return cls(**config)


def list_brokers() -> list[str]:
    return list(_BROKER_REGISTRY.keys())
```

### 5.4 Binance 券商实现

```python
# 新建文件: backend/src/trading/brokers/binance.py

"""Binance USDT-M 永续合约券商适配器。

使用 ccxt 作为底层 REST 客户端（项目已有依赖）。
支持实盘和 testnet 双模式。
"""

@register_broker
class BinanceBroker(BaseBroker):
    exchange_id = "binance"

    def __init__(self, api_key: str, secret_key: str, testnet: bool = False):
        import ccxt.async_support as ccxt_async
        self._exchange = ccxt_async.binance({
            "apiKey": api_key,
            "secret": secret_key,
            "options": {"defaultType": "future"},
            "urls": {
                "api": {
                    "fapiPublic": "https://testnet.binancefuture.com/fapi/v1"
                    if testnet else "https://fapi.binance.com/fapi/v1",
                    "fapiPrivate": "https://testnet.binancefuture.com/fapi/v1"
                    if testnet else "https://fapi.binance.com/fapi/v1",
                }
            },
        }) if testnet else ccxt_async.binance({
            "apiKey": api_key, "secret": secret_key,
            "options": {"defaultType": "future"},
        })

    async def place_order(self, symbol, side, order_type, quantity, price=None):
        # 1. 获取市场精度 → 2. 标准化 symbol/size → 3. 下单 → 4. 返回 BrokerOrder
        ...

    async def cancel_order(self, order_id, symbol=""): ...

    async def get_position(self, symbol): ...

    async def get_positions(self): ...

    async def get_balance(self): ...

    def get_fee_rate(self, symbol) -> dict[str, float]:
        return {"maker": 0.0002, "taker": 0.0004}

    async def test_connection(self) -> bool: ...
```

### 5.5 OKX 券商实现

```python
# 新建文件: backend/src/trading/brokers/okx.py

@register_broker
class OKXBroker(BaseBroker):
    exchange_id = "okx"
    # 类似 Binance，使用 ccxt.pro.okx
    ...
```

### 5.6 BrokerNode — 工作流节点

```python
# 修改文件: backend/src/workflow/nodes/trading_nodes.py
# 在现有 OrderNode 基础上增强:

@register_node
class BrokerNode(BaseNode):
    """券商连接节点 — 管理交易所连接和订单路由。
    
    与 OrderNode 的区别:
      - BrokerNode: 管理连接、查询持仓/余额
      - OrderNode:  发送具体交易指令
    
    输入端口:
      - codes/STOCK_LIST → 要查询的标的列表 (查询持仓时)
      
    输出端口:
      - positions/PARAMS → 持仓列表
      - balance/PARAMS   → 账户余额
      - status/PARAMS     → 连接状态
    """
    node_type = "broker"
    category = "deploy"
    label = "Broker Connect"
    description = "Connect to exchange/broker, query positions and balance"
    icon = "Plug"
    resource_profile = "io_bound"

    inputs = [
        BaseNode.in_port("codes", PortType.STOCK_LIST, required=False),
    ]
    outputs = [
        BaseNode.out_port("positions", PortType.PARAMS),
        BaseNode.out_port("balance", PortType.PARAMS),
        BaseNode.out_port("status", PortType.PARAMS),
    ]
    config_schema = {
        "exchange": {
            "title": "Exchange", "type": "string",
            "enum": ["futu", "binance", "okx"],
            "default": "binance",
        },
        "testnet": {"title": "Testnet", "type": "boolean", "default": True},
        "action": {
            "title": "Action", "type": "string",
            "enum": ["positions", "balance", "connect_test"],
            "default": "positions",
        },
    }
```

### 5.7 凭证安全存储

```python
# 新建文件: backend/src/trading/credential_store.py

"""券商 API 凭证加密存储。

使用 cryptography.fernet (项目已有依赖) 做对称加密。
密钥来源: CREDENTIAL_ENCRYPTION_KEY 环境变量 (64 字节 hex)
"""

from cryptography.fernet import Fernet
...
```

### 5.8 数据库迁移

```sql
-- backend/migrations/014_broker_credentials.sql

CREATE TABLE IF NOT EXISTS broker_credentials (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exchange_id VARCHAR(20) NOT NULL,
    label VARCHAR(100) DEFAULT '',
    api_key_enc TEXT NOT NULL,
    secret_key_enc TEXT NOT NULL,
    passphrase_enc TEXT,
    testnet BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, exchange_id, label)
);

CREATE INDEX idx_broker_cred_user ON broker_credentials(user_id);
```

---

## 6. Phase 3：实验管线节点

### 6.1 设计要点

这是借鉴 QuantDinger 设计理念、但在你现有架构上完全重新实现的核心能力。

**量化实验管线** = 市场状态驱动 + 策略变体生成 + 批量回测 + 多因子评分 + 排名输出

**适配方式**：新增 3 个工作流节点 + 1 个服务模块，全部通过画布组装。

```
工作流示例:
  StockPoolNode ─→ FactorNode ─→ StrategyNode ─→ ExperimentNode ─→ BacktestNode
                                   (基准策略)        │                  │
                                                     │ 生成N个候选       │ 并行回测
                                                     │                  │
                                                     └── ScoreNode ←────┘
                                                          │
                                                          └── RankSelectNode → 最优策略
```

### 6.2 新增端口类型

```python
# 修改 schema.py，PortType 新增:

SCORE_RESULT = "score_result"          # 策略评分结果 dict
EXPERIMENT_RESULT = "experiment_result" # 实验输出 dict
```

### 6.3 策略评分服务

```python
# 新建文件: backend/src/services/strategy_scorer.py

"""策略多因子评分服务。

设计原则:
  - 输入: 回测结果 dict (已有 BACKTEST_RESULT 格式)
  - 输出: 0-100 的综合评分 + 各维度分项 + 等级 (A/B/C/D/E)
  - 权重: 根据市场状态自适应（通过 config 传入或使用默认权重）
  - 惩罚项: 样本量不足 (<5 笔交易) 扣 12 分，<12 笔扣 5 分
"""

from dataclasses import dataclass, field

DEFAULT_WEIGHTS = {
    "total_return":    0.22,   # 总收益
    "annual_return":   0.12,   # 年化收益
    "sharpe_ratio":    0.18,   # 夏普比率
    "profit_factor":   0.14,   # 盈亏比
    "win_rate":        0.09,   # 胜率
    "max_drawdown":    0.15,   # 最大回撤 (负向：越小越好)
    "equity_stability": 0.10,  # 权益曲线稳定性
}


@dataclass
class ScoreResult:
    overall: float        # 0-100
    grade: str            # A/B/C/D/E
    components: dict      # 各维度 0-100 分项
    summary: dict         # 摘要指标


class StrategyScorer:
    """按回测结果计算综合评分。"""

    def __init__(self, weights: dict = None):
        self.weights = weights or DEFAULT_WEIGHTS

    def score(self, backtest_result: dict) -> ScoreResult:
        """对单次回测结果评分。"""
        ...

    def rank(self, scored_candidates: list[dict]) -> list[dict]:
        """按 overall 降序排列，附加 rank 字段。"""
        ...
```

### 6.4 策略变体生成器

```python
# 新建文件: backend/src/services/variant_generator.py

"""从基准策略 + 参数空间生成候选变体。

支持三种生成模式:
  1. grid:   参数空间笛卡尔积 → 随机打乱 → 截取 max_variants 个
  2. random: 参数空间内随机采样 max_variants 次
  3. llm:    LLM 根据 Regime 输出建议参数 (Phase 5 联动)

参数空间定义示例:
  {
    "strategy_config.risk.stop_loss_pct": [0.01, 0.02, 0.03, 0.05],
    "strategy_config.risk.take_profit_pct": [0.03, 0.05, 0.08, 0.10],
    "top_n": [3, 5, 10, 20],
  }
"""

class VariantGenerator:
    def generate(self, base_snapshot: dict, parameter_space: dict,
                 method: str = "grid", max_variants: int = 24) -> list[dict]:
        """生成候选策略变体列表。每个变体是 base_snapshot 的深拷贝 + 参数覆盖。"""
        ...
```

### 6.5 ExperimentNode — 核心工作流节点

```python
# 新建文件: backend/src/workflow/nodes/experiment_nodes.py

@register_node
class ExperimentNode(BaseNode):
    """实验管线节点 — 自动化策略研究闭环。

    输入:
      - strategy/df_ohlcv → 基准策略和数据
      - regime/PARAMS (可选) → 市场状态 (连接 RegimeNode 输出)
      
    输出:
      - best_strategy/PARAMS → 最优策略配置
      - all_results/EXPERIMENT_RESULT → 全部候选排名
      - best_backtest/BACKTEST_RESULT → 最优策略的回测结果

    工作流程:
      1. Regime 识别 (或复用上游 RegimeNode 输出)
      2. VariantGenerator 生成 N 个候选策略
      3. 并行回测所有候选 (通过 async 并发)
      4. StrategyScorer 评分 → 排名
      5. 输出最优策略
    """
    node_type = "experiment"
    category = "analysis"
    label = "Experiment Pipeline"
    description = "Regime-aware strategy optimization: generate variants → batch backtest → score → rank → best"
    icon = "FlaskConical"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("strategy", PortType.PARAMS, required=False),
        BaseNode.in_port("ohlcv", PortType.DF_OHLCV, required=False),
        BaseNode.in_port("regime", PortType.PARAMS, required=False),
    ]
    outputs = [
        BaseNode.out_port("best_strategy", PortType.PARAMS),
        BaseNode.out_port("all_results", PortType.EXPERIMENT_RESULT),
        BaseNode.out_port("best_backtest", PortType.BACKTEST_RESULT),
    ]
    config_schema = {
        "parameter_space": {
            "title": "Parameter Space (JSON)",
            "type": "string",
            "default": '{"top_n": [3,5,10,20], "momentum_window": [10,20,30,60]}',
            "description": "JSON object: key → [value1, value2, ...]",
        },
        "method": {
            "title": "Search Method",
            "type": "string",
            "enum": ["grid", "random"],
            "default": "grid",
        },
        "max_variants": {
            "title": "Max Variants",
            "type": "integer",
            "default": 24,
            "minimum": 4,
            "maximum": 200,
        },
        "scoring_weights": {
            "title": "Scoring Weights (JSON)",
            "type": "string",
            "default": "",
            "description": "Custom weight overrides. Empty = use defaults.",
        },
    }
```

### 6.6 ScoreNode — 评分节点

```python
@register_node
class ScoreNode(BaseNode):
    """策略评分节点 — 对回测结果进行多因子评分。

    输入:
      - backtest_result/BACKTEST_RESULT → 回测结果
      - regime/PARAMS (可选) → 市场状态（用于自适应权重）

    输出:
      - score/SCORE_RESULT → 0-100 综合评分 + 分项
    """
    node_type = "score"
    category = "analysis"
    label = "Score Strategy"
    description = "Multi-factor strategy scoring: return, sharpe, drawdown, win rate, stability"
    icon = "Award"

    inputs = [
        BaseNode.in_port("backtest_result", PortType.BACKTEST_RESULT),
        BaseNode.in_port("regime", PortType.PARAMS, required=False),
    ]
    outputs = [
        BaseNode.out_port("score", PortType.SCORE_RESULT),
    ]
```

### 6.7 RankSelectNode — 排名选择节点

```python
@register_node
class RankSelectNode(BaseNode):
    """排名选择节点 — 从多个评分结果中选择 Top-N。

    输入:
      - scores/SCORE_RESULT (可多次连接，多对一聚合)
      
    输出:
      - top_results/PARAMS → Top-N 排名列表
    """
    node_type = "rank_select"
    category = "analysis"
    label = "Rank & Select"
    ...
```

---

## 7. Phase 4：市场状态识别节点

### 7.1 设计要点

**目标**：给定 OHLCV 数据，输出当前市场状态分类 + 推荐策略族 + 置信度。

**适配方式**：新增 `RegimeNode` 工作流节点，输出 `REGIME_RESULT` 端口类型。

### 7.2 状态分类体系

```python
# 新建文件: backend/src/services/regime_engine.py

"""A 股增强版市场状态识别引擎。

基于 6 个量化特征进行规则型分类:
  - price_change_pct:   周期价格涨跌幅
  - ema_gap_pct:        EMA10 与 EMA30 的间距
  - realized_vol_pct:   30 周期年化波动率
  - atr_pct:            14 周期 ATR 占比
  - directional_eff:    方向效率 = |总位移| / 路径长度
  - volume_ratio:       当前成交量 / 20 周期均值

分类规则:
  bull_trend:        EMA10 > EMA30 + 1% 且 方向效率 ≥ 0.55 且 涨幅 > 1%
  bear_trend:        EMA10 < EMA30 - 1% 且 方向效率 ≥ 0.55 且 跌幅 > 1%
  high_volatility:   波动率 ≥ 4.5% 或 ATR ≥ 3.5%
  range_compression: EMA 间距 ≤ 0.45% 且 方向效率 ≤ 0.38 且 ATR ≤ 2.0%
  transition:        其他情况（默认）

A 股特有状态:
  limit_up_frenzy:   涨停股占比 > 5% 且 连板股 > 10 只
  bear_grinding:     持续阴跌 (连续 10+ 天跌幅 > -0.5%/天) + 缩量
  structural_rotation: 板块轮动加速 (周度板块涨幅排名相关性 < 0.3)
"""

REGIME_PROFILES = {
    "bull_trend": {
        "label": "牛市趋势",
        "strategy_families": ["trend_following", "breakout", "pullback_continuation"],
    },
    "bear_trend": {
        "label": "熊市趋势",
        "strategy_families": ["short_trend", "breakdown", "inverse_etf"],
    },
    "range_compression": {
        "label": "区间压缩",
        "strategy_families": ["mean_reversion", "bollinger_reversion", "range_breakout_watch"],
    },
    "high_volatility": {
        "label": "高波动",
        "strategy_families": ["vol_breakout", "reduced_risk_trend", "event_driven"],
    },
    "transition": {
        "label": "过渡期",
        "strategy_families": ["hybrid", "wait_and_see", "confirmation_breakout"],
    },
    "limit_up_frenzy": {
        "label": "涨停潮",
        "strategy_families": ["limit_up_chase", "hot_money_follow"],
    },
    "bear_grinding": {
        "label": "阴跌磨底",
        "strategy_families": ["defensive_dividend", "net_nets", "reverse_repo"],
    },
}


class RegimeEngine:
    def detect(self, df: pd.DataFrame, market: str = "CN_A") -> dict:
        """检测市场状态。

        Returns:
            {
                "regime": "bull_trend",
                "label": "牛市趋势",
                "confidence": 0.78,
                "features": { ... },        # 量化特征值
                "strategy_families": [...],  # 推荐策略族
                "segments": [                # 历史分段
                    {"regime": "range_compression", "start": "2026-01-01", "end": "2026-03-15"},
                    {"regime": "bull_trend", "start": "2026-03-16", "end": "2026-06-06"},
                ],
            }
        """
        ...
```

### 7.3 RegimeNode — 工作流节点

```python
# 新建文件: backend/src/workflow/nodes/regime_nodes.py

@register_node
class RegimeNode(BaseNode):
    """市场状态识别节点。

    输入:  OHLCV 数据
    输出:  市场状态 + 推荐策略族 + 量化特征

    典型连接:
      DataLoadNode → RegimeNode → ExperimentNode
                               → StrategyNode (策略族推荐)
    """
    node_type = "regime"
    category = "analysis"
    label = "Market Regime"
    description = "Detect market state from OHLCV: bull/bear/range/volatile, with strategy family hints"
    icon = "Activity"

    inputs = [
        BaseNode.in_port("ohlcv", PortType.DF_OHLCV),
    ]
    outputs = [
        BaseNode.out_port("regime", PortType.REGIME_RESULT),
        BaseNode.out_port("features", PortType.PARAMS),
        BaseNode.out_port("segments", PortType.PARAMS),
    ]
    config_schema = {
        "market": {
            "title": "Market", "type": "string",
            "enum": ["CN_A", "CN_FUTURES", "CRYPTO", "US_EQUITY", "HK_EQUITY", "FOREX"],
            "default": "CN_A",
        },
        "enable_a_share_specific": {
            "title": "A-Share Specific States",
            "type": "boolean",
            "default": True,
            "description": "Enable limit_up_frenzy, bear_grinding, structural_rotation detection",
        },
    }
```

### 7.4 与实验管线的联动

`ExperimentNode` 接收 `RegimeNode` 输出的 `REGIME_RESULT`，据此：
1. 调整 `StrategyScorer` 的评分权重（趋势市重收益、震荡市重胜率）
2. 筛选 `VariantGenerator` 的候选策略类型
3. 为 LLM Agent 提供市场上下文

---

## 8. Phase 5：策略进化引擎

### 8.1 设计要点

你已有 [walk_forward.py](backend/src/optimize/walk_forward.py)、[bayesian.py](backend/src/optimize/bayesian.py)、[grid_search.py](backend/src/optimize/grid_search.py)，需要在它们之上增加**迭代进化循环**。

### 8.2 进化循环设计

```python
# 新建文件: backend/src/optimize/evolution.py

"""迭代策略进化引擎。

流程 (n_generations=5):
  Gen 1: Grid 搜索参数空间 → 回测全部候选 → 评分 → Top-10
  Gen 2: 在 Top-3 周围做局部随机扰动 → 回测 → 评分 → 合并排名
  Gen 3: 交叉 Top-3 的参数 (参数级交叉) → 回测 → 评分
  Gen 4: LLM 辅助微调 (可选，需 Agent 联动) → 回测 → 评分
  Gen 5: Walk-Forward 验证最优候选 → 输出帕累托前沿

防止过拟合:
  - 每代使用 OOS 70/30 分割
  - 检测 OOS 退化 (OOS 评分下降 > 40% → 标记过拟合)
  - 早停: 连续 2 代无提升 → 终止
"""

from dataclasses import dataclass, field
from enum import Enum
...
```

### 8.3 EvolutionNode — 工作流节点

```python
# 修改文件: backend/src/workflow/nodes/strategy_nodes.py
# 在现有 StrategyNode 旁边增加:

@register_node
class EvolutionNode(BaseNode):
    """策略进化节点 — 自动迭代优化策略参数。

    输入:  基准策略 + 参数空间 + OHLCV 数据
    输出:  最优策略 + 进化历史 + 帕累托前沿

    可与 ExperimentNode 串联:
      RegimeNode → ExperimentNode(gird, 粗搜索) → EvolutionNode(细进化) → BacktestNode
    """
    node_type = "evolution"
    category = "strategy"
    label = "Strategy Evolution"
    description = "Iteratively evolve strategy parameters: grid → local search → crossover → LLM refine"
    icon = "GitBranch"

    inputs = [
        BaseNode.in_port("strategy", PortType.PARAMS),
        BaseNode.in_port("ohlcv", PortType.DF_OHLCV),
        BaseNode.in_port("regime", PortType.PARAMS, required=False),
    ]
    outputs = [
        BaseNode.out_port("best_strategy", PortType.PARAMS),
        BaseNode.out_port("evolution_history", PortType.PARAMS),
        BaseNode.out_port("pareto_frontier", PortType.PARAMS),
    ]
    config_schema = {
        "n_generations": {
            "title": "Generations", "type": "integer",
            "default": 5, "minimum": 2, "maximum": 20,
        },
        "population_size": {
            "title": "Population Size", "type": "integer",
            "default": 24, "minimum": 8, "maximum": 200,
        },
        "enable_llm_refine": {
            "title": "LLM Refine (Gen 4)", "type": "boolean", "default": False,
        },
        "oos_split": {
            "title": "OOS Split Ratio", "type": "number",
            "default": 0.3, "minimum": 0.1, "maximum": 0.5,
        },
        "early_stop_no_improve": {
            "title": "Early Stop (generations)", "type": "integer",
            "default": 2, "minimum": 1, "maximum": 5,
        },
    }
```

---

## 9. Phase 6：AI 反思与自学习

### 9.1 设计要点

**目标**：记录 AI Agent 的每次分析决策，定期验证预测准确性，形成反馈闭环。

**适配方式**：后台 worker + 数据库表 + Agent 工具集成。

### 9.2 分析记忆存储

```sql
-- backend/migrations/015_analysis_memory.sql

CREATE TABLE IF NOT EXISTS analysis_memory (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(64),
    market VARCHAR(20) NOT NULL,          -- CN_A / CRYPTO / US_EQUITY
    symbol VARCHAR(20) NOT NULL,
    decision VARCHAR(20) NOT NULL,        -- bullish / bearish / neutral
    confidence INTEGER DEFAULT 50,        -- 0-100
    price_at_analysis DECIMAL(16, 4),
    reasoning TEXT,                       -- Agent 推理过程摘要
    context_snapshot JSONB,               -- 分析时的市场数据快照
    agent_response TEXT,                  -- Agent 完整输出
    -- 验证字段
    validated_at TIMESTAMP,
    actual_outcome VARCHAR(20),           -- correct / incorrect / partial
    actual_return_pct DECIMAL(10, 4),     -- 实际收益率
    was_correct BOOLEAN,                  -- 决策是否正确
    user_feedback VARCHAR(20),            -- user_correct / user_incorrect / null
    feedback_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_am_user_symbol ON analysis_memory(user_id, symbol);
CREATE INDEX idx_am_validated ON analysis_memory(validated_at) WHERE validated_at IS NULL;
CREATE INDEX idx_am_created ON analysis_memory(created_at);
```

### 9.3 反思 Worker

```python
# 新建文件: backend/src/services/reflection_worker.py

"""反思 Worker — 后台周期性验证历史 AI 决策。

流程 (每天凌晨 2:00 运行):
  1. 查询 7 天前未验证的分析记录 (LIMIT 200)
  2. 加载对应 symbol 的后续行情数据
  3. 计算实际收益率 (7 天)
  4. 判断: 
     - bullish + 上涨 → was_correct=true
     - bearish + 下跌 → was_correct=true
     - neutral + 横盘(±2%) → was_correct=true
     - 其他 → was_correct=false
  5. 更新 analysis_memory.validated_at / was_correct / actual_return_pct
  6. 计算近期准确率，若 < 45% → 记录告警日志
"""

import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ReflectionWorker:
    def __init__(self, min_age_days: int = 7, batch_size: int = 200):
        self.min_age_days = min_age_days
        self.batch_size = batch_size

    async def run_cycle(self) -> dict:
        """运行一次验证周期。返回 {validated, correct, incorrect, accuracy}。"""
        ...
```

### 9.4 Agent 工具集成

在 `AgentNode` 的工具列表中增加 `remember_analysis` 工具，Agent 可以在分析完成后自动记录决策：

```python
# 修改文件: backend/src/agent/tools.py
# 新增 remember_analysis_tool:

{
    "name": "remember_analysis",
    "description": "Record this analysis decision for future reflection and learning",
    "parameters": {
        "symbol": "str",
        "decision": "bullish | bearish | neutral",
        "confidence": "int (0-100)",
        "reasoning": "str (brief summary)",
    }
}
```

---

## 10. Phase 7：i18n 与分发

### 10.1 多语言扩展

**现状**：`frontend/src/lib/i18n.tsx` 支持 zh/en。

**扩展**：增加 ja (日语)、ko (韩语)。参考现有 `useI18n()` hook 的 t.key 模式。

```typescript
// 修改 i18n.tsx — 增加日语和韩语翻译
const ja = {
  "nav.dashboard": "ダッシュボード",
  "nav.strategy": "戦略",
  "nav.backtest": "バックテスト",
  // ...
};

const ko = {
  "nav.dashboard": "대시보드",
  "nav.strategy": "전략",
  // ...
};
```

### 10.2 前端预构建 Docker 镜像

```yaml
# docker-compose.yml 新增 frontend 服务 (替换现有 profiles 方式):

frontend:
  image: node:20-alpine
  working_dir: /app
  ports:
    - "${FRONTEND_PORT:-5899}:80"
  volumes:
    - ./frontend:/app
  environment:
    - VITE_API_URL=http://astockpursue:8899
  command: >
    sh -c "
      npm install &&
      npx vite build --outDir dist &&
      cp -r dist/* /usr/share/nginx/html/
    "
  # 生产模式: 使用 nginx:alpine 作为 base image 预构建 SPA
  profiles:
    - frontend
```

### 10.3 GitHub Actions 自动发布

```yaml
# .github/workflows/docker-publish.yml

name: Docker Publish
on:
  push:
    tags: ["v*"]
jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build & Push Backend
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ghcr.io/${{ github.repository }}:latest
      - name: Build & Push Frontend
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          push: true
          tags: ghcr.io/${{ github.repository }}-frontend:latest
```

---

## 11. 执行路线图

```
Week │ Phase │ 产出
─────┼───────┼─────────────────────────────────────────────────────────
  1  │   0   │ Redis 缓存层上线，data_store.py 命中率 > 70%
     │       │ docker-compose.yml 更新，健康检查通过
─────┼───────┼─────────────────────────────────────────────────────────
  1  │   1   │ channels.py 增加 Telegram + Discord + Feishu 方言检测
     │       │ NotifyNode 画布节点可用
     │       │ RiskPipeline 内联通知验证通过
─────┼───────┼─────────────────────────────────────────────────────────
  2  │   2   │ BaseBroker 抽象 + BinanceBroker + OKXBroker 实现
     │       │ BrokerNode + CredentialStore + 数据库迁移
     │       │ testnet 连接测试通过
─────┼───────┼─────────────────────────────────────────────────────────
  3  │   3   │ StrategyScorer + VariantGenerator
     │       │ ExperimentNode + ScoreNode + RankSelectNode
     │       │ 端到端工作流: 数据→策略→实验→评分→最优输出
─────┼───────┼─────────────────────────────────────────────────────────
  4  │   4   │ RegimeEngine + RegimeNode
     │       │ 与 ExperimentNode 联动验证
     │       │ A 股特有状态检测 (涨停潮/阴跌/轮动)
─────┼───────┼─────────────────────────────────────────────────────────
  5  │   5   │ EvolutionNode (迭代进化循环)
     │       │ Walk-Forward + OOS 过拟合检测
─────┼───────┼─────────────────────────────────────────────────────────
  6  │   6   │ AnalysisMemory + ReflectionWorker
     │       │ Agent remember_analysis 工具
     │       │ 后台验证周期运行
─────┼───────┼─────────────────────────────────────────────────────────
  6  │   7   │ i18n ja/ko + 前端预构建 + GitHub Actions
     │       │ 文档更新
```

### 可并行执行的任务

```
Phase 0 (Redis) ─┬─→ Phase 1 (通知) ──→ (独立，无依赖)
                 │
                 ├─→ Phase 2 (券商) ──→ (独立，无依赖)
                 │
                 └─→ Phase 3 (实验) ──→ Phase 4 (Regime) ──→ Phase 5 (进化)
                                                        │
                                                        └─→ Phase 6 (反思) (独立)
```

---

## 12. 文件变更清单

### 新建文件 (~30 个)

```
backend/src/cache/__init__.py
backend/src/cache/redis_client.py
backend/src/cache/data_cache.py
backend/src/trading/brokers/__init__.py
backend/src/trading/brokers/base.py
backend/src/trading/brokers/factory.py
backend/src/trading/brokers/binance.py
backend/src/trading/brokers/okx.py
backend/src/trading/credential_store.py
backend/src/services/strategy_scorer.py
backend/src/services/variant_generator.py
backend/src/services/regime_engine.py
backend/src/services/reflection_worker.py
backend/src/optimize/evolution.py
backend/src/workflow/nodes/notify_nodes.py
backend/src/workflow/nodes/experiment_nodes.py
backend/src/workflow/nodes/regime_nodes.py
backend/src/api/experiment_routes.py
backend/src/api/notification_routes.py
backend/migrations/014_broker_credentials.sql
backend/migrations/015_analysis_memory.sql
backend/tests/test_strategy_scorer.py
backend/tests/test_regime_engine.py
backend/tests/test_variant_generator.py
backend/tests/test_broker_factory.py
.github/workflows/docker-publish.yml
```

### 修改文件 (~15 个)

```
docker-compose.yml
backend/.env.example
backend/requirements.txt
backend/backtest/data_store.py            ← Redis L0 缓存
backend/src/workflow/schema.py            ← 新增 PortType
backend/src/workflow/node_registry.py     ← 新增 init 导入
backend/src/workflow/nodes/trading_nodes.py  ← BrokerNode
backend/src/workflow/nodes/strategy_nodes.py ← EvolutionNode
backend/src/notify/channels.py            ← Telegram/Discord/Feishu
backend/src/notify/engine.py              ← 信号上下文
backend/src/trading/risk_pipeline.py      ← 内联通知
backend/src/agent/tools.py                ← remember_analysis
backend/src/api/__init__.py               ← 路由注册
frontend/src/lib/i18n.tsx                 ← ja, ko
frontend/src/workflow/canvas/NodePalette.tsx ← 新节点
```

### 不需修改的核心文件（保持不变）

```
backend/src/trading/engine.py          ← on_bar() 管道不变
backend/src/trading/signal_adapter.py  ← 调度逻辑不变
backend/src/factors/**/*               ← 因子工厂不变
backend/src/workflow/workflow_engine.py ← Kahn 引擎不变
backend/backtest/engines/**/*           ← 9 种引擎不变
```

---

## 附录：关键设计决策

1. **为什么 Redis 是可选的**
   - `get_redis()` 返回 None 时自动降级，不阻塞系统启动
   - 适合开发环境（无 Docker）和生产环境（有 Docker）无缝切换

2. **为什么券商用 ccxt 而不是原生 SDK**
   - CCXT 已在项目依赖中（`ccxt>=4.0.0`）
   - 统一 API，减少重复代码
   - 覆盖 Binance/OKX/Bybit 等 100+ 交易所

3. **为什么实验管线是多个节点而不是一个大节点**
   - 遵循工作流哲学：每个节点一个职责
   - 用户可以自由组合（只用 Scorer 不用 Experiment）
   - 中间结果可检查、缓存、复用

4. **为什么 Regime 用规则型而不是 ML 型**
   - 规则可解释、可调试、可审查
   - 不需要标注数据，立即可用
   - 后续阶段可以接入 GP 引擎做 Regime 进化
