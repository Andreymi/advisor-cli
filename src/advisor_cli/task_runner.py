"""Background task runner with timeout and status tracking.

This module provides a managed way to run async tasks in the background:
- Timeout mechanism using asyncio.wait_for
- Status tracking (pending → running → completed/failed/timeout)
- Proper error logging and reporting

Usage:
    python -m advisor_cli.task_runner <task_id> <task_type> <json_params>
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

# Configure logging for background tasks
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default timeout for LLM requests (5 minutes)
DEFAULT_TIMEOUT_SECONDS = 300


class TaskStatus:
    """Task status constants."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


def get_task_dir() -> Path:
    """Get task directory (same as cli_async.TASK_DIR)."""
    import tempfile

    return Path(tempfile.gettempdir()) / "advisor-tasks"


def update_task_status(
    task_id: str,
    status: str,
    result: Any = None,
    error: str | None = None,
) -> None:
    """Update task status in the task file.

    Args:
        task_id: Unique task identifier
        status: One of TaskStatus constants
        result: Task result (for completed tasks)
        error: Error message (for failed/timeout tasks)
    """
    task_dir = get_task_dir()
    task_dir.mkdir(exist_ok=True)
    task_file = task_dir / f"{task_id}.json"

    data = {
        "status": status,
        "updated": time.time(),
    }

    if status == TaskStatus.PENDING:
        data["created"] = time.time()
    elif status == TaskStatus.COMPLETED:
        data["result"] = result
        data["completed"] = time.time()
    elif status in (TaskStatus.FAILED, TaskStatus.TIMEOUT):
        data["error"] = error
        data["completed"] = time.time()

    # Merge with existing data if present
    if task_file.exists():
        try:
            existing = json.loads(task_file.read_text())
            existing.update(data)
            data = existing
        except (json.JSONDecodeError, OSError):
            pass

    task_file.write_text(json.dumps(data, ensure_ascii=False))


async def run_compare_task(
    task_id: str,
    params: dict,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> None:
    """Run compare_experts task with timeout.

    Args:
        task_id: Unique task identifier
        params: Parameters for compare_experts
        timeout: Timeout in seconds
    """
    from advisor_cli.core import (
        CompareExpertsInput,
        ResponseFormat,
        compare_experts,
        init_cache,
    )

    logger.info(f"Starting task {task_id} with timeout {timeout}s")
    update_task_status(task_id, TaskStatus.RUNNING)

    try:
        init_cache()

        # Parse response format
        response_format_str = params.get("response_format", "MARKDOWN")
        response_format = ResponseFormat[response_format_str]

        input_params = CompareExpertsInput(
            query=params["query"],
            context=params.get("context"),
            models=params["models"],
            response_format=response_format,
            reasoning=params.get("reasoning"),
        )

        # Run with timeout
        result = await asyncio.wait_for(
            compare_experts(input_params),
            timeout=timeout,
        )

        update_task_status(task_id, TaskStatus.COMPLETED, result=result)
        logger.info(f"Task {task_id} completed successfully")

    except asyncio.TimeoutError:
        error_msg = f"Task timed out after {timeout} seconds"
        update_task_status(task_id, TaskStatus.TIMEOUT, error=error_msg)
        logger.error(f"Task {task_id}: {error_msg}")

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        update_task_status(task_id, TaskStatus.FAILED, error=error_msg)
        logger.error(f"Task {task_id} failed: {error_msg}")


async def run_ask_task(
    task_id: str,
    params: dict,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> None:
    """Run consult_expert task with timeout.

    Args:
        task_id: Unique task identifier
        params: Parameters for consult_expert
        timeout: Timeout in seconds
    """
    from advisor_cli.core import (
        ConsultExpertInput,
        ResponseFormat,
        consult_expert,
        init_cache,
    )

    logger.info(f"Starting task {task_id} with timeout {timeout}s")
    update_task_status(task_id, TaskStatus.RUNNING)

    try:
        init_cache()

        response_format_str = params.get("response_format", "MARKDOWN")
        response_format = ResponseFormat[response_format_str]

        input_params = ConsultExpertInput(
            query=params["query"],
            context=params.get("context"),
            model=params["model"],
            response_format=response_format,
            reasoning=params.get("reasoning"),
        )

        result = await asyncio.wait_for(
            consult_expert(input_params),
            timeout=timeout,
        )

        update_task_status(task_id, TaskStatus.COMPLETED, result=result)
        logger.info(f"Task {task_id} completed successfully")

    except asyncio.TimeoutError:
        error_msg = f"Task timed out after {timeout} seconds"
        update_task_status(task_id, TaskStatus.TIMEOUT, error=error_msg)
        logger.error(f"Task {task_id}: {error_msg}")

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        update_task_status(task_id, TaskStatus.FAILED, error=error_msg)
        logger.error(f"Task {task_id} failed: {error_msg}")


def main() -> None:
    """Entry point for background task runner."""
    if len(sys.argv) < 4:
        print(
            "Usage: python -m advisor_cli.task_runner <task_id> <task_type> <json_params>"
        )
        sys.exit(1)

    task_id = sys.argv[1]
    task_type = sys.argv[2]
    params_json = sys.argv[3]

    try:
        params = json.loads(params_json)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON params: {e}")
        sys.exit(1)

    timeout = params.pop("timeout", DEFAULT_TIMEOUT_SECONDS)

    if task_type == "compare":
        asyncio.run(run_compare_task(task_id, params, timeout))
    elif task_type == "ask":
        asyncio.run(run_ask_task(task_id, params, timeout))
    else:
        logger.error(f"Unknown task type: {task_type}")
        sys.exit(1)


if __name__ == "__main__":
    main()
