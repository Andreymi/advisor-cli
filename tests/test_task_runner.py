"""Tests for task_runner module - background task execution with timeout."""

import json
import time
from pathlib import Path
from unittest.mock import patch


from advisor_cli.task_runner import (
    DEFAULT_TIMEOUT_SECONDS,
    TaskStatus,
    get_task_dir,
    update_task_status,
)


class TestTaskStatusConstants:
    """Tests for TaskStatus constants."""

    def test_status_pending(self):
        """TaskStatus.PENDING should be 'pending'."""
        assert TaskStatus.PENDING == "pending"

    def test_status_running(self):
        """TaskStatus.RUNNING should be 'running'."""
        assert TaskStatus.RUNNING == "running"

    def test_status_completed(self):
        """TaskStatus.COMPLETED should be 'completed'."""
        assert TaskStatus.COMPLETED == "completed"

    def test_status_failed(self):
        """TaskStatus.FAILED should be 'failed'."""
        assert TaskStatus.FAILED == "failed"

    def test_status_timeout(self):
        """TaskStatus.TIMEOUT should be 'timeout'."""
        assert TaskStatus.TIMEOUT == "timeout"


class TestDefaultTimeout:
    """Tests for default timeout constant."""

    def test_default_timeout_is_5_minutes(self):
        """DEFAULT_TIMEOUT_SECONDS should be 300 (5 minutes)."""
        assert DEFAULT_TIMEOUT_SECONDS == 300


class TestGetTaskDir:
    """Tests for get_task_dir function."""

    def test_returns_path_object(self):
        """get_task_dir should return a Path object."""
        result = get_task_dir()
        assert isinstance(result, Path)

    def test_contains_advisor_tasks(self):
        """get_task_dir should return path containing 'advisor-tasks'."""
        result = get_task_dir()
        assert "advisor-tasks" in str(result)


class TestUpdateTaskStatus:
    """Tests for update_task_status function."""

    def test_create_pending_task(self, tmp_path):
        """update_task_status should create pending task with created timestamp."""
        with patch("advisor_cli.task_runner.get_task_dir", return_value=tmp_path):
            update_task_status("task-1", TaskStatus.PENDING)

            task_file = tmp_path / "task-1.json"
            assert task_file.exists()

            data = json.loads(task_file.read_text())
            assert data["status"] == "pending"
            assert "created" in data
            assert "updated" in data

    def test_update_to_running(self, tmp_path):
        """update_task_status should update status to running."""
        with patch("advisor_cli.task_runner.get_task_dir", return_value=tmp_path):
            update_task_status("task-2", TaskStatus.PENDING)
            update_task_status("task-2", TaskStatus.RUNNING)

            task_file = tmp_path / "task-2.json"
            data = json.loads(task_file.read_text())
            assert data["status"] == "running"
            # Should preserve created timestamp
            assert "created" in data

    def test_complete_with_result(self, tmp_path):
        """update_task_status should store result for completed tasks."""
        with patch("advisor_cli.task_runner.get_task_dir", return_value=tmp_path):
            result_data = {"answer": "42", "model": "gpt-4"}
            update_task_status("task-3", TaskStatus.COMPLETED, result=result_data)

            task_file = tmp_path / "task-3.json"
            data = json.loads(task_file.read_text())
            assert data["status"] == "completed"
            assert data["result"] == result_data
            assert "completed" in data

    def test_failed_with_error(self, tmp_path):
        """update_task_status should store error for failed tasks."""
        with patch("advisor_cli.task_runner.get_task_dir", return_value=tmp_path):
            update_task_status("task-4", TaskStatus.FAILED, error="Connection timeout")

            task_file = tmp_path / "task-4.json"
            data = json.loads(task_file.read_text())
            assert data["status"] == "failed"
            assert data["error"] == "Connection timeout"
            assert "completed" in data

    def test_timeout_with_error(self, tmp_path):
        """update_task_status should store error for timeout tasks."""
        with patch("advisor_cli.task_runner.get_task_dir", return_value=tmp_path):
            update_task_status(
                "task-5", TaskStatus.TIMEOUT, error="Task timed out after 300s"
            )

            task_file = tmp_path / "task-5.json"
            data = json.loads(task_file.read_text())
            assert data["status"] == "timeout"
            assert "timed out" in data["error"]

    def test_creates_directory_if_missing(self, tmp_path):
        """update_task_status should create task directory if it doesn't exist."""
        task_dir = tmp_path / "new-dir"
        with patch("advisor_cli.task_runner.get_task_dir", return_value=task_dir):
            assert not task_dir.exists()
            update_task_status("task-6", TaskStatus.PENDING)
            assert task_dir.exists()


class TestCliAsyncStatusIntegration:
    """Tests for cli_async integration with new status system."""

    def test_get_task_status_returns_data(self, tmp_path):
        """get_task_status should return task data dict."""
        from advisor_cli.cli_async import get_task_status

        with patch("advisor_cli.cli_async.TASK_DIR", tmp_path):
            # Create a task file
            task_file = tmp_path / "test-task.json"
            task_data = {
                "status": "running",
                "created": time.time(),
                "updated": time.time(),
            }
            task_file.write_text(json.dumps(task_data))

            result = get_task_status("test-task")
            assert result is not None
            assert result["status"] == "running"

    def test_get_task_status_returns_none_for_missing(self, tmp_path):
        """get_task_status should return None for non-existent task."""
        from advisor_cli.cli_async import get_task_status

        with patch("advisor_cli.cli_async.TASK_DIR", tmp_path):
            result = get_task_status("nonexistent")
            assert result is None

    def test_get_async_result_returns_none_for_running(self, tmp_path):
        """get_async_result should return None for running tasks."""
        from advisor_cli.cli_async import get_async_result

        with patch("advisor_cli.cli_async.TASK_DIR", tmp_path):
            task_file = tmp_path / "running-task.json"
            task_file.write_text(
                json.dumps({"status": "running", "created": time.time()})
            )

            result = get_async_result("running-task")
            assert result is None

    def test_get_async_result_returns_error_for_failed(self, tmp_path):
        """get_async_result should return error info for failed tasks."""
        from advisor_cli.cli_async import get_async_result

        with patch("advisor_cli.cli_async.TASK_DIR", tmp_path):
            task_file = tmp_path / "failed-task.json"
            task_file.write_text(
                json.dumps(
                    {
                        "status": "failed",
                        "error": "Test error",
                        "created": time.time(),
                    }
                )
            )

            result = get_async_result("failed-task", keep=True)
            assert result is not None
            assert result["status"] == "failed"
            assert result["error"] == "Test error"

    def test_task_id_length_constant(self):
        """TASK_ID_LENGTH should be 8."""
        from advisor_cli.cli_async import TASK_ID_LENGTH

        assert TASK_ID_LENGTH == 8
