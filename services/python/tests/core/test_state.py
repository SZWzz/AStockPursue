"""Tests for src.core.state — run directory creation and state persistence."""

from __future__ import annotations

import json

import pytest

from src.core.state import RunStateStore


@pytest.mark.unit
class TestCreateRunDir:
    def test_create_run_dir_returns_a_path(self, tmp_path):
        store = RunStateStore()
        workspace = tmp_path / "runs"
        workspace.mkdir()

        run_dir = store.create_run_dir(workspace)
        assert run_dir.exists()
        assert run_dir.is_dir()

    def test_create_run_dir_creates_subdirectories(self, tmp_path):
        store = RunStateStore()
        workspace = tmp_path / "runs"
        workspace.mkdir()

        run_dir = store.create_run_dir(workspace)
        assert (run_dir / "code").is_dir()
        assert (run_dir / "logs").is_dir()
        assert (run_dir / "artifacts").is_dir()

    def test_create_run_dir_name_pattern(self, tmp_path):
        store = RunStateStore()
        workspace = tmp_path / "runs"
        workspace.mkdir()

        run_dir = store.create_run_dir(workspace)
        name = run_dir.name
        # Pattern: YYYYMMDD_HHMMSS_ff_suffix (4 parts after split by _)
        # timestamp = "%Y%m%d_%H%M%S_%f"[:18] → "YYYYMMDD_HHMMSS_f" (18 chars)
        # So name = "YYYYMMDD_HHMMSS_f_suffix" → 4 parts
        parts = name.split("_")
        assert len(parts) == 4
        assert len(parts[0]) == 8  # YYYYMMDD
        assert len(parts[1]) == 6  # HHMMSS
        assert len(parts[2]) <= 6  # truncated microseconds
        assert len(parts[3]) == 6  # 6-char hex suffix

    def test_create_run_dir_unique_dirs(self, tmp_path):
        store = RunStateStore()
        workspace = tmp_path / "runs"
        workspace.mkdir()

        d1 = store.create_run_dir(workspace)
        d2 = store.create_run_dir(workspace)
        assert d1 != d2


@pytest.mark.unit
class TestSaveRequest:
    def test_save_request_writes_req_json(self, tmp_path):
        store = RunStateStore()
        run_dir = tmp_path / "run-001"
        run_dir.mkdir()

        payload = store.save_request(run_dir, "test prompt", {"key": "value"})
        req_file = run_dir / "req.json"
        assert req_file.exists()

        data = json.loads(req_file.read_text())
        assert data["prompt"] == "test prompt"
        assert data["context"] == {"key": "value"}

    def test_save_request_returns_dict(self, tmp_path):
        store = RunStateStore()
        run_dir = tmp_path / "run-002"
        run_dir.mkdir()

        result = store.save_request(run_dir, "prompt", {})
        assert isinstance(result, dict)
        assert "prompt" in result
        assert "context" in result


@pytest.mark.unit
class TestMarkSuccess:
    def test_mark_success_creates_state_json(self, tmp_path):
        store = RunStateStore()
        run_dir = tmp_path / "run-003"
        run_dir.mkdir()

        store.mark_success(run_dir)
        state_file = run_dir / "state.json"
        assert state_file.exists()

        data = json.loads(state_file.read_text())
        assert data["status"] == "success"


@pytest.mark.unit
class TestMarkFailure:
    def test_mark_failure_creates_state_json_with_reason(self, tmp_path):
        store = RunStateStore()
        run_dir = tmp_path / "run-004"
        run_dir.mkdir()

        store.mark_failure(run_dir, "division by zero")
        state_file = run_dir / "state.json"
        assert state_file.exists()

        data = json.loads(state_file.read_text())
        assert data["status"] == "failed"
        assert data["reason"] == "division by zero"
