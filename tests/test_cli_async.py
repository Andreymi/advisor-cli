"""Tests for cli_async module - async task utilities."""

import json
import time
from pathlib import Path
from unittest.mock import patch


from advisor_cli.cli_async import (
    TASK_DIR,
    TASK_TTL_SECONDS,
    cleanup_old_tasks,
    create_async_task,
    get_async_result,
)


class TestAsyncTaskConstants:
    """Tests for module constants."""

    def test_task_ttl_is_one_hour(self):
        """TASK_TTL_SECONDS should be 3600 (1 hour)."""
        assert TASK_TTL_SECONDS == 3600

    def test_task_dir_is_in_temp(self):
        """TASK_DIR should be in system temp directory."""
        assert "advisor-tasks" in str(TASK_DIR)


class TestCreateAsyncTask:
    """Tests for create_async_task function."""

    def test_create_and_get_task(self, tmp_path):
        """Create a task and retrieve it."""
        with patch("advisor_cli.cli_async.TASK_DIR", tmp_path):
            task_id = "test-task-123"
            result = {"model": "gpt-4", "response": "Hello world"}

            create_async_task(task_id, result)

            # Verify file was created
            task_file = tmp_path / f"{task_id}.json"
            assert task_file.exists()

            # Verify content structure
            data = json.loads(task_file.read_text())
            assert "result" in data
            assert "created" in data
            assert data["result"] == result
            assert isinstance(data["created"], float)

    def test_create_task_creates_directory(self, tmp_path):
        """create_async_task should create TASK_DIR if it doesn't exist."""
        task_dir = tmp_path / "new-dir"
        with patch("advisor_cli.cli_async.TASK_DIR", task_dir):
            assert not task_dir.exists()

            create_async_task("task-1", {"data": "test"})

            assert task_dir.exists()


class TestGetAsyncResult:
    """Tests for get_async_result function."""

    def test_get_task_deletes_by_default(self, tmp_path):
        """get_async_result should delete the task file by default."""
        with patch("advisor_cli.cli_async.TASK_DIR", tmp_path):
            task_id = "delete-test"
            result = {"key": "value"}

            create_async_task(task_id, result)
            task_file = tmp_path / f"{task_id}.json"
            assert task_file.exists()

            retrieved = get_async_result(task_id)
            assert retrieved == result
            assert not task_file.exists()

    def test_get_task_keeps_with_flag(self, tmp_path):
        """get_async_result with keep=True should preserve the file."""
        with patch("advisor_cli.cli_async.TASK_DIR", tmp_path):
            task_id = "keep-test"
            result = {"preserved": True}

            create_async_task(task_id, result)
            task_file = tmp_path / f"{task_id}.json"

            retrieved = get_async_result(task_id, keep=True)
            assert retrieved == result
            assert task_file.exists()

    def test_get_nonexistent_task_returns_none(self, tmp_path):
        """get_async_result for non-existent task should return None."""
        with patch("advisor_cli.cli_async.TASK_DIR", tmp_path):
            result = get_async_result("nonexistent-task-id")
            assert result is None


class TestCleanupOldTasks:
    """Tests for cleanup_old_tasks function."""

    def test_cleanup_removes_old_tasks(self, tmp_path):
        """cleanup_old_tasks should remove tasks older than TTL."""
        with patch("advisor_cli.cli_async.TASK_DIR", tmp_path):
            # Create an "old" task file
            old_task = tmp_path / "old-task.json"
            old_task.write_text(json.dumps({"result": {}, "created": 0}))

            # Set modification time to 2 hours ago
            old_time = time.time() - 7200
            import os

            os.utime(old_task, (old_time, old_time))

            assert old_task.exists()
            cleanup_old_tasks()
            assert not old_task.exists()

    def test_cleanup_keeps_recent_tasks(self, tmp_path):
        """cleanup_old_tasks should keep tasks newer than TTL."""
        with patch("advisor_cli.cli_async.TASK_DIR", tmp_path):
            # Create a recent task
            recent_task = tmp_path / "recent-task.json"
            recent_task.write_text(
                json.dumps({"result": {"fresh": True}, "created": time.time()})
            )

            cleanup_old_tasks()
            assert recent_task.exists()

    def test_cleanup_handles_missing_directory(self, tmp_path):
        """cleanup_old_tasks should handle non-existent TASK_DIR gracefully."""
        nonexistent = tmp_path / "does-not-exist"
        with patch("advisor_cli.cli_async.TASK_DIR", nonexistent):
            # Should not raise
            cleanup_old_tasks()

    def test_cleanup_handles_file_errors(self, tmp_path):
        """cleanup_old_tasks should handle OSError gracefully."""
        with patch("advisor_cli.cli_async.TASK_DIR", tmp_path):
            # Create a task file
            task_file = tmp_path / "error-task.json"
            task_file.write_text(json.dumps({"result": {}, "created": 0}))

            # Make it old
            old_time = time.time() - 7200
            import os

            os.utime(task_file, (old_time, old_time))

            # Mock unlink to raise OSError
            with patch.object(Path, "unlink", side_effect=OSError("Permission denied")):
                # Should not raise, just skip
                cleanup_old_tasks()
