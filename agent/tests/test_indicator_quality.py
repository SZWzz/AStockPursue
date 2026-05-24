from __future__ import annotations

from src.lab.quality import analyze_indicator_code_quality


def _code_with(**overrides: str) -> str:
    """Build indicator code from named fragments. Override defaults with empty string to omit."""
    defaults = {
        "name": 'my_indicator_name = "Test"\n',
        "desc": 'my_indicator_description = "A test indicator"\n',
        "copy": "df = df.copy()\n",
        "buy": 'df["buy"] = df["close"] > df["close"].shift(1)\n',
        "sell": 'df["sell"] = df["close"] < df["close"].shift(1)\n',
        "output": 'output = {"name": "Test", "plots": [], "signals": []}\n',
    }
    merged = {**defaults, **overrides}
    return "".join(merged[k] for k in defaults)


def _find_hint(hints: list[dict], code: str) -> dict | None:
    return next((h for h in hints if h["code"] == code), None)


class TestEmptyCode:
    def test_empty_string(self) -> None:
        hints = analyze_indicator_code_quality("")
        assert _find_hint(hints, "EMPTY_CODE") is not None

    def test_whitespace_only(self) -> None:
        hints = analyze_indicator_code_quality("   \n  ")
        assert _find_hint(hints, "EMPTY_CODE") is not None


class TestMissingContract:
    def test_missing_name(self) -> None:
        code = _code_with(name="", desc="", buy="")
        hints = analyze_indicator_code_quality(code)
        assert _find_hint(hints, "MISSING_INDICATOR_NAME") is not None

    def test_missing_description(self) -> None:
        code = _code_with(name="my_indicator_name = 'X'\n", desc="", buy="")
        hints = analyze_indicator_code_quality(code)
        assert _find_hint(hints, "MISSING_INDICATOR_DESCRIPTION") is not None

    def test_missing_df_copy(self) -> None:
        code = _code_with(copy="", buy="", output="")
        hints = analyze_indicator_code_quality(code)
        assert _find_hint(hints, "MISSING_DF_COPY") is not None

    def test_missing_output(self) -> None:
        code = _code_with(output="")
        hints = analyze_indicator_code_quality(code)
        assert _find_hint(hints, "MISSING_OUTPUT") is not None

    def test_missing_buy_sell(self) -> None:
        code = _code_with(buy="", sell="")
        hints = analyze_indicator_code_quality(code)
        assert _find_hint(hints, "MISSING_BUY_SELL_COLUMNS") is not None


class TestFutureDataLeak:
    def test_shift_negative_detected(self) -> None:
        code = _code_with() + 'df["future"] = df["close"].shift(-1)\n'
        hints = analyze_indicator_code_quality(code)
        leak = _find_hint(hints, "FUTURE_DATA_LEAK")
        assert leak is not None
        assert leak["params"]["kind"] == "shift"

    def test_iloc_plus_detected(self) -> None:
        code = _code_with() + "x = df.iloc[i + 5]\n"
        hints = analyze_indicator_code_quality(code)
        leak = _find_hint(hints, "FUTURE_DATA_LEAK")
        assert leak is not None
        assert leak["params"]["kind"] == "iloc"

    def test_shift_positive_not_flagged(self) -> None:
        code = _code_with() + 'prev = df["close"].shift(1)\n'
        hints = analyze_indicator_code_quality(code)
        assert _find_hint(hints, "FUTURE_DATA_LEAK") is None


class TestNdarrayMisuse:
    def test_direct_chaining_detected(self) -> None:
        code = _code_with(output="") + "x = np.where(df['close'] > 0, 1, 0).rolling(10).mean()\n"
        hints = analyze_indicator_code_quality(code)
        assert _find_hint(hints, "NDARRAY_PANDAS_METHOD_MISUSE") is not None

    def test_tainted_variable_detected(self) -> None:
        code = _code_with(output="") + "x = np.where(df['close'] > 0, 1, 0)\ny = x.rolling(10).mean()\n"
        hints = analyze_indicator_code_quality(code)
        assert _find_hint(hints, "NDARRAY_PANDAS_METHOD_MISUSE") is not None

    def test_helper_returns_ndarray(self) -> None:
        code = _code_with(output="") + """
def calc():
    return np.where(df['close'] > 0, 1, 0)
"""
        hints = analyze_indicator_code_quality(code)
        assert _find_hint(hints, "HELPER_RETURNS_NDARRAY") is not None


class TestStrategyAnnotations:
    def test_no_annotations(self) -> None:
        code = _code_with()
        hints = analyze_indicator_code_quality(code)
        assert _find_hint(hints, "NO_STRATEGY_ANNOTATIONS") is not None

    def test_no_stop_and_take_profit(self) -> None:
        code = _code_with() + "# @strategy entryPct 0.5\n"
        hints = analyze_indicator_code_quality(code)
        assert _find_hint(hints, "NO_STOP_AND_TAKE_PROFIT") is not None

    def test_unknown_strategy_key(self) -> None:
        code = _code_with() + "# @strategy bogusKey 123\n"
        hints = analyze_indicator_code_quality(code)
        assert _find_hint(hints, "UNKNOWN_STRATEGY_KEY") is not None


class TestGoodCode:
    def test_complete_indicator_minimal_issues(self) -> None:
        code = '''
my_indicator_name = "Complete RSI"
my_indicator_description = "A complete RSI strategy with risk controls"
# @param period int 14 RSI period
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05
df = df.copy()
period = params.get("period", 14)
delta = df["close"].diff()
gain = delta.where(delta > 0, 0.0)
loss = (-delta).where(delta < 0, 0.0)
avg_gain = gain.rolling(period).mean()
avg_loss = loss.rolling(period).mean()
rs = avg_gain / avg_loss.replace(0, np.nan)
rsi = 100.0 - (100.0 / (1.0 + rs))
df["buy"] = rsi < 30
df["sell"] = rsi > 70
output = {
    "name": my_indicator_name,
    "plots": [{"name": "RSI", "data": rsi.tolist(), "color": "#9C27B0", "overlay": False}],
    "signals": [],
}
'''
        hints = analyze_indicator_code_quality(code)
        errors = [h for h in hints if h["severity"] == "error"]
        assert len(errors) == 0, f"Unexpected errors: {[{e['code']: e.get('params', {})} for e in errors]}"


class TestBasicHintPresence:
    def test_empty_code_returns_error(self) -> None:
        hints = analyze_indicator_code_quality("")
        assert len(hints) >= 1
        assert hints[0]["severity"] == "error"

    def test_all_hints_have_code_field(self) -> None:
        code = _code_with()
        hints = analyze_indicator_code_quality(code)
        for h in hints:
            assert "code" in h
            assert "severity" in h
            assert h["severity"] in ("error", "warn", "info")
