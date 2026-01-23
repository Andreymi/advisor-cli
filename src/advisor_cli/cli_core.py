"""Core CLI commands for advisor-cli.

This module provides the main user-facing commands:
- ask: Single model query
- compare: Multi-model comparison (consilium)
- result: Get async task result
- status: Show configuration status
- models: Show model configuration

These commands are the primary interface for interacting with LLMs.
"""

import json
import logging
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional

import typer

from .cli_async import (
    TASK_ID_LENGTH,
    TaskStatus,
    cleanup_old_tasks,
    get_async_result,
    update_task_status,
)
from .cli_output import _parse_format, print_output
from .core import (
    CUSTOM_PROVIDERS,
    DEFAULT_MODEL,
    DEFAULT_MODELS_COMPARE,
    ENABLED_PROVIDERS,
    CompareExpertsInput,
    ConsultExpertInput,
    compare_experts,
    consult_expert,
    init_cache,
)
from .utils import run_async

logger = logging.getLogger(__name__)

# Typer app for core commands
core_app = typer.Typer()


def _run_background_task(
    task_id: str,
    task_type: str,
    params: dict,
) -> bool:
    """Run a task in the background using task_runner.

    Creates a pending task, then spawns a subprocess running task_runner.
    The subprocess handles timeout and status updates.

    Args:
        task_id: Unique task identifier
        task_type: Type of task ("compare" or "ask")
        params: Task parameters as a dictionary

    Returns:
        True if subprocess started successfully, False otherwise
    """
    # Create pending task
    update_task_status(task_id, TaskStatus.PENDING)

    # Build command
    params_json = json.dumps(params, ensure_ascii=False)
    cmd = [
        sys.executable,
        "-m",
        "advisor_cli.task_runner",
        task_id,
        task_type,
        params_json,
    ]

    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        logger.info(f"Started background task {task_id} ({task_type})")
        return True
    except OSError as e:
        # Update task status to failed
        update_task_status(
            task_id,
            TaskStatus.FAILED,
            error=f"Failed to start subprocess: {e}",
        )
        logger.error(f"Failed to start background task {task_id}: {e}")
        return False


@core_app.command()
def ask(
    query: str = typer.Argument(..., help="Вопрос к модели"),
    context: Optional[str] = typer.Option(
        None, "--context", "-c", help="Контекст inline"
    ),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Файл с контекстом"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Модель LLM"),
    format: Optional[str] = typer.Option(
        None, "--format", help="Формат: markdown|json"
    ),
    reasoning: Optional[str] = typer.Option(
        None, "--reasoning", "-r", help="Уровень reasoning: low|medium|high"
    ),
) -> None:
    """Получить ответ от LLM."""
    from .file_utils import build_context

    cleanup_old_tasks()
    init_cache()

    try:
        final_context = build_context(context, file)
    except (ValueError, FileNotFoundError) as e:
        print_output(str(e), error=True)
        raise typer.Exit(1)

    response_format = _parse_format(format)

    params = ConsultExpertInput(
        query=query,
        context=final_context,
        model=model or DEFAULT_MODEL,
        response_format=response_format,
        reasoning=reasoning,
    )

    result = run_async(consult_expert(params))
    print_output(result)


@core_app.command()
def compare(
    query: str = typer.Argument(..., help="Вопрос к моделям"),
    context: Optional[str] = typer.Option(
        None, "--context", "-c", help="Контекст inline"
    ),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Файл с контекстом"),
    models: Optional[str] = typer.Option(
        None, "--models", "-m", help="Модели через запятую"
    ),
    format: Optional[str] = typer.Option(
        None, "--format", help="Формат: markdown|json"
    ),
    reasoning: Optional[str] = typer.Option(
        None, "--reasoning", "-r", help="Уровень reasoning: low|medium|high"
    ),
    background: bool = typer.Option(False, "--async", help="Запустить в фоне"),
) -> None:
    """Получить ответы от нескольких LLM (консилиум)."""
    from .file_utils import build_context

    cleanup_old_tasks()
    init_cache()

    try:
        final_context = build_context(context, file)
    except (ValueError, FileNotFoundError) as e:
        print_output(str(e), error=True)
        raise typer.Exit(1)

    response_format = _parse_format(format)

    params = CompareExpertsInput(
        query=query,
        context=final_context,
        models=models or DEFAULT_MODELS_COMPARE,
        response_format=response_format,
        reasoning=reasoning,
    )

    if background:
        task_id = str(uuid.uuid4())[:TASK_ID_LENGTH]
        # Run in background via task_runner with timeout
        task_params = {
            "query": query,
            "context": final_context,
            "models": models or DEFAULT_MODELS_COMPARE,
            "response_format": response_format.name,
            "reasoning": reasoning,
        }
        success = _run_background_task(task_id, "compare", task_params)
        if success:
            print_output(f"Task ID: {task_id}")
            print_output(f"Получить результат: advisor result {task_id}")
            print_output(f"Проверить статус: advisor result {task_id} --keep")
        else:
            print_output("Не удалось запустить фоновую задачу", error=True)
            raise typer.Exit(1)
    else:
        result = run_async(compare_experts(params))
        print_output(result)


@core_app.command()
def result(
    task_id: str = typer.Argument(..., help="ID задачи"),
    keep: bool = typer.Option(False, "--keep", help="Не удалять после прочтения"),
) -> None:
    """Получить результат фоновой задачи.

    Если задача ещё выполняется, показывает текущий статус.
    С флагом --keep можно проверять статус без удаления файла.
    """
    from .cli_async import get_task_status

    # First check task status
    task_data = get_task_status(task_id)
    if task_data is None:
        print_output(f"Задача не найдена: {task_id}", error=True)
        raise typer.Exit(1)

    status = task_data.get("status")

    # Show status for pending/running tasks
    if status == TaskStatus.PENDING:
        print_output(f"Задача {task_id}: ожидает запуска")
        raise typer.Exit(0)
    elif status == TaskStatus.RUNNING:
        print_output(f"Задача {task_id}: выполняется...")
        raise typer.Exit(0)
    elif status == TaskStatus.TIMEOUT:
        error = task_data.get("error", "Превышено время ожидания")
        print_output(f"Задача {task_id}: таймаут - {error}", error=True)
        if not keep:
            # Clean up the task file
            get_async_result(task_id, keep=False)
        raise typer.Exit(1)
    elif status == TaskStatus.FAILED:
        error = task_data.get("error", "Неизвестная ошибка")
        print_output(f"Задача {task_id}: ошибка - {error}", error=True)
        if not keep:
            get_async_result(task_id, keep=False)
        raise typer.Exit(1)

    # For completed tasks, get the result
    res = get_async_result(task_id, keep=keep)
    if res is None:
        print_output(f"Результат задачи {task_id} не найден", error=True)
        raise typer.Exit(1)

    print_output(json.dumps(res, ensure_ascii=False, indent=2))


@core_app.command()
def status() -> None:
    """Показать текущий статус конфигурации."""
    from .core import CACHE_ENABLED

    print_output("\nAdvisor CLI - Статус\n")

    if ENABLED_PROVIDERS or CUSTOM_PROVIDERS:
        print_output("Включённые провайдеры:")
        for provider in ENABLED_PROVIDERS:
            print_output(f"  - {provider}")
        for provider in CUSTOM_PROVIDERS:
            print_output(f"  - {provider} (custom)")
    else:
        print_output("Нет включённых провайдеров.")
        print_output("Запустите 'advisor setup' для настройки.")

    print_output(f"\nКэширование: {'включено' if CACHE_ENABLED else 'выключено'}\n")


@core_app.command("models")
def models_cmd() -> None:
    """Показать настроенные модели и текущую конфигурацию."""
    print_output("\nТекущая конфигурация моделей\n")
    print_output(f"Single (ask): {DEFAULT_MODEL}")
    print_output(f"Compare (compare): {DEFAULT_MODELS_COMPARE}")

    print_output("\nДоступные модели по провайдерам:")

    try:
        from .setup_wizard import PROVIDER_INFO

        for provider in ENABLED_PROVIDERS:
            info = PROVIDER_INFO.get(provider, {})
            name = info.get("name", provider)
            models_list = info.get("models", [])
            print_output(f"\n  {name}:")
            for model in models_list:
                print_output(f"    - {model}")
    except ImportError:
        for provider in ENABLED_PROVIDERS:
            print_output(f"\n  {provider}:")
            print_output(f"    - {provider}/*")

    if CUSTOM_PROVIDERS:
        print_output("\n  Custom провайдеры:")
        for provider in CUSTOM_PROVIDERS:
            print_output(f"    - {provider}/*")

    print_output("")
