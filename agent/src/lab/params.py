"""Indicator parameter and strategy config parsers.

Parses ``# @param`` and ``# @strategy`` annotations from indicator source code.
Ported from QuantDinger's indicator_params.py.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class StrategyConfigParser:
    """Parse ``# @strategy`` annotations for risk/position configuration.

    Supported annotations::

        # @strategy stopLossPct 0.02
        # @strategy takeProfitPct 0.05
        # @strategy entryPct 0.5
        # @strategy trailingEnabled true
        # @strategy trailingStopPct 0.02
        # @strategy trailingActivationPct 0.03
        # @strategy tradeDirection long
    """

    STRATEGY_PATTERN = re.compile(
        r"#\s*@strategy\s+(\w+)\s*:?\s*(\S+)\s*(.*)",
        re.IGNORECASE,
    )

    VALID_KEYS: dict[str, dict[str, Any]] = {
        "stopLossPct":           {"type": "float", "min": 0, "max": 1},
        "takeProfitPct":         {"type": "float", "min": 0, "max": 5},
        "entryPct":              {"type": "float", "min": 0.01, "max": 1},
        "trailingEnabled":       {"type": "bool"},
        "trailingStopPct":       {"type": "float", "min": 0, "max": 1},
        "trailingActivationPct": {"type": "float", "min": 0, "max": 1},
        "tradeDirection":        {"type": "str", "enum": ["long", "short", "both"]},
    }

    @classmethod
    def parse(cls, code: str) -> dict[str, Any]:
        """Parse @strategy annotations, returning a config dict."""
        config: dict[str, Any] = {}
        if not code:
            return config
        for line in code.split("\n"):
            line = line.strip()
            m = cls.STRATEGY_PATTERN.match(line)
            if not m:
                continue
            key = m.group(1)
            raw_val = m.group(2)
            if key not in cls.VALID_KEYS:
                continue
            spec = cls.VALID_KEYS[key]
            val = cls._convert(raw_val, spec)
            if val is not None:
                config[key] = val
        return config

    @classmethod
    def _convert(cls, raw: str, spec: dict) -> Any:
        t = spec["type"]
        try:
            if t == "float":
                v = float(raw)
                v = max(spec.get("min", v), min(spec.get("max", v), v))
                return round(v, 6)
            elif t == "int":
                v = int(raw)
                v = max(spec.get("min", v), min(spec.get("max", v), v))
                return v
            elif t == "bool":
                return raw.lower() in ("true", "1", "yes", "on")
            elif t == "str":
                if "enum" in spec and raw not in spec["enum"]:
                    return spec["enum"][0]
                return raw
        except (ValueError, TypeError):
            return None
        return None

    @classmethod
    def generate_annotations(cls, config: dict[str, Any]) -> str:
        """Generate @strategy annotation lines from a config dict."""
        lines = []
        for key, spec in cls.VALID_KEYS.items():
            if key in config:
                val = config[key]
                if spec["type"] == "bool":
                    val = "true" if val else "false"
                lines.append(f"# @strategy {key} {val}")
        return "\n".join(lines)


class IndicatorParamsParser:
    """Parse ``# @param`` declarations in indicator code.

    Format::

        # @param param_name type default_value description
        # @param ma_fast int 5 short-term MA period
        # @param threshold float 0.5 entry threshold range=0.1:1.0:0.1

    Supported types: int, float, bool, str/string.

    Optional sweep markers in description (numeric params only):
        ``range=lo:hi:step`` or ``values=a,b,c``
    """

    PARAM_PATTERN = re.compile(
        r"#\s*@param\s+(\w+)\s+(int|float|bool|str|string)\s+(\S+)\s*(.*)",
        re.IGNORECASE,
    )

    _RANGE_RE = re.compile(
        r"range\s*=\s*(-?\d+(?:\.\d+)?)\s*:\s*(-?\d+(?:\.\d+)?)\s*:\s*(-?\d+(?:\.\d+)?)",
        re.IGNORECASE,
    )
    _VALUES_RE = re.compile(r"values\s*=\s*([^\s]+)", re.IGNORECASE)

    @classmethod
    def parse_params(cls, code: str) -> list[dict[str, Any]]:
        """Parse @param declarations, returning a list of param definitions."""
        params: list[dict[str, Any]] = []
        if not code:
            return params

        for line in code.split("\n"):
            line = line.strip()
            m = cls.PARAM_PATTERN.match(line)
            if not m:
                continue

            name = m.group(1)
            param_type = m.group(2).lower()
            default_str = m.group(3)
            description = m.group(4).strip() if m.group(4) else ""

            default = cls._convert_value(default_str, param_type)

            if param_type == "string":
                param_type = "str"

            values: list[Any] | None = None
            if param_type in ("int", "float"):
                values = cls._extract_sweep_values(description, param_type)
            description = cls._strip_sweep_markers(description)

            entry: dict[str, Any] = {
                "name": name,
                "type": param_type,
                "default": default,
                "description": description,
            }
            if values:
                entry["values"] = values
            params.append(entry)

        return params

    @classmethod
    def _extract_sweep_values(cls, description: str, param_type: str) -> list[Any] | None:
        if not description:
            return None
        m_values = cls._VALUES_RE.search(description)
        if m_values:
            raw = m_values.group(1)
            out: list[Any] = []
            for token in raw.split(","):
                token = token.strip()
                if not token:
                    continue
                converted = cls._convert_value(token, param_type)
                if converted is not None:
                    out.append(converted)
            seen: set[Any] = set()
            unique: list[Any] = []
            for v in out:
                if v in seen:
                    continue
                seen.add(v)
                unique.append(v)
            return unique or None

        m_range = cls._RANGE_RE.search(description)
        if m_range:
            try:
                lo = float(m_range.group(1))
                hi = float(m_range.group(2))
                step = float(m_range.group(3))
            except (TypeError, ValueError):
                return None
            if step == 0 or (hi - lo) * step < 0:
                return None
            out = []
            cursor = lo
            max_count = 1024
            while (step > 0 and cursor <= hi + 1e-9) or (step < 0 and cursor >= hi - 1e-9):
                if param_type == "int":
                    out.append(int(round(cursor)))
                else:
                    out.append(round(cursor, 8))
                cursor += step
                if len(out) >= max_count:
                    break
            seen = set()
            unique = []
            for v in out:
                if v in seen:
                    continue
                seen.add(v)
                unique.append(v)
            return unique or None
        return None

    @classmethod
    def _strip_sweep_markers(cls, description: str) -> str:
        cleaned = cls._RANGE_RE.sub("", description or "")
        cleaned = cls._VALUES_RE.sub("", cleaned)
        return cleaned.strip()

    @classmethod
    def _convert_value(cls, value_str: str, param_type: str) -> Any:
        try:
            param_type = param_type.lower()
            if param_type == "int":
                return int(value_str)
            elif param_type == "float":
                return float(value_str)
            elif param_type == "bool":
                return value_str.lower() in ("true", "1", "yes", "on")
            else:
                return value_str
        except (ValueError, TypeError):
            return value_str

    @classmethod
    def merge_params(
        cls, declared_params: list[dict], user_params: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge declared params with user-provided values, falling back to defaults."""
        result: dict[str, Any] = {}
        for param in declared_params:
            name = param["name"]
            param_type = param["type"]
            default = param["default"]

            if name in user_params:
                result[name] = cls._convert_value(str(user_params[name]), param_type)
            else:
                result[name] = default
        return result

    @classmethod
    def generate_params_block(cls, params: list[dict[str, Any]]) -> str:
        """Generate @param annotation lines from a params list."""
        lines = []
        for p in params:
            lines.append(
                f"# @param {p['name']} {p['type']} {p['default']} {p.get('description', '')}"
            )
        return "\n".join(lines)

    @classmethod
    def inject_params_into_code(cls, code: str, user_params: dict[str, Any]) -> str:
        """Replace param defaults in code with user-specified values.

        Finds lines like ``# @param fast_ma int 5 ...`` and rewrites
        the default value to match ``user_params``.
        """

        def _replace(m: re.Match) -> str:
            name = m.group(1)
            if name in user_params:
                return f"# @param {name} {m.group(2)} {user_params[name]} {m.group(4)}"
            return m.group(0)

        return cls.PARAM_PATTERN.sub(_replace, code)
