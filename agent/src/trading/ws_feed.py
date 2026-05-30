"""WebSocket real-time market data feeds.

Replaces REST polling in LiveDriver with push-based WebSocket streams
for lower latency and true real-time trading.

Abstract base: ``MarketFeed``
Implementations:
  - ``OKXWebSocketFeed`` — crypto via OKX public WebSocket
  - ``EastMoneyWebSocketFeed`` — A-share via EastMoney push2 WebSocket
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Callback types ────────────────────────────────────────────────────────────

OnBar = Callable[[str, pd.Timestamp, float, float, float, float, float], None]
"""Callback: on_bar(code, timestamp, open, high, low, close, volume)."""

OnError = Callable[[str, Exception], None]
"""Callback: on_error(code, exception)."""


# ── Abstract base ─────────────────────────────────────────────────────────────

class MarketFeed(ABC):
    """Abstract WebSocket market data feed.

    Subclasses implement ``_subscribe()`` / ``_unsubscribe()`` / ``_connect()``
    and call ``_emit_bar()`` when a new candle is received.
    """

    def __init__(self) -> None:
        self._on_bar: OnBar | None = None
        self._on_error: OnError | None = None
        self._subscribed: set[str] = set()
        self._running = False
        self._thread: threading.Thread | None = None

    def on_bar(self, cb: OnBar) -> None:
        self._on_bar = cb

    def on_error(self, cb: OnError) -> None:
        self._on_error = cb

    def subscribe(self, codes: list[str]) -> None:
        """Subscribe to bar updates for *codes* (idempotent)."""
        new_codes = [c for c in codes if c not in self._subscribed]
        if not new_codes:
            return
        self._subscribed.update(new_codes)
        if self._running:
            self._subscribe(new_codes)

    def unsubscribe(self, codes: list[str]) -> None:
        """Unsubscribe from *codes*."""
        for c in codes:
            self._subscribed.discard(c)
        if self._running:
            self._unsubscribe(codes)

    def start(self) -> None:
        """Start the WebSocket feed in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="ws-feed")
        self._thread.start()
        logger.info("%s started", type(self).__name__)

    def stop(self) -> None:
        """Stop the feed and wait for the thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("%s stopped", type(self).__name__)

    # ── Subclass interface ────────────────────────────────────────────────

    @abstractmethod
    def _connect(self) -> None:
        """Establish WebSocket connection."""

    @abstractmethod
    def _subscribe(self, codes: list[str]) -> None:
        """Send subscribe message for *codes*."""

    @abstractmethod
    def _unsubscribe(self, codes: list[str]) -> None:
        """Send unsubscribe message for *codes*."""

    @abstractmethod
    def _recv_loop(self) -> None:
        """Blocking receive loop. Calls _emit_bar for each new candle."""

    # ── Internal ──────────────────────────────────────────────────────────

    def _run_loop(self) -> None:
        """Main loop with auto-reconnect."""
        while self._running:
            try:
                self._connect()
                if self._subscribed:
                    self._subscribe(list(self._subscribed))
                self._recv_loop()
            except Exception as exc:
                logger.warning("%s error: %s — reconnecting in 5s", type(self).__name__, exc)
                if self._on_error:
                    try:
                        self._on_error("__feed__", exc)
                    except Exception:
                        pass
                time.sleep(5)

    def _emit_bar(
        self,
        code: str,
        ts: pd.Timestamp,
        open_: float,
        high: float,
        low: float,
        close: float,
        volume: float,
    ) -> None:
        if self._on_bar:
            try:
                self._on_bar(code, ts, open_, high, low, close, volume)
            except Exception:
                logger.debug("on_bar callback failed for %s", code, exc_info=True)


# ── OKX WebSocket Feed ────────────────────────────────────────────────────────

class OKXWebSocketFeed(MarketFeed):
    """OKX public WebSocket — crypto candlestick channel."""

    _WS_URL = "wss://ws.okx.com:8443/ws/v5/public"

    def __init__(self, interval: str = "1H"):
        super().__init__()
        self._interval = interval
        self._ws: Optional[any] = None

    def _connect(self) -> None:
        import websocket
        self._ws = websocket.create_connection(self._WS_URL, timeout=15)
        logger.debug("OKX WS connected")

    def _subscribe(self, codes: list[str]) -> None:
        if not self._ws:
            return
        args = []
        for c in codes:
            inst = c.replace("/", "-").replace("USDT", "-USDT").upper()
            if not inst.endswith("-USDT"):
                inst = inst + "-USDT"
            args.append({"channel": f"candle{self._interval}", "instId": inst})
        msg = json.dumps({"op": "subscribe", "args": args})
        self._ws.send(msg)
        logger.debug("OKX WS subscribed: %s", codes)

    def _unsubscribe(self, codes: list[str]) -> None:
        if not self._ws:
            return
        args = []
        for c in codes:
            inst = c.replace("/", "-").replace("USDT", "-USDT").upper()
            if not inst.endswith("-USDT"):
                inst = inst + "-USDT"
            args.append({"channel": f"candle{self._interval}", "instId": inst})
        msg = json.dumps({"op": "unsubscribe", "args": args})
        self._ws.send(msg)

    def _recv_loop(self) -> None:
        assert self._ws is not None
        while self._running:
            raw = self._ws.recv()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if "data" not in data:
                continue

            for item in data["data"]:
                candle = item[0]
                # OKX candle format: [ts, open, high, low, close, vol, ...]
                if len(candle) < 6:
                    continue
                code = data.get("arg", {}).get("instId", "UNKNOWN")
                ts = pd.Timestamp(int(candle[0]) / 1000, unit="s")
                self._emit_bar(
                    code, ts,
                    float(candle[1]), float(candle[2]), float(candle[3]),
                    float(candle[4]), float(candle[5]),
                )


# ── EastMoney WebSocket Feed ──────────────────────────────────────────────────

class EastMoneyWebSocketFeed(MarketFeed):
    """EastMoney push2 WebSocket — A-share real-time candlestick updates.

    Uses the same push2 endpoint family as the EastMoney HTTP loader but via
    WebSocket for push-based delivery.
    """

    def __init__(self, interval: str = "1D"):
        super().__init__()
        self._interval = interval
        self._ws: Optional[any] = None
        self._last_bar_ts: dict[str, pd.Timestamp] = {}

    def _connect(self) -> None:
        import websocket
        # EastMoney public WebSocket for stock quotes
        self._ws = websocket.create_connection(
            "wss://push2.eastmoney.com/api/qt/ws",
            timeout=15,
        )
        logger.debug("EastMoney WS connected")

    def _subscribe(self, codes: list[str]) -> None:
        if not self._ws:
            return
        for code in codes:
            market = "1" if (code.strip().upper().lstrip("SH SZ ")).startswith(("6", "9")) else "0"
            digits = "".join(c for c in code if c.isdigit())
            secid = f"{market}.{digits}"
            # Subscribe to kline push
            msg = json.dumps({
                "cmd": "sub",
                "topics": [f"kline_{secid}_{self._interval}"],
            })
            self._ws.send(msg)
        logger.debug("EastMoney WS subscribed: %s", codes)

    def _unsubscribe(self, codes: list[str]) -> None:
        if not self._ws:
            return
        for code in codes:
            market = "1" if code.strip().upper().lstrip("SH SZ ").startswith(("6", "9")) else "0"
            digits = "".join(c for c in code if c.isdigit())
            secid = f"{market}.{digits}"
            msg = json.dumps({
                "cmd": "unsub",
                "topics": [f"kline_{secid}_{self._interval}"],
            })
            self._ws.send(msg)

    def _recv_loop(self) -> None:
        assert self._ws is not None
        import websocket
        while self._running:
            try:
                self._ws.settimeout(5)
                raw = self._ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except Exception:
                raise

            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # EastMoney push format varies; try common patterns
            for item in data if isinstance(data, list) else [data]:
                if not isinstance(item, dict):
                    continue
                code = str(item.get("c", item.get("code", "")))
                if not code or not code[0].isdigit():
                    continue
                ts_raw = item.get("t", item.get("time", ""))
                ts = pd.Timestamp(int(ts_raw) / 1000, unit="s") if ts_raw and str(ts_raw).isdigit() else pd.Timestamp.now()

                o = float(item.get("o", item.get("open", 0)))
                h = float(item.get("h", item.get("high", 0)))
                l = float(item.get("l", item.get("low", 0)))
                c = float(item.get("c", item.get("close", 0)))
                v = float(item.get("v", item.get("volume", 0)))

                if o == 0 and h == 0 and l == 0 and c == 0:
                    continue

                # Deduplicate: only emit if bar timestamp changed
                last_ts = self._last_bar_ts.get(code)
                if last_ts is not None and ts <= last_ts:
                    continue
                self._last_bar_ts[code] = ts

                self._emit_bar(code, ts, o, h, l, c, v)
