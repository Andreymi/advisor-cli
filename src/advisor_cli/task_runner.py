"""Background task runner with timeout and status tracking.

This module is the entry point for background task execution via subprocess.
It imports task management utilities from cli_async and provides timeout handling.

Usage:
    python -m advisor_cli.task_runner <task_id> <task_type> <json_params>
"""

import asyncio
import json
import logging
import sys

# Configure logging for background tasks
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default timeout for LLM requests (5 minutes)
DEFAULT_TIMEOUT_SECONDS = 300

# Import task utilities from cli_async (single source of truth)
from .cli_async import TaskStatus, update_task_status


async def run_task(
    task_id: str,
    task_type: str,
    params: dict,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> None:
    """Run a task with timeout and status tracking.

    This is a unified task runner that handles both 'ask' and 'compare' tasks.

    Args:
        task_id: Unique task identifier
        task_type: Type of task ('ask' or 'compare')
        params: Task parameters dictionary
        timeout: Timeout in seconds
    """
    from advisor_cli.core import (
        CompareExpertsInput,
        ConsultExpertInput,
        ResponseFormat,
        compare_experts,
        consult_expert,
        init_cache,
    )

    logger.info(f"Starting {task_type} task {task_id} with timeout {timeout}s")
    update_task_status(task_id, TaskStatus.RUNNING)

    try:
        init_cache()

        # Parse response format
        response_format_str = params.get("response_format", "MARKDOWN")
        response_format = ResponseFormat[response_format_str]

        # Build input and get async function based on task type
        if task_type == "compare":
            input_params = CompareExpertsInput(
                query=params["query"],
                context=params.get("context"),
                models=params["models"],
                response_format=response_format,
                reasoning=params.get("reasoning"),
            )
            coro = compare_experts(input_params)
        elif task_type == "ask":
            input_params = ConsultExpertInput(
                query=params["query"],
                context=params.get("context"),
                model=params["model"],
                response_format=response_format,
                reasoning=params.get("reasoning"),
            )
            coro = consult_expert(input_params)
        else:
            raise ValueError(f"Unknown task type: {task_type}")

        # Run with timeout
        result = await asyncio.wait_for(coro, timeout=timeout)

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

    if task_type not in ("compare", "ask"):
        logger.error(f"Unknown task type: {task_type}")
        sys.exit(1)

    asyncio.run(run_task(task_id, task_type, params, timeout))


if __name__ == "__main__":
    main()
