"""Async task utilities for advisor CLI.

This module provides functionality for managing asynchronous tasks:
- Creating tasks with results stored in temporary files
- Retrieving task results (with optional cleanup)
- Cleaning up expired tasks based on TTL

Tasks are stored as JSON files in a temporary directory with a configurable TTL.
"""

import json
import tempfile
import time
from pathlib import Path

# Directory for storing async task results
TASK_DIR = Path(tempfile.gettempdir()) / "advisor-tasks"

# Time-to-live for task results in seconds (1 hour)
TASK_TTL_SECONDS = 3600


def create_async_task(task_id: str, result: dict) -> None:
    """Save async task result to a temporary file.

    Creates a JSON file containing the result and creation timestamp.
    The task directory is created if it doesn't exist.

    Args:
        task_id: Unique identifier for the task
        result: Dictionary containing the task result to store
    """
    TASK_DIR.mkdir(exist_ok=True)
    task_file = TASK_DIR / f"{task_id}.json"
    task_file.write_text(
        json.dumps({"result": result, "created": time.time()}, ensure_ascii=False)
    )


def get_async_result(task_id: str, keep: bool = False) -> dict | None:
    """Retrieve async task result from temporary file.

    By default, the task file is deleted after retrieval.
    Use keep=True to preserve the file for subsequent retrievals.

    Args:
        task_id: Unique identifier for the task
        keep: If True, preserve the task file after reading

    Returns:
        The task result dictionary, or None if task doesn't exist
    """
    task_file = TASK_DIR / f"{task_id}.json"
    if not task_file.exists():
        return None

    data = json.loads(task_file.read_text())

    if not keep:
        task_file.unlink()

    return data["result"]


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
