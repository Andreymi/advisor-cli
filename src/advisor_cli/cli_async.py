"""Async task utilities for advisor CLI.

This module provides functionality for managing asynchronous tasks:
- Creating tasks with results stored in temporary files
- Retrieving task results (with optional cleanup)
- Task status tracking (pending → running → completed/failed/timeout)
- Cleaning up expired tasks based on TTL

Tasks are stored as JSON files in a temporary directory with a configurable TTL.
"""

import json
import tempfile
import time
from pathlib import Path
from typing import Any

# Directory for storing async task results
TASK_DIR = Path(tempfile.gettempdir()) / "advisor-tasks"

# Time-to-live for task results in seconds (1 hour)
TASK_TTL_SECONDS = 3600

# Length of task ID (truncated UUID)
TASK_ID_LENGTH = 8


class TaskStatus:
    """Task status constants."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


def create_async_task(task_id: str, result: dict) -> None:
    """Save async task result to a temporary file.

    Creates a JSON file containing the result and creation timestamp.
    The task directory is created if it doesn't exist.

    Args:
        task_id: Unique identifier for the task
        result: Dictionary containing the task result to store

    Note:
        This is a legacy function for backward compatibility.
        New code should use task_runner.update_task_status().
    """
    TASK_DIR.mkdir(exist_ok=True)
    task_file = TASK_DIR / f"{task_id}.json"
    task_file.write_text(
        json.dumps(
            {
                "status": TaskStatus.COMPLETED,
                "result": result,
                "created": time.time(),
                "completed": time.time(),
            },
            ensure_ascii=False,
        )
    )


def get_task_status(task_id: str) -> dict[str, Any] | None:
    """Get task status and metadata without deleting the file.

    Args:
        task_id: Unique identifier for the task

    Returns:
        Dictionary with task status and metadata, or None if task doesn't exist
    """
    task_file = TASK_DIR / f"{task_id}.json"
    if not task_file.exists():
        return None

    try:
        return json.loads(task_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def get_async_result(task_id: str, keep: bool = False) -> dict | None:
    """Retrieve async task result from temporary file.

    By default, the task file is deleted after retrieval.
    Use keep=True to preserve the file for subsequent retrievals.

    Args:
        task_id: Unique identifier for the task
        keep: If True, preserve the task file after reading

    Returns:
        The task result dictionary, or None if task doesn't exist or not completed
    """
    task_file = TASK_DIR / f"{task_id}.json"
    if not task_file.exists():
        return None

    try:
        data = json.loads(task_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    # Handle legacy format (no status field)
    if "status" not in data:
        result = data.get("result")
        if not keep:
            task_file.unlink()
        return result

    # New format with status
    status = data.get("status")
    if status == TaskStatus.COMPLETED:
        result = data.get("result")
        if not keep:
            task_file.unlink()
        return result
    elif status in (TaskStatus.FAILED, TaskStatus.TIMEOUT):
        # Return error info as result
        error_result = {"error": data.get("error"), "status": status}
        if not keep:
            task_file.unlink()
        return error_result

    # Task is still pending or running
    return None


def cleanup_old_tasks() -> None:
    """Delete tasks older than TASK_TTL_SECONDS.

    Called on startup to clean up expired task files.
    Silently handles missing directory and file access errors.
    """
    if not TASK_DIR.exists():
        return

    now = time.time()
    for task_file in TASK_DIR.glob("*.json"):
        try:
            if now - task_file.stat().st_mtime > TASK_TTL_SECONDS:
                task_file.unlink()
        except OSError:
            # Skip files that can't be accessed or deleted
            pass
