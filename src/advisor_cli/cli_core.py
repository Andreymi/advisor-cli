"""Core CLI commands for advisor-cli.

This module provides the main user-facing commands:
- ask: Single model query
- compare: Multi-model comparison (consilium)
- result: Get async task result
- status: Show configuration status
- models: Show model configuration

These commands are the primary interface for interacting with LLMs.
"""

import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional

import typer

from .cli_async import TASK_DIR, cleanup_old_tasks, get_async_result
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

# Length of truncated task ID for async operations
TASK_ID_LENGTH = 8

# Typer app for core commands
core_app = typer.Typer()


def _run_background_task(cmd: list[str]) -> None:
    """Run a command in the background as a detached process.

    Uses subprocess.Popen with start_new_session to fully detach the process.
    Output is redirected to DEVNULL.

    Args:
        cmd: Command and arguments to execute

    Note:
        Silently handles OSError (e.g., command not found) to prevent
        crashes when the Python executable path is invalid.
    """
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        # Handle cases where subprocess cannot be started
        # (e.g., invalid executable path, permission denied)
        pass


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
        # Run in background via subprocess
        cmd = [
            sys.executable,
            "-c",
            f"""
import asyncio
import json
from advisor_cli.core import CompareExpertsInput, ResponseFormat, compare_experts, init_cache

init_cache()
params = CompareExpertsInput(
    query={repr(query)},
    context={repr(final_context)},
    models={repr(models or DEFAULT_MODELS_COMPARE)},
    response_format=ResponseFormat.{response_format.name},
    reasoning={repr(reasoning)},
)
result = asyncio.run(compare_experts(params))

from pathlib import Path
import time
TASK_DIR = Path({repr(str(TASK_DIR))})
TASK_DIR.mkdir(exist_ok=True)
task_file = TASK_DIR / "{task_id}.json"
task_file.write_text(json.dumps({{"result": result, "created": time.time()}}, ensure_ascii=False))
""",
        ]
        _run_background_task(cmd)
        print_output(f"Task ID: {task_id}")
        print_output(f"Получить результат: advisor result {task_id}")
    else:
        result = run_async(compare_experts(params))
        print_output(result)


@core_app.command()
def result(
    task_id: str = typer.Argument(..., help="ID задачи"),
    keep: bool = typer.Option(False, "--keep", help="Не удалять после прочтения"),
) -> None:
    """Получить результат фоновой задачи."""
    res = get_async_result(task_id, keep=keep)
    if res is None:
        print_output(f"Задача не найдена: {task_id}", error=True)
        raise typer.Exit(1)
    print_output(res)


@core_app.command()
def status() -> None:
    """Показать текущий статус конфигурации."""
    init_cache()
    from .core import CACHE_ACTIVE

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

    print_output(f"\nКэширование: {'включено' if CACHE_ACTIVE else 'выключено'}\n")


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
