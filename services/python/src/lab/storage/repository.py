"""File-based indicator repository.

Stores user-authored indicator scripts on disk under
``~/.AStockPursue/indicators/``. Each indicator is a self-contained ``.py`` file
following the QuantDinger contract (my_indicator_name, my_indicator_description,
output dict, df['buy']/df['sell']).

Also supports bridging to the Alpha Zoo: a mature indicator can be *promoted*
into a zoo factor with a ``__alpha_meta__`` block and a ``compute(panel)``
function added automatically.
"""

from __future__ import annotations

import logging
import os
import tempfile
import re
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config.paths import get_runtime_root

logger = logging.getLogger(__name__)

_META_RE = re.compile(r"^\s*my_indicator_name\s*=\s*['\"](.+?)['\"]\s*$", re.MULTILINE)
_DESC_RE = re.compile(
    r"^\s*my_indicator_description\s*=\s*['\"](.+?)['\"]\s*$", re.MULTILINE
)
_SAFE_FILENAME_RE = re.compile(r"^[\w\-]+\.py$")


@dataclass
class IndicatorInfo:
    """Lightweight metadata about a stored indicator."""
    id: str
    name: str
    description: str
    file_path: Path
    created_at: str
    updated_at: str
    param_count: int = 0
    strategy_config: dict[str, Any] = field(default_factory=dict)


def _indicators_dir() -> Path:
    root = get_runtime_root()
    d = root / "indicators"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_filename(name: str) -> str:
    """Convert an indicator name to a safe filename."""
    safe = re.sub(r"[^\w\-]", "_", name).strip("_").lower()
    if not safe:
        safe = "indicator"
    return f"{safe}.py"


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically (temp file + rename, safe against concurrent writes)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _extract_meta_from_code(code: str) -> tuple[str, str]:
    """Extract indicator name and description from source code."""
    name = ""
    desc = ""
    m = _META_RE.search(code)
    if m:
        name = m.group(1).strip()[:100]
    m = _DESC_RE.search(code)
    if m:
        desc = m.group(1).strip()[:500]
    return name, desc


def extract_code_from_response(response: str) -> str:
    """Extract Python code from an agent response (may contain markdown fences)."""
    import re as _re

    pattern = _re.compile(r"```(?:python)?\s*\n(.*?)```", _re.DOTALL)
    m = pattern.search(response)
    if m:
        return m.group(1).strip()
    return response.strip()


class IndicatorRepository:
    """CRUD operations for user-authored indicator scripts."""

    def __init__(self, base_dir: Path | None = None):
        self._base_dir = base_dir or _indicators_dir()
        self._git_ready = False

    # ── Git integration ────────────────────────────────────────────────────

    def _ensure_git_repo(self) -> None:
        """Initialize git repo in indicators directory if needed."""
        if self._git_ready:
            return
        git_dir = self._base_dir / ".git"
        if not git_dir.exists():
            try:
                subprocess.run(
                    ["git", "init"], cwd=self._base_dir,
                    capture_output=True, timeout=10,
                )
                subprocess.run(
                    ["git", "config", "user.name", "AStockPursue Indicator Lab"],
                    cwd=self._base_dir, capture_output=True, timeout=10,
                )
                subprocess.run(
                    ["git", "config", "user.email", "indicator-lab@AStockPursue"],
                    cwd=self._base_dir, capture_output=True, timeout=10,
                )
            except Exception:
                logger.warning("Failed to init git repo in %s", self._base_dir)
                return
        self._git_ready = True

    def _git_commit(self, file_path: Path, message: str) -> None:
        """Stage and commit a file."""
        self._ensure_git_repo()
        if not self._git_ready:
            return
        try:
            rel = file_path.relative_to(self._base_dir)
            subprocess.run(
                ["git", "add", str(rel)], cwd=self._base_dir,
                capture_output=True, timeout=10,
            )
            subprocess.run(
                ["git", "commit", "-m", message], cwd=self._base_dir,
                capture_output=True, timeout=10,
            )
        except Exception as e:
            logger.debug("Git commit failed (non-fatal): %s", e)

    def history(self, indicator_id: str) -> list[dict]:
        """Get git commit history for an indicator.

        Returns list of {commit_hash, timestamp, message}.
        """
        py_file = self._resolve_file(indicator_id)
        if py_file is None:
            return []
        self._ensure_git_repo()
        if not self._git_ready:
            return []
        try:
            rel = py_file.relative_to(self._base_dir)
            r = subprocess.run(
                ["git", "log", "--follow", "--format=%H|%aI|%s", "--", str(rel)],
                cwd=self._base_dir, capture_output=True, text=True, timeout=10,
            )
            if r.returncode != 0:
                return []
            entries: list[dict] = []
            for line in r.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 2)
                if len(parts) == 3:
                    entries.append({
                        "commit_hash": parts[0][:8],
                        "timestamp": parts[1],
                        "message": parts[2],
                    })
            return entries
        except Exception as e:
            logger.warning("Git history failed: %s", e)
            return []

    def rollback(self, indicator_id: str, commit_hash: str) -> IndicatorInfo | None:
        """Restore an indicator to a previous version.

        Returns the restored IndicatorInfo, or None on failure.
        """
        py_file = self._resolve_file(indicator_id)
        if py_file is None:
            return None
        self._ensure_git_repo()
        if not self._git_ready:
            return None
        try:
            rel = py_file.relative_to(self._base_dir)
            r = subprocess.run(
                ["git", "show", f"{commit_hash}:{rel}"],
                cwd=self._base_dir, capture_output=True, text=True, timeout=10,
            )
            if r.returncode != 0:
                return None
            old_code = r.stdout
            py_file.write_text(old_code, encoding="utf-8")
            self._git_commit(py_file, f"Rollback to {commit_hash[:8]}: {indicator_id}")
            return self._file_to_info(py_file)
        except Exception as e:
            logger.warning("Git rollback failed: %s", e)
            return None

    def diff(self, indicator_id: str, commit_hash: str) -> str:
        """Show diff between a commit and current HEAD for an indicator."""
        py_file = self._resolve_file(indicator_id)
        if py_file is None:
            return ""
        self._ensure_git_repo()
        if not self._git_ready:
            return ""
        try:
            rel = py_file.relative_to(self._base_dir)
            r = subprocess.run(
                ["git", "diff", f"{commit_hash}..HEAD", "--", str(rel)],
                cwd=self._base_dir, capture_output=True, text=True, timeout=10,
            )
            return r.stdout or "(no changes)"
        except Exception as e:
            return f"Diff failed: {e}"

    # ── CRUD ────────────────────────────────────────────────────────────────

    def list(self) -> list[IndicatorInfo]:
        """List all saved indicators."""
        results: list[IndicatorInfo] = []
        for py_file in sorted(self._base_dir.glob("*.py")):
            try:
                info = self._file_to_info(py_file)
                results.append(info)
            except Exception:
                logger.exception(f"Failed to read indicator {py_file.name}")
        return results

    def get(self, indicator_id: str) -> IndicatorInfo | None:
        """Get a single indicator by ID."""
        py_file = self._resolve_file(indicator_id)
        if py_file is None:
            return None
        try:
            return self._file_to_info(py_file)
        except Exception:
            logger.exception(f"Failed to read indicator {py_file.name}")
            return None

    def get_code(self, indicator_id: str) -> str | None:
        """Get the raw source code of an indicator."""
        py_file = self._resolve_file(indicator_id)
        if py_file is None:
            return None
        try:
            return py_file.read_text(encoding="utf-8")
        except OSError:
            return None

    def save(
        self, code: str, indicator_id: str | None = None, filename: str | None = None
    ) -> IndicatorInfo:
        """Save or update an indicator (atomic write — safe against concurrent saves).

        Args:
            code: The full Python source code.
            indicator_id: If provided, update the existing indicator with this ID.
            filename: If provided and indicator_id is None, use this filename.

        Returns:
            IndicatorInfo for the saved indicator.
        """
        name, description = _extract_meta_from_code(code)

        if indicator_id:
            existing = self._resolve_file(indicator_id)
            if existing:
                _atomic_write(existing, code)
                info = self._file_to_info(existing)
                self._git_commit(existing, f"Update indicator: {name}")
                return info

        if filename:
            safe = filename if _SAFE_FILENAME_RE.match(filename) else _safe_filename(filename)
        else:
            safe = _safe_filename(name)

        file_path = self._base_dir / safe

        # If file exists, generate a unique name
        if file_path.exists():
            stem = safe[:-3]
            file_path = self._base_dir / f"{stem}_{uuid.uuid4().hex[:8]}.py"

        _atomic_write(file_path, code)
        info = self._file_to_info(file_path)

        # Auto-commit to git
        msg = (
            f"Update indicator: {name}" if indicator_id
            else f"Save indicator: {name}"
        )
        self._git_commit(file_path, msg)

        return info

    def delete(self, indicator_id: str) -> bool:
        """Delete an indicator by ID. Returns True if deleted."""
        py_file = self._resolve_file(indicator_id)
        if py_file is None:
            return False
        try:
            py_file.unlink()
            return True
        except OSError:
            logger.exception(f"Failed to delete {py_file.name}")
            return False

    # ── Alpha Zoo bridge ────────────────────────────────────────────────────

    def promote_to_alpha(
        self,
        indicator_id: str,
        zoo_id: str = "user",
        theme: list[str] | None = None,
        universe: list[str] | None = None,
    ) -> Path | None:
        """Promote a mature indicator to an Alpha Zoo factor.

        Reads the indicator source, wraps it with a ``compute(panel)`` function
        and ``__alpha_meta__`` dict, and writes it into the zoo directory.

        Args:
            indicator_id: The indicator to promote.
            zoo_id: Target zoo subdirectory (default: "user").
            theme: Alpha theme tags.
            universe: Applicable market universes.

        Returns:
            Path to the created zoo factor file, or None on failure.
        """
        from src.config.paths import get_runtime_root

        code = self.get_code(indicator_id)
        if code is None:
            return None

        info = self.get(indicator_id)
        if info is None:
            return None

        name, description = _extract_meta_from_code(code)
        short_id = re.sub(r"[^a-z0-9_]", "_", info.id.lower())[:31]
        alpha_id = f"{zoo_id}_{short_id}"

        zoo_dir = get_runtime_root() / "zoo" / zoo_id
        zoo_dir.mkdir(parents=True, exist_ok=True)

        theme = theme or ["momentum"]
        universe = universe or ["equity_us"]

        alpha_code = self._generate_alpha_code(
            alpha_id=alpha_id,
            nickname=name,
            theme=theme,
            universe=universe,
            user_code=code,
            description=description,
        )

        out_path = zoo_dir / f"{short_id}.py"
        _atomic_write(out_path, alpha_code)
        logger.info(f"Promoted indicator {indicator_id} → alpha {alpha_id} at {out_path}")
        return out_path

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _resolve_file(self, indicator_id: str) -> Path | None:
        """Resolve an indicator ID to a file path.

        The ID can be a filename (with or without .py) or a full path.
        """
        if indicator_id.endswith(".py") and _SAFE_FILENAME_RE.match(indicator_id):
            candidate = self._base_dir / indicator_id
            if candidate.exists():
                return candidate

        candidate = self._base_dir / f"{indicator_id}.py"
        if candidate.exists():
            return candidate

        # Try matching by stem (for indicator IDs that map to filenames)
        for py_file in self._base_dir.glob("*.py"):
            if py_file.stem == indicator_id:
                return py_file

        return None

    def _file_to_info(self, file_path: Path) -> IndicatorInfo:
        from src.lab.params import IndicatorParamsParser, StrategyConfigParser

        code = file_path.read_text(encoding="utf-8")
        name, description = _extract_meta_from_code(code)
        params = IndicatorParamsParser.parse_params(code)
        strategy = StrategyConfigParser.parse(code)

        stat = file_path.stat()
        return IndicatorInfo(
            id=file_path.stem,
            name=name or file_path.stem,
            description=description or "",
            file_path=file_path,
            created_at=datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
            updated_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            param_count=len(params),
            strategy_config=strategy,
        )

    @staticmethod
    def _generate_alpha_code(
        alpha_id: str,
        nickname: str,
        theme: list[str],
        universe: list[str],
        user_code: str,
        description: str,
    ) -> str:
        """Wrap user indicator code as an Alpha Zoo factor with real compute().

        Parses the QD-style indicator code and generates a compute(panel)
        function that iterates over panel columns, runs the equivalent logic
        per instrument, and returns a wide-format score DataFrame.
        """
        from src.lab.params import IndicatorParamsParser, StrategyConfigParser

        params = IndicatorParamsParser.parse_params(user_code)
        strategy = StrategyConfigParser.parse(user_code)

        # Extract param defaults for injection into generated code
        param_defaults: dict[str, str] = {}
        for p in params:
            val = p["default"]
            if isinstance(val, str):
                param_defaults[p["name"]] = repr(val)
            else:
                param_defaults[p["name"]] = str(val)

        # Determine columns used
        columns_used = ["close"]
        if re.search(r"(?<![\"'])open(?![\"'])", user_code):
            columns_used.append("open")
        if re.search(r"(?<![\"'])high(?![\"'])", user_code):
            columns_used.append("high")
        if re.search(r"(?<![\"'])low(?![\"'])", user_code):
            columns_used.append("low")
        if re.search(r"(?<![\"'])volume(?![\"'])", user_code):
            columns_used.append("volume")
        columns_used = list(dict.fromkeys(columns_used))

        # Extract the core logic: lines between "df = df.copy()" and buy/sell/output
        user_lines = user_code.strip().split("\n")
        core_lines: list[str] = []
        in_core = False
        for line in user_lines:
            stripped = line.strip()
            if re.match(r"^\s*df\s*=\s*df\.copy\s*\(\s*\)", stripped):
                in_core = True
                continue
            if in_core:
                if re.match(r"^\s*(df\s*\[\s*['\"]buy['\"]\s*\]|df\s*\[\s*['\"]sell['\"]\s*\]|output\s*=)", stripped):
                    continue
                core_lines.append(line)

        core_body = "\n".join(core_lines) if core_lines else (
            "    # No core logic extracted; using momentum fallback\n"
            "    returns = sub_df['close'].pct_change(5)\n"
            "    score = -returns"
        )

        # Replace `df` variable references with `sub_df` for the per-column loop
        # Only replace standalone `df` references, not `sub_df`, `pd.DataFrame`, etc.
        core_body = re.sub(r'\bdf\b', 'sub_df', core_body)

        # Indent the core logic for injection into the compute function
        indented_core = "\n".join(
            f"        {line}" if line.strip() else ""
            for line in core_body.split("\n")
        )

        # Build param dict for the generated code
        params_dict_lines = ",\n".join(
            f'            "{name}": {val}'
            for name, val in param_defaults.items()
        )
        params_block = (
            f"        params = {{\n{params_dict_lines}\n        }}"
            if param_defaults
            else "        params = {}"
        )

        lines = [
            '"""Auto-generated alpha factor — promoted from Indicator Lab."""',
            "",
            "from src.factors.base import rank, scale, ts_mean, ts_std, ts_corr, delta, "
            "decay_linear, signed_power, safe_div",
            "import pandas as pd",
            "import numpy as np",
            "",
            "__alpha_meta__ = {",
            f"    'id': '{alpha_id}',",
            f"    'nickname': '{nickname}',",
            f"    'theme': {theme},",
            "    'formula_latex': r'user-defined',",
            f"    'columns_required': {columns_used},",
            f"    'universe': {universe},",
            "    'frequency': ['1D'],",
            "    'decay_horizon': 5,",
            "    'min_warmup_bars': 60,",
            f"    'notes': '{description[:200]}',",
            "}",
            "",
            "",
            "def compute(panel: dict[str, pd.DataFrame]) -> pd.DataFrame:",
            '    """User-defined alpha — promoted from Indicator Lab.',
            "",
            f"    Original: {nickname}",
            f"    {description[:120]}",
            '    """',
            "    close = panel['close']",
            "    scores = pd.DataFrame(0.0, index=close.index, columns=close.columns)",
            "",
            "    open_ = panel.get('open')",
            "    high = panel.get('high')",
            "    low = panel.get('low')",
            "    volume = panel.get('volume')",
            "",
            "    for col in close.columns:",
            "        # Build single-instrument sub-panel",
            "        sub_df = pd.DataFrame({'close': close[col]})",
            "        if open_ is not None:",
            "            sub_df['open'] = open_[col]",
            "        if high is not None:",
            "            sub_df['high'] = high[col]",
            "        if low is not None:",
            "            sub_df['low'] = low[col]",
            "        if volume is not None:",
            "            sub_df['volume'] = volume[col]",
            "",
            "        sub_df = sub_df.dropna()",
            "        if len(sub_df) < 60:",
            "            continue",
            "",
            f"{params_block}",
            "",
            "        # === User indicator logic (per-instrument) ===",
            f"{indented_core}",
            "",
            "        # === Convert buy/sell signals to scores ===",
            "        idx = sub_df.index",
            "        score = pd.Series(0.0, index=idx)",
            "        if 'buy' in sub_df.columns:",
            "            score[sub_df['buy'].fillna(False).astype(bool)] = 1.0",
            "        if 'sell' in sub_df.columns:",
            "            score[sub_df['sell'].fillna(False).astype(bool)] = -1.0",
            "        if 'buy' in sub_df.columns and 'sell' in sub_df.columns:",
            "            conflict = (",
            "                sub_df['buy'].fillna(False).astype(bool)",
            "                & sub_df['sell'].fillna(False).astype(bool)",
            "            )",
            "            score[conflict] = 0.0",
            "",
            "        scores.loc[idx, col] = score",
            "",
            "    return scores",
            "",
        ]

        return "\n".join(lines)
