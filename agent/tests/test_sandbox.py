from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.security.sandbox import (
    SAFE_IMPORT_MODULES,
    SandboxTimeoutError,
    build_safe_builtins,
    safe_exec_code,
    safe_exec_isolated,
    safe_exec_with_validation,
    validate_code_safety,
)


class TestValidateCodeSafety:
    def test_accepts_safe_imports(self) -> None:
        safe, err = validate_code_safety("""
import numpy as np
import pandas as pd
import math
from collections import defaultdict
""")
        assert safe, f"Should accept safe imports, got: {err}"

    def test_rejects_os_import(self) -> None:
        safe, err = validate_code_safety("import os\nos.system('ls')")
        assert not safe, "Should reject os import"

    def test_rejects_subprocess_import(self) -> None:
        safe, _ = validate_code_safety("import subprocess\nsubprocess.run(['ls'])")
        assert not safe

    def test_rejects_sys_import(self) -> None:
        safe, _ = validate_code_safety("import sys\nsys.exit()")
        assert not safe

    def test_rejects_eval_call(self) -> None:
        safe, err = validate_code_safety('eval("1+1")')
        assert not safe, f"Should reject eval(), got: {err}"

    def test_rejects_exec_call(self) -> None:
        safe, _ = validate_code_safety('exec("x=1")')
        assert not safe

    def test_rejects_open_call(self) -> None:
        safe, _ = validate_code_safety("open('/etc/passwd')")
        assert not safe

    def test_rejects_dunder_access(self) -> None:
        safe, _ = validate_code_safety("x.__class__")
        assert not safe

    def test_rejects_getattr_call(self) -> None:
        safe, _ = validate_code_safety("getattr(obj, 'hidden')")
        assert not safe

    def test_accepts_rsi_indicator(self) -> None:
        code = '''
my_indicator_name = "Test"
my_indicator_description = "Test RSI"
df = df.copy()
period = 14
delta = df["close"].diff()
gain = delta.where(delta > 0, 0.0)
loss = (-delta).where(delta < 0, 0.0)
avg_gain = gain.rolling(period).mean()
avg_loss = loss.rolling(period).mean()
rs = avg_gain / avg_loss.replace(0, np.nan)
rsi = 100.0 - (100.0 / (1.0 + rs))
df["buy"] = rsi < 30
'''
        safe, err = validate_code_safety(code)
        assert safe, f"Should accept RSI indicator, got: {err}"

    def test_accepts_math_operations(self) -> None:
        safe, _ = validate_code_safety("x = abs(-5) + round(3.14) + pow(2, 3) + min(1,2) + max(3,4)")
        assert safe

    def test_rejects_breakpoint(self) -> None:
        safe, _ = validate_code_safety("breakpoint()")
        assert not safe

    def test_rejects_globals_call(self) -> None:
        safe, _ = validate_code_safety("globals()")
        assert not safe

    def test_allows_local_signal_variable(self) -> None:
        """Local variable named 'signal' (trading signal) should not be flagged."""
        safe, err = validate_code_safety("""
signal = df['close'] > df['close'].rolling(20).mean()
signal.replace(True, 1, inplace=True)
signal.replace(False, -1, inplace=True)
""")
        assert safe, f"Should allow local variable 'signal', got: {err}"

    def test_rejects_imported_signal_module_call(self) -> None:
        """import signal + signal.alarm() should still be rejected."""
        safe, _ = validate_code_safety("import signal\nsignal.alarm(10)")
        assert not safe

    def test_allows_local_signal_but_rejects_signal_import(self) -> None:
        """Mixed: local 'signal' var OK, but 'import signal' is still blocked at regex level."""
        safe, _ = validate_code_safety("import signal\nsignal = 1\nsignal.replace(0, -1)")
        assert not safe  # blocked by regex r"\bimport\s+signal\b"


class TestBuildSafeBuiltins:
    def test_includes_safe_functions(self) -> None:
        b = build_safe_builtins()
        assert "print" in b
        assert "len" in b
        assert "range" in b
        assert "True" in b
        assert "False" in b

    def test_excludes_dangerous_functions(self) -> None:
        b = build_safe_builtins()
        assert "open" not in b
        assert "eval" not in b
        assert "exec" not in b
        assert "compile" not in b
        assert "getattr" not in b
        assert "globals" not in b

    def test_import_restricted_to_whitelist(self) -> None:
        b = build_safe_builtins()
        imp = b.get("__import__")
        assert imp is not None

    def test_extra_allowed_adds_names(self) -> None:
        b = build_safe_builtins(extra_allowed={"custom_func"})
        assert "custom_func" not in b  # Doesn't exist in builtins, so not added
        b2 = build_safe_builtins(extra_allowed={"open"})
        assert "open" in b2  # Was excluded but explicitly allowed


class TestSafeExecCode:
    def test_executes_simple_code(self) -> None:
        code = "x = 1 + 2\nresult = x * 3"
        env: dict = {}
        r = safe_exec_code(code, env, timeout=5)
        assert r["success"], f"exec failed: {r['error']}"
        assert env.get("result") == 9

    def test_timeout_detected(self) -> None:
        code = "import time\ntime.sleep(30)"
        env: dict = {}
        r = safe_exec_code(code, env, timeout=1)
        assert not r["success"]
        assert "timed out" in r.get("error", "").lower() or "timeout" in r.get("error", "").lower()

    def test_exception_captured(self) -> None:
        code = "x = 1 / 0"
        env: dict = {}
        r = safe_exec_code(code, env, timeout=5)
        assert not r["success"]
        assert "ZeroDivisionError" in r.get("error", "")

    def test_pandas_operations_work(self) -> None:
        code = """
df['ma'] = df['close'].rolling(window=3, min_periods=3).mean()
result = float(df['ma'].iloc[-1])
"""
        df = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0, 5.0]})
        env = {"df": df.copy(), "pd": pd, "np": np}
        r = safe_exec_code(code, env, timeout=5)
        assert r["success"], f"exec failed: {r['error']}"
        assert env.get("result") == pytest.approx(4.0)


class TestSafeExecWithValidation:
    def test_unsafe_code_rejected_before_exec(self) -> None:
        code = "import os\nx = 1"
        env: dict = {}
        r = safe_exec_with_validation(code, env, timeout=5)
        assert not r["success"]
        assert "Unsafe" in r.get("error", "")

    def test_safe_code_runs_with_pre_import(self) -> None:
        code = "x = np.array([1, 2, 3])\nresult = x.sum()"
        env: dict = {}
        r = safe_exec_with_validation(code, env, timeout=5)
        assert r["success"], f"exec failed: {r['error']}"
        assert env.get("result") == 6


class TestSafeExecIsolated:
    def test_subprocess_execution(self) -> None:
        code = "x = 42"
        r = safe_exec_isolated(code, timeout=5)
        assert r["success"], f"isolated exec failed: {r['error']}"
        assert r["result"].get("x") == 42

    def test_subprocess_timeout(self) -> None:
        code = "import time\ntime.sleep(60)"
        r = safe_exec_isolated(code, timeout=2)
        assert not r["success"]


class TestImportWhitelist:
    def test_numpy_allowed(self) -> None:
        assert "numpy" in SAFE_IMPORT_MODULES

    def test_pandas_allowed(self) -> None:
        assert "pandas" in SAFE_IMPORT_MODULES

    def test_scipy_allowed(self) -> None:
        assert "scipy" in SAFE_IMPORT_MODULES

    def test_os_not_allowed(self) -> None:
        assert "os" not in SAFE_IMPORT_MODULES

    def test_subprocess_not_allowed(self) -> None:
        assert "subprocess" not in SAFE_IMPORT_MODULES
