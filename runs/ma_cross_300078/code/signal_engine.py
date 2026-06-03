"""双均线金叉/死叉信号引擎。

MA5 上穿 MA20（金叉）→ 做多信号 1
MA5 下穿 MA20（死叉）→ 平仓信号 0
纯 pandas 实现，无外部技术分析库依赖。
"""

from typing import Dict

import pandas as pd


class SignalEngine:
    """双均线交叉信号引擎。

    通过 MA 快慢线位置关系生成交易信号：
    - MA5 > MA20 → 1.0（持有多头仓位）
    - MA5 <= MA20 → 0.0（空仓观望）

    Attributes:
        fast_period: 快线周期，默认 5。
        slow_period: 慢线周期，默认 20。

    Example:
        >>> engine = SignalEngine(fast_period=5, slow_period=20)
        >>> signals = engine.generate({"300078.SZ": df})
        >>> signals["300078.SZ"].value_counts()
    """

    def __init__(self, fast_period: int = 5, slow_period: int = 20):
        """初始化双均线信号引擎。

        Args:
            fast_period: 快线（短期均线）周期，默认 5。
            slow_period: 慢线（长期均线）周期，默认 20。
        """
        self.fast_period = fast_period
        self.slow_period = slow_period

    def generate(
        self, data_map: Dict[str, pd.DataFrame]
    ) -> Dict[str, pd.Series]:
        """根据双均线位置关系生成交易信号。

        Args:
            data_map: 标的代码到 OHLCV DataFrame 的映射。
                DataFrame 需包含 close 列，index 为 datetime。

        Returns:
            标的代码到信号 Series 的映射（1.0=做多, 0.0=观望）。
        """
        result = {}
        warmup = self.slow_period

        for symbol, df in data_map.items():
            signal = pd.Series(0.0, index=df.index, dtype=float)

            if len(df) < warmup:
                result[symbol] = signal
                continue

            close = df["close"]

            # 计算双均线
            ma_fast = close.rolling(window=self.fast_period, min_periods=self.fast_period).mean()
            ma_slow = close.rolling(window=self.slow_period, min_periods=self.slow_period).mean()

            # 金叉做多 / 死叉平仓
            signal = (ma_fast > ma_slow).astype(float)

            # 前 warmup-1 根 K 线信号置 0（均线未就绪）
            signal.iloc[:warmup - 1] = 0.0

            result[symbol] = signal

        return result
