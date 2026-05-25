"""Sandboxed Python execution for user-authored indicator code.

Provides timeout, import whitelist, and AST-based safety validation.
Ported from QuantDinger's safe_exec.py and adapted for AStockPursue.
"""

from __future__ import annotations

import ast
import builtins as _builtins_mod
import logging
import multiprocessing
import os
import re
import signal
import sys
import threading
import traceback
from contextlib import contextmanager
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SandboxTimeoutError(Exception):
    """Code execution timed out."""


# ── Whitelisted builtins ────────────────────────────────────────────────────
_BUILTINS_WHITELIST: set[str] = {
    "bool", "int", "float", "complex", "str", "bytes", "bytearray",
    "list", "tuple", "dict", "set", "frozenset",
    "range", "slice", "memoryview",
    "abs", "round", "pow", "divmod", "min", "max", "sum",
    "len", "enumerate", "zip", "map", "filter", "sorted", "reversed",
    "iter", "next", "all", "any",
    "repr", "ascii", "chr", "ord", "format", "bin", "hex", "oct",
    "hash", "id",
    "isinstance", "issubclass", "hasattr", "callable",
    "print",
    "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
    "AttributeError", "ZeroDivisionError", "StopIteration",
    "RuntimeError", "OverflowError", "ArithmeticError",
    "NotImplementedError", "NameError", "ImportError",
    "True", "False", "None",
    "Ellipsis", "NotImplemented",
    "staticmethod", "classmethod", "property", "super",
    "object",
}

SAFE_IMPORT_MODULES: set[str] = {
    "numpy", "pandas", "math", "json", "datetime", "time",
    "collections", "functools", "itertools", "statistics",
    "decimal", "fractions", "operator", "copy",
    "typing", "re", "warnings", "dataclasses", "enum", "abc",
    "scipy", "sklearn",
}


def _make_safe_import():
    """Create a restricted __import__ that only allows whitelisted modules."""
    def safe_import(name, *args, **kwargs):
        root = name.split(".")[0]
        if root in SAFE_IMPORT_MODULES:
            return _builtins_mod.__import__(name, *args, **kwargs)
        raise ImportError(f"Import not allowed: {name}")
    return safe_import


def build_safe_builtins(extra_allowed: set[str] | None = None) -> dict[str, Any]:
    """Build a restricted __builtins__ dict for sandboxed exec()."""
    allowed = _BUILTINS_WHITELIST | (extra_allowed or set())
    safe: dict[str, Any] = {}
    for name in allowed:
        val = getattr(_builtins_mod, name, None)
        if val is not None:
            safe[name] = val
    safe["__import__"] = _make_safe_import()
    safe["__build_class__"] = _builtins_mod.__build_class__
    return safe


# ── Timeout ─────────────────────────────────────────────────────────────────

@contextmanager
def timeout_context(seconds: int):
    """Cross-platform code execution timeout context manager."""
    is_main_thread = threading.current_thread() is threading.main_thread()

    if sys.platform != "win32" and is_main_thread:
        def timeout_handler(signum, frame):
            raise SandboxTimeoutError(f"Code execution timed out ({seconds}s)")

        try:
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)
            try:
                yield
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            return
        except ValueError:
            pass

    timed_out = threading.Event()

    def _inject_timeout():
        timed_out.set()
        try:
            import ctypes
            exc = ctypes.py_object(SandboxTimeoutError)
            target_tid = threading.current_thread().ident
            ret = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_ulong(target_tid), exc
            )
            if ret == 0:
                logger.warning("timeout inject: invalid thread id")
            elif ret > 1:
                ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    ctypes.c_ulong(target_tid), ctypes.py_object(0)
                )
        except Exception as e:
            logger.warning(f"timeout inject failed: {e}")

    timer = threading.Timer(seconds, _inject_timeout)
    timer.daemon = True
    timer.start()
    try:
        yield
    finally:
        timer.cancel()
        if timed_out.is_set():
            raise SandboxTimeoutError(f"Code execution timed out ({seconds}s)")


# ── Core execution ──────────────────────────────────────────────────────────

def safe_exec_code(
    code: str,
    exec_globals: dict[str, Any],
    exec_locals: dict[str, Any] | None = None,
    timeout: int = 30,
    max_memory_mb: int | None = None,
) -> dict[str, Any]:
    """Execute Python code in-process with timeout protection."""
    if exec_locals is None:
        exec_locals = exec_globals

    if max_memory_mb is None:
        max_memory_mb = 500

    try:
        if sys.platform != "win32" and os.getenv("SAFE_EXEC_ENABLE_RLIMIT", "") == "true":
            try:
                import resource
                max_memory_bytes = max_memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (max_memory_bytes, max_memory_bytes))
            except (ImportError, ValueError, OSError) as e:
                logger.warning(f"Failed to set memory limit: {e}")

        with timeout_context(timeout):
            exec(code, exec_globals, exec_locals)

        return {"success": True, "error": None, "result": None}

    except MemoryError:
        error_msg = f"Code execution out of memory (limit={max_memory_mb}MB)"
        logger.error(error_msg)
        return {"success": False, "error": error_msg, "result": None}
    except SandboxTimeoutError as e:
        logger.error(f"Code execution timed out (timeout={timeout}s)")
        return {"success": False, "error": str(e), "result": None}
    except Exception as e:
        error_msg = f"Code execution error: {e}\n{traceback.format_exc()}"
        logger.error(f"Code execution error: {e}")
        return {"success": False, "error": error_msg, "result": None}


def safe_exec_with_validation(
    code: str,
    exec_globals: dict[str, Any],
    exec_locals: dict[str, Any] | None = None,
    timeout: int = 60,
    max_memory_mb: int | None = None,
    pre_import: str = "import numpy as np\nimport pandas as pd\n",
) -> dict[str, Any]:
    """Validate + execute user code in one call.

    1. Runs validate_code_safety(); rejects unsafe code.
    2. Injects build_safe_builtins() if __builtins__ is not already set.
    3. Executes pre_import, then user code via safe_exec_code().
    """
    is_safe, err = validate_code_safety(code)
    if not is_safe:
        return {"success": False, "error": f"Unsafe code rejected: {err}", "result": None}

    if "__builtins__" not in exec_globals:
        exec_globals["__builtins__"] = build_safe_builtins()

    if pre_import:
        try:
            exec(pre_import, exec_globals)
        except Exception as e:
            return {"success": False, "error": f"Pre-import failed: {e}", "result": None}

    return safe_exec_code(
        code=code,
        exec_globals=exec_globals,
        exec_locals=exec_locals,
        timeout=timeout,
        max_memory_mb=max_memory_mb,
    )


# ── Subprocess isolation ────────────────────────────────────────────────────

def _isolated_worker(code: str, input_data: dict[str, Any] | None, max_memory_mb: int, result_pipe):
    """Module-level target for safe_exec_isolated (must be picklable for spawn)."""
    import pickle as _pickle

    try:
        if sys.platform != "win32":
            try:
                import resource
                mem = max_memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
            except Exception:
                pass

        import numpy as np
        import pandas as pd

        exec_env = {
            "__builtins__": build_safe_builtins(),
            "np": np,
            "pd": pd,
        }
        if input_data:
            exec_env.update(input_data)

        pre_import = "import numpy as np\nimport pandas as pd\n"
        exec(pre_import, exec_env)
        exec(code, exec_env)

        output = {}
        for k, v in exec_env.items():
            if k.startswith("_") or k in ("np", "pd", "__builtins__"):
                continue
            try:
                _pickle.dumps(v)
                output[k] = v
            except Exception:
                pass

        result_pipe.send({"success": True, "error": None, "result": output})
    except Exception as e:
        result_pipe.send({
            "success": False,
            "error": f"{type(e).__name__}: {e}",
            "result": None,
        })
    finally:
        result_pipe.close()


def safe_exec_isolated(
    code: str,
    input_data: dict[str, Any] | None = None,
    timeout: int = 60,
    max_memory_mb: int = 500,
) -> dict[str, Any]:
    """Execute user code in an isolated subprocess.

    Data is serialized via pickle through pipes.
    """
    parent_conn, child_conn = multiprocessing.Pipe(duplex=False)

    ctx = multiprocessing.get_context("spawn")
    proc = ctx.Process(
        target=_isolated_worker,
        args=(code, input_data, max_memory_mb, child_conn),
        daemon=True,
    )
    proc.start()
    child_conn.close()

    proc.join(timeout=timeout)

    if proc.is_alive():
        proc.kill()
        proc.join(timeout=5)
        return {
            "success": False,
            "error": f"Code execution timed out ({timeout}s), subprocess killed",
            "result": None,
        }

    if proc.exitcode != 0 and not parent_conn.poll():
        return {
            "success": False,
            "error": (
                f"Subprocess exited abnormally (exit code: {proc.exitcode}). "
                f"Worker did not return a result — this likely indicates a hard "
                f"crash (segfault, OOM kill, or C-level abort). "
                f"Check server logs for multiprocessing worker tracebacks."
            ),
            "result": None,
        }

    try:
        if parent_conn.poll(timeout=1):
            return parent_conn.recv()
        return {"success": False, "error": "Subprocess returned no result", "result": None}
    except Exception as e:
        return {"success": False, "error": f"Failed to read subprocess result: {e}", "result": None}
    finally:
        parent_conn.close()


# ── Static validation ───────────────────────────────────────────────────────

def validate_code_safety(code: str) -> tuple[bool, str | None]:
    """Validate code safety via regex + AST double check."""
    dangerous_patterns = [
        r"\bos\.system\b", r"\bos\.popen\b", r"\bos\.spawn\b",
        r"\bos\.exec\b", r"\bos\.fork\b", r"\bos\.environ\b",
        r"\bos\.getenv\b", r"\bos\.putenv\b",
        r"\bos\.remove\b", r"\bos\.unlink\b", r"\bos\.rmdir\b",
        r"\bos\.makedirs\b", r"\bos\.mkdir\b",
        r"\bos\.listdir\b", r"\bos\.walk\b", r"\bos\.scandir\b",
        r"\bos\.path\b",
        r"\bsubprocess\b", r"\bcommands\b",
        r"\b__import__\s*\(", r"\beval\s*\(", r"\bexec\s*\(",
        r"\bcompile\s*\(", r"\bopen\s*\(", r"\bfile\s*\(",
        r"\b__builtins__\b",
        r"\bimport\s+os\b", r"\bimport\s+sys\b",
        r"\bimport\s+subprocess\b", r"\bimport\s+shutil\b",
        r"\bimport\s+pymysql\b", r"\bimport\s+sqlite3\b",
        r"\bimport\s+psycopg\b", r"\bimport\s+sqlalchemy\b",
        r"\bimport\s+requests\b", r"\bimport\s+urllib\b",
        r"\bimport\s+http\b", r"\bimport\s+socket\b",
        r"\bimport\s+ftplib\b", r"\bimport\s+telnetlib\b",
        r"\bimport\s+smtplib\b", r"\bimport\s+ssl\b",
        r"\bimport\s+pickle\b", r"\bimport\s+cpickle\b",
        r"\bimport\s+marshal\b", r"\bimport\s+shelve\b",
        r"\bimport\s+ctypes\b", r"\bimport\s+cffi\b",
        r"\bimport\s+multiprocessing\b", r"\bimport\s+threading\b",
        r"\bimport\s+concurrent\b", r"\bimport\s+asyncio\b",
        r"\bimport\s+signal\b", r"\bimport\s+resource\b",
        r"\bimport\s+importlib\b", r"\bimport\s+imp\b",
        r"\bimport\s+builtins\b", r"\bimport\s+code\b",
        r"\bimport\s+codeop\b", r"\bimport\s+runpy\b",
        r"\bimport\s+tempfile\b", r"\bimport\s+glob\b",
        r"\bimport\s+pathlib\b", r"\bimport\s+io\b",
        r"\bgetattr\s*\(", r"\bsetattr\s*\(", r"\bdelattr\s*\(",
        r"\b__getattribute__\b", r"\b__setattr__\b", r"\b__delattr__\b",
        r"\b__dict__\b", r"\b__class__\b", r"\b__bases__\b",
        r"\b__subclasses__\b", r"\b__mro__\b", r"\b__module__\b",
        r"\b__globals__\b", r"\b__code__\b", r"\b__func__\b",
        r"\bglobals\s*\(", r"\bvars\s*\(", r"\bdir\s*\(",
        r"\bbreakpoint\s*\(",
        r"\bimportlib\b",
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, code):
            return False, f"Dangerous code pattern detected: {pattern}"

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        logger.warning(f"Code syntax validation failed: {e}")
        return False, "Code syntax error"
    except Exception:
        logger.exception("AST parse failed, rejecting code")
        return False, "Code parse failed"

    dangerous_modules = {
        "os", "sys", "subprocess", "shutil", "signal", "resource",
        "pymysql", "sqlite3", "psycopg2", "sqlalchemy",
        "requests", "urllib", "http", "socket", "ftplib", "telnetlib",
        "smtplib", "ssl",
        "pickle", "cpickle", "marshal", "shelve",
        "ctypes", "cffi",
        "multiprocessing", "threading", "concurrent", "asyncio",
        "importlib", "imp", "builtins", "code", "codeop", "runpy",
        "tempfile", "glob", "pathlib", "io",
    }

    dangerous_call_names = {
        "eval", "exec", "compile", "__import__",
        "getattr", "setattr", "delattr",
        "globals", "vars", "dir", "breakpoint",
        "open", "input", "exit", "quit",
    }

    dangerous_dunder_attrs = {
        "__builtins__", "__import__", "__class__", "__bases__",
        "__subclasses__", "__mro__", "__globals__", "__code__",
        "__func__", "__dict__", "__module__",
    }

    # First pass: collect names that are explicitly imported from dangerous modules.
    # We only block method calls on names that were actually imported (e.g. "signal"
    # from "import signal"), not local variables that happen to share the name
    # (e.g. "signal" as a Pandas Series of trading signals).
    dangerous_bound_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in dangerous_modules:
                    bound_name = alias.asname or root
                    dangerous_bound_names.add(bound_name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root in dangerous_modules:
                    for alias in node.names:
                        bound_name = alias.asname or alias.name
                        dangerous_bound_names.add(bound_name)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in SAFE_IMPORT_MODULES:
                    return False, (
                        f"Module '{alias.name}' not allowed. "
                        f"Allowed: {', '.join(sorted(SAFE_IMPORT_MODULES))}"
                    )

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root not in SAFE_IMPORT_MODULES:
                    return False, (
                        f"Module '{node.module}' not allowed. "
                        f"Allowed: {', '.join(sorted(SAFE_IMPORT_MODULES))}"
                    )

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in dangerous_call_names:
                return False, f"Dangerous function call: {node.func.id}()"
            if isinstance(node.func, ast.Attribute):
                if (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id in dangerous_bound_names
                ):
                    return False, (
                        f"Dangerous module call: {node.func.value.id}.{node.func.attr}"
                    )

        elif isinstance(node, ast.Attribute):
            if isinstance(node.attr, str) and node.attr in dangerous_dunder_attrs:
                return False, f"Dangerous attribute access: .{node.attr}"

    return True, None
