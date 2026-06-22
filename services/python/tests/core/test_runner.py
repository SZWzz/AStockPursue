"""Tests for src.core.runner — backtest code execution and artifact collection."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from src.core.runner import RunResult, Runner


@pytest.mark.unit
class TestRunResult:
    def test_runresult_dataclass_fields(self):
        result = RunResult(
            success=True,
            exit_code=0,
            stdout="hello",
            stderr="",
            artifacts={},
        )
        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "hello"
        assert result.stderr == ""
        assert result.artifacts == {}

    def test_runresult_artifacts_with_paths(self, tmp_path):
        path1 = tmp_path / "equity.csv"
        path1.write_text("data")
        path2 = tmp_path / "metrics.csv"
        path2.write_text("metrics")

        result = RunResult(
            success=True,
            exit_code=0,
            stdout="ok",
            stderr="",
            artifacts={"equity": path1, "metrics": path2},
        )
        assert len(result.artifacts) == 2
        assert result.artifacts["equity"] == path1


@pytest.mark.unit
class TestRunnerInit:
    def test_runner_default_timeout(self):
        runner = Runner()
        assert runner.timeout == 300

    def test_runner_custom_timeout(self):
        runner = Runner(timeout=60)
        assert runner.timeout == 60

    def test_runner_default_artifacts_spec(self):
        runner = Runner()
        assert runner.artifacts_spec is not None
        assert "defaults" in runner.artifacts_spec
        assert "artifacts" in runner.artifacts_spec

    def test_runner_custom_artifacts_spec(self):
        custom_spec = {"defaults": {"required": ["equity"]}, "artifacts": {}}
        runner = Runner(artifacts_spec=custom_spec)
        assert runner.artifacts_spec is custom_spec


@pytest.mark.unit
class TestPickPythonInterpreter:
    def test_pick_python_interpreter_returns_a_string(self):
        runner = Runner(timeout=10)
        interpreter = runner._pick_python_interpreter()
        assert isinstance(interpreter, str)
        assert len(interpreter) > 0

    def test_pick_python_interpreter_falls_back_to_sys_executable(self):
        runner = Runner(timeout=10)
        interpreter = runner._pick_python_interpreter()
        # Should be a path that exists (sys.executable as fallback)
        assert interpreter == sys.executable or "python" in interpreter.lower()


@pytest.mark.unit
class TestBuildRuntimeEnv:
    def test_build_runtime_env_returns_dict_with_expected_keys(self, tmp_path):
        runner = Runner(timeout=10)
        run_dir = tmp_path / "runs" / "test-001"
        run_dir.mkdir(parents=True)

        env = runner._build_runtime_env(run_dir)
        assert isinstance(env, dict)
        assert "PYTHONUNBUFFERED" in env
        assert env["PYTHONUNBUFFERED"] == "1"
        assert "PYTHONIOENCODING" in env
        assert "PYTHONUTF8" in env

    def test_build_runtime_env_with_pythonpath_extra(self, tmp_path):
        runner = Runner(timeout=10)
        run_dir = tmp_path / "runs" / "test-002"
        run_dir.mkdir(parents=True)
        extra = tmp_path / "extra_lib"
        extra.mkdir()

        env = runner._build_runtime_env(run_dir, pythonpath_extra=extra)
        assert str(extra) in env.get("PYTHONPATH", "")


@pytest.mark.unit
class TestExecute:
    def test_execute_success_with_echo_script(self, tmp_path):
        """Verify execute returns success=True for a simple echo script."""
        run_dir = tmp_path / "runs" / "test-001"
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(parents=True)
        (run_dir / "logs").mkdir(parents=True, exist_ok=True)

        entry = tmp_path / "entry.py"
        entry.write_text("print('hello world')")

        runner = Runner(timeout=10)
        result = runner.execute(entry, run_dir)

        assert result.success is True
        assert result.exit_code == 0
        assert "hello world" in result.stdout

    def test_execute_failure_with_exit_code(self, tmp_path):
        """Verify execute returns success=False for a failing script."""
        run_dir = tmp_path / "runs" / "test-002"
        (run_dir / "artifacts").mkdir(parents=True)
        (run_dir / "logs").mkdir(parents=True, exist_ok=True)

        entry = tmp_path / "fail_entry.py"
        entry.write_text("import sys; sys.exit(42)")

        runner = Runner(timeout=10)
        result = runner.execute(entry, run_dir)

        assert result.success is False
        assert result.exit_code != 0

    def test_execute_collects_artifacts(self, tmp_path):
        """Verify execute collects artifact files from the run directory."""
        run_dir = tmp_path / "runs" / "test-003"
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(parents=True)
        (run_dir / "logs").mkdir(parents=True, exist_ok=True)

        # Create expected artifact files
        (artifacts_dir / "equity.csv").write_text("timestamp,equity\n2024,1000")
        (artifacts_dir / "metrics.csv").write_text("sharpe,1.5")

        entry = tmp_path / "entry.py"
        entry.write_text("print('done')")

        runner = Runner(timeout=10, artifacts_spec={
            "defaults": {"required": ["equity", "metrics"]},
            "artifacts": {
                "equity": {"path": "artifacts/equity.csv", "schema": "equity_csv"},
                "metrics": {"path": "artifacts/metrics.csv", "schema": "metrics_csv"},
            },
        })
        result = runner.execute(entry, run_dir)

        assert result.success is True
        assert "equity" in result.artifacts
        assert "metrics" in result.artifacts

    def test_execute_with_cwd_override(self, tmp_path):
        """Verify execute works with explicit cwd parameter."""
        run_dir = tmp_path / "runs" / "test-004"
        (run_dir / "artifacts").mkdir(parents=True)
        (run_dir / "logs").mkdir(parents=True, exist_ok=True)

        entry = tmp_path / "entry.py"
        entry.write_text("print('cwd test')")

        runner = Runner(timeout=10)
        result = runner.execute(entry, run_dir, cwd=tmp_path)

        assert result.success is True
        assert "cwd test" in result.stdout
