# CLI Split & Tech Debt Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce cli.py from 1100+ lines to ~50 lines by splitting into focused modules, and fix subprocess security issues.

**Architecture:** Split cli.py by domain (core commands, config, mcp, skill, install) with shared utilities. Each module registers its own typer sub-app. Main cli.py only imports and assembles.

**Tech Stack:** Python 3.10+, typer, pydantic

---

## Task 1: Create cli_async.py (Async Task Utilities)

**Files:**
- Create: `src/advisor_cli/cli_async.py`
- Test: `tests/test_cli_async.py`
- Modify: `src/advisor_cli/cli.py` (remove lines 52-94)

**Step 1: Write the failing test**

```python
# tests/test_cli_async.py
"""Tests for async task utilities."""

import json
import pytest
import time
from pathlib import Path
from unittest.mock import patch

from advisor_cli.cli_async import (
    TASK_DIR,
    TASK_TTL_SECONDS,
    create_async_task,
    get_async_result,
    cleanup_old_tasks,
)


class TestAsyncTasks:
    """Tests for async task management."""

    def test_task_ttl_is_one_hour(self):
        """TASK_TTL should be documented as 1 hour."""
        assert TASK_TTL_SECONDS == 3600

    def test_create_and_get_task(self, tmp_path):
        """Should create and retrieve task."""
        with patch("advisor_cli.cli_async.TASK_DIR", tmp_path):
            task_id = "test123"
            result = {"response": "Hello"}

            create_async_task(task_id, result)

            retrieved = get_async_result(task_id, keep=True)
            assert retrieved == result

    def test_get_task_deletes_by_default(self, tmp_path):
        """Should delete task after retrieval by default."""
        with patch("advisor_cli.cli_async.TASK_DIR", tmp_path):
            task_id = "test456"
            create_async_task(task_id, {"data": "test"})

            # First retrieval
            get_async_result(task_id)

            # Second should be None
            assert get_async_result(task_id) is None

    def test_get_nonexistent_task_returns_none(self, tmp_path):
        """Should return None for missing task."""
        with patch("advisor_cli.cli_async.TASK_DIR", tmp_path):
            assert get_async_result("nonexistent") is None

    def test_cleanup_removes_old_tasks(self, tmp_path):
        """Should remove tasks older than TTL."""
        with patch("advisor_cli.cli_async.TASK_DIR", tmp_path):
            # Create old task file
            task_file = tmp_path / "old123.json"
            task_file.write_text(json.dumps({"result": "old", "created": 0}))

            cleanup_old_tasks()

            assert not task_file.exists()

    def test_cleanup_keeps_recent_tasks(self, tmp_path):
        """Should keep tasks newer than TTL."""
        with patch("advisor_cli.cli_async.TASK_DIR", tmp_path):
            task_file = tmp_path / "new123.json"
            task_file.write_text(json.dumps({"result": "new", "created": time.time()}))

            cleanup_old_tasks()

            assert task_file.exists()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_async.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'advisor_cli.cli_async'"

**Step 3: Write minimal implementation**

```python
# src/advisor_cli/cli_async.py
#!/usr/bin/env python3
"""Async task management for advisor-cli.

Background tasks are saved to temp files and can be retrieved later.
"""

import json
import tempfile
import time
from pathlib import Path

# Task storage directory
TASK_DIR = Path(tempfile.gettempdir()) / "advisor-tasks"

# Task time-to-live: 1 hour (3600 seconds)
# After this time, tasks are automatically cleaned up
TASK_TTL_SECONDS = 3600


def create_async_task(task_id: str, result: dict) -> None:
    """Save task result to temporary file.

    Args:
        task_id: Unique task identifier (usually UUID[:8])
        result: Task result to save
    """
    TASK_DIR.mkdir(exist_ok=True)
    task_file = TASK_DIR / f"{task_id}.json"
    task_file.write_text(
        json.dumps(
            {
                "result": result,
                "created": time.time(),
            },
            ensure_ascii=False,
        )
    )


def get_async_result(task_id: str, keep: bool = False) -> dict | None:
    """Get task result from temporary file.

    Args:
        task_id: Task identifier
        keep: If False (default), delete task file after retrieval

    Returns:
        Task result dict or None if not found
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

    Called on startup to prevent accumulation of stale tasks.
    """
    if not TASK_DIR.exists():
        return
    now = time.time()
    for f in TASK_DIR.glob("*.json"):
        try:
            if now - f.stat().st_mtime > TASK_TTL_SECONDS:
                f.unlink()
        except OSError:
            pass
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_async.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add src/advisor_cli/cli_async.py tests/test_cli_async.py
git commit -m "refactor: extract async task utils to cli_async.py"
```

---

## Task 2: Create cli_output.py (Output Utilities)

**Files:**
- Create: `src/advisor_cli/cli_output.py`
- Test: `tests/test_cli_output.py`

**Step 1: Write the failing test**

```python
# tests/test_cli_output.py
"""Tests for CLI output utilities."""

import pytest
import sys
from io import StringIO
from unittest.mock import patch

from advisor_cli.cli_output import print_output, _parse_format
from advisor_cli.core import ResponseFormat


class TestPrintOutput:
    """Tests for print_output function."""

    def test_prints_to_stdout(self, capsys):
        """Should print to stdout by default."""
        print_output("Hello")
        captured = capsys.readouterr()
        assert captured.out == "Hello\n"
        assert captured.err == ""

    def test_prints_to_stderr_when_error(self, capsys):
        """Should print to stderr when error=True."""
        print_output("Error message", error=True)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == "Error message\n"


class TestParseFormat:
    """Tests for _parse_format helper."""

    def test_none_returns_markdown(self):
        assert _parse_format(None) == ResponseFormat.MARKDOWN

    def test_json_lowercase(self):
        assert _parse_format("json") == ResponseFormat.JSON

    def test_json_uppercase(self):
        assert _parse_format("JSON") == ResponseFormat.JSON

    def test_markdown_lowercase(self):
        assert _parse_format("markdown") == ResponseFormat.MARKDOWN

    def test_markdown_mixed_case(self):
        assert _parse_format("Markdown") == ResponseFormat.MARKDOWN

    def test_invalid_format_exits(self):
        from typer import Exit
        with pytest.raises(Exit):
            _parse_format("invalid")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_output.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/advisor_cli/cli_output.py
#!/usr/bin/env python3
"""Output utilities for advisor-cli."""

import sys

import typer

from .core import ResponseFormat


def print_output(text: str, error: bool = False) -> None:
    """Print text to stdout or stderr.

    Args:
        text: Text to print
        error: If True, print to stderr instead of stdout
    """
    if error:
        sys.stderr.write(text + "\n")
    else:
        sys.stdout.write(text + "\n")


def _parse_format(format: str | None) -> ResponseFormat:
    """Parse format string to ResponseFormat enum.

    Args:
        format: 'json', 'markdown', or None

    Returns:
        ResponseFormat enum value

    Raises:
        typer.Exit: If format is invalid
    """
    if format is None:
        return ResponseFormat.MARKDOWN
    fmt_lower = format.lower()
    if fmt_lower == "json":
        return ResponseFormat.JSON
    elif fmt_lower == "markdown":
        return ResponseFormat.MARKDOWN
    else:
        print_output(f"Ошибка: Неизвестный формат '{format}'", error=True)
        raise typer.Exit(1)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_output.py -v`
Expected: PASS (8 tests)

**Step 5: Commit**

```bash
git add src/advisor_cli/cli_output.py tests/test_cli_output.py
git commit -m "refactor: extract output utils to cli_output.py"
```

---

## Task 3: Create cli_core.py (Core Commands: ask, compare, result, status, models)

**Files:**
- Create: `src/advisor_cli/cli_core.py`
- Modify: `src/advisor_cli/cli.py` (remove ask, compare, result, status, models commands)

**Step 1: Write the failing test**

```python
# tests/test_cli_core.py
"""Tests for core CLI commands module."""

import pytest
from typer.testing import CliRunner

# Import will fail until module exists
from advisor_cli.cli_core import core_app


runner = CliRunner()


class TestCoreAppExists:
    """Tests that core_app is properly defined."""

    def test_core_app_has_ask_command(self):
        """core_app should have ask command."""
        command_names = [cmd.name for cmd in core_app.registered_commands]
        assert "ask" in command_names

    def test_core_app_has_compare_command(self):
        """core_app should have compare command."""
        command_names = [cmd.name for cmd in core_app.registered_commands]
        assert "compare" in command_names

    def test_core_app_has_result_command(self):
        """core_app should have result command."""
        command_names = [cmd.name for cmd in core_app.registered_commands]
        assert "result" in command_names
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_core.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/advisor_cli/cli_core.py
#!/usr/bin/env python3
"""Core CLI commands for advisor-cli.

Contains: ask, compare, result, status, models
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
from .file_utils import build_context
from .utils import run_async

# Typer app for core commands
core_app = typer.Typer()


# Short task ID length (8 chars from UUID)
TASK_ID_LENGTH = 8


@core_app.command()
def ask(
    query: str = typer.Argument(..., help="Вопрос эксперту"),
    context: Optional[str] = typer.Option(None, "-c", "--context", help="Контекст"),
    file: Optional[Path] = typer.Option(None, "-f", "--file", help="Файл с контекстом"),
    model: Optional[str] = typer.Option(None, "-m", "--model", help="Модель"),
    role: Optional[str] = typer.Option(None, "-r", "--role", help="Роль эксперта"),
    format: Optional[str] = typer.Option(
        None, "--format", help="Формат вывода: markdown|json"
    ),
    background: bool = typer.Option(False, "--async", help="Выполнить в фоне"),
    reasoning: bool = typer.Option(
        False, "--reasoning", help="Использовать extended thinking"
    ),
) -> None:
    """Получить консультацию от эксперта (одна модель)."""
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
        role=role,
        response_format=response_format,
        reasoning=reasoning,
    )

    if background:
        _run_background_task(
            "consult_expert",
            params,
            response_format,
            reasoning,
        )
    else:
        result = run_async(consult_expert(params))
        print_output(result)


@core_app.command()
def compare(
    query: str = typer.Argument(..., help="Вопрос для сравнения"),
    context: Optional[str] = typer.Option(None, "-c", "--context", help="Контекст"),
    file: Optional[Path] = typer.Option(None, "-f", "--file", help="Файл с контекстом"),
    models: Optional[str] = typer.Option(
        None, "-m", "--models", help="Модели через запятую"
    ),
    format: Optional[str] = typer.Option(
        None, "--format", help="Формат вывода: markdown|json"
    ),
    background: bool = typer.Option(False, "--async", help="Выполнить в фоне"),
    reasoning: bool = typer.Option(
        False, "--reasoning", help="Использовать extended thinking"
    ),
) -> None:
    """Сравнить ответы нескольких моделей (консилиум)."""
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
        _run_background_task(
            "compare_experts",
            params,
            response_format,
            reasoning,
        )
    else:
        result = run_async(compare_experts(params))
        print_output(result)


def _run_background_task(
    func_name: str,
    params: ConsultExpertInput | CompareExpertsInput,
    response_format,
    reasoning: bool,
) -> None:
    """Run task in background subprocess with proper error handling.

    Args:
        func_name: Name of function to call ('consult_expert' or 'compare_experts')
        params: Input parameters for the function
        response_format: Output format enum
        reasoning: Whether to use extended thinking
    """
    task_id = str(uuid.uuid4())[:TASK_ID_LENGTH]

    # Build Python code to execute
    if func_name == "consult_expert":
        code = f'''
import asyncio
import json
import time
from pathlib import Path
from advisor_cli.core import ConsultExpertInput, ResponseFormat, consult_expert, init_cache

init_cache()
params = ConsultExpertInput(
    query={repr(params.query)},
    context={repr(params.context)},
    model={repr(params.model)},
    role={repr(params.role)},
    response_format=ResponseFormat.{response_format.name},
    reasoning={repr(reasoning)},
)
result = asyncio.run(consult_expert(params))

TASK_DIR = Path({repr(str(TASK_DIR))})
TASK_DIR.mkdir(exist_ok=True)
task_file = TASK_DIR / "{task_id}.json"
task_file.write_text(json.dumps({{"result": result, "created": time.time()}}, ensure_ascii=False))
'''
    else:
        code = f'''
import asyncio
import json
import time
from pathlib import Path
from advisor_cli.core import CompareExpertsInput, ResponseFormat, compare_experts, init_cache

init_cache()
params = CompareExpertsInput(
    query={repr(params.query)},
    context={repr(params.context)},
    models={repr(params.models)},
    response_format=ResponseFormat.{response_format.name},
    reasoning={repr(reasoning)},
)
result = asyncio.run(compare_experts(params))

TASK_DIR = Path({repr(str(TASK_DIR))})
TASK_DIR.mkdir(exist_ok=True)
task_file = TASK_DIR / "{task_id}.json"
task_file.write_text(json.dumps({{"result": result, "created": time.time()}}, ensure_ascii=False))
'''

    cmd = [sys.executable, "-c", code]

    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        print_output(f"Task ID: {task_id}")
        print_output(f"Получить результат: advisor result {task_id}")
    except OSError as e:
        print_output(f"Ошибка запуска фоновой задачи: {e}", error=True)
        raise typer.Exit(1)


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
        from .config import PROVIDER_INFO

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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_core.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/advisor_cli/cli_core.py tests/test_cli_core.py
git commit -m "refactor: extract core commands to cli_core.py"
```

---

## Task 4: Create cli_config.py (Config Commands)

**Files:**
- Create: `src/advisor_cli/cli_config.py`

**Step 1: Write the failing test**

```python
# tests/test_cli_config.py
"""Tests for config CLI commands module."""

import pytest

from advisor_cli.cli_config import config_app


class TestConfigAppExists:
    """Tests that config_app is properly defined."""

    def test_config_app_has_single_command(self):
        """config_app should have single command."""
        command_names = [cmd.name for cmd in config_app.registered_commands]
        assert "single" in command_names

    def test_config_app_has_compare_command(self):
        """config_app should have compare command."""
        command_names = [cmd.name for cmd in config_app.registered_commands]
        assert "compare" in command_names

    def test_config_app_has_show_command(self):
        """config_app should have show command."""
        command_names = [cmd.name for cmd in config_app.registered_commands]
        assert "show" in command_names

    def test_config_app_has_purge_command(self):
        """config_app should have purge command."""
        command_names = [cmd.name for cmd in config_app.registered_commands]
        assert "purge" in command_names
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_config.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/advisor_cli/cli_config.py
#!/usr/bin/env python3
"""Config CLI commands for advisor-cli.

Contains: config single, config compare, config format, config show, config purge
"""

from typing import Optional

import typer

from .cli_output import print_output
from .utils import run_async

# Typer app for config commands
config_app = typer.Typer(help="Управление конфигурацией")


@config_app.command("single")
def config_single(
    model: str = typer.Argument(..., help="Модель (например: gemini/gemini-2.5-pro)"),
    check: bool = typer.Option(
        True, "--check/--no-check", help="Проверить доступность модели"
    ),
) -> None:
    """Установить модель для ask (одиночный запрос)."""
    if "/" not in model:
        print_output("Ошибка: Формат модели: provider/model", error=True)
        raise typer.Exit(1)

    if check:
        print_output("Проверка модели...")
        try:
            from .setup_wizard import test_model

            success, msg = run_async(test_model(model))
            if not success:
                print_output(f"Ошибка: {msg}", error=True)
                raise typer.Exit(1)
            print_output("OK - Модель доступна")
        except ImportError:
            print_output("Wizard не установлен, пропускаем проверку")

    from .config import update_config

    update_config("ADVISOR_DEFAULT_MODEL", model)
    print_output(f"Модель по умолчанию: {model}")


@config_app.command("compare")
def config_compare(
    models_str: str = typer.Argument(
        ...,
        help="Модели через запятую (например: gemini/gemini-2.0-flash,openai/gpt-4o)",
    ),
    check: bool = typer.Option(
        True, "--check/--no-check", help="Проверить доступность моделей"
    ),
) -> None:
    """Установить модели для compare (консилиум)."""
    model_list = [m.strip() for m in models_str.split(",") if m.strip()]

    if not model_list:
        print_output("Ошибка: Список моделей пуст", error=True)
        raise typer.Exit(1)

    if check:
        try:
            from .setup_wizard import test_model

            all_ok = True
            for model in model_list:
                if "/" not in model:
                    print_output(f"  {model}: X Неверный формат", error=True)
                    all_ok = False
                    continue

                print_output(f"Проверка {model}...")
                success, msg = run_async(test_model(model))

                if success:
                    print_output(f"  {model}: OK")
                else:
                    print_output(f"  {model}: X {msg}", error=True)
                    all_ok = False

            if not all_ok:
                print_output("\nНекоторые модели недоступны")
        except ImportError:
            print_output("Wizard не установлен, пропускаем проверку")

    from .config import update_config

    update_config("ADVISOR_DEFAULT_MODELS_COMPARE", ",".join(model_list))
    print_output(f"\nМодели для сравнения: {', '.join(model_list)}")


@config_app.command("format")
def config_format(
    fmt: str = typer.Argument(..., help="Формат по умолчанию: markdown|json"),
) -> None:
    """Установить формат вывода по умолчанию."""
    if fmt.lower() not in ("markdown", "json"):
        print_output("Ошибка: Формат должен быть markdown или json", error=True)
        raise typer.Exit(1)

    from .config import update_config

    update_config("ADVISOR_OUTPUT_FORMAT", fmt.lower())
    print_output(f"Формат по умолчанию: {fmt.lower()}")


@config_app.command("show")
def config_show() -> None:
    """Показать текущую конфигурацию и расположение файлов."""
    from .config import CACHE_DIR, CONFIG_FILE, load_config, mask_api_key

    print_output("\n=== Advisor CLI Configuration ===\n")
    print_output(f"Config file: {CONFIG_FILE}")
    print_output(f"Cache dir:   {CACHE_DIR}")
    print_output(f"Config exists: {CONFIG_FILE.exists()}")
    print_output(f"Cache exists:  {CACHE_DIR.exists()}")

    if not CONFIG_FILE.exists():
        print_output("\nКонфигурация не найдена. Запустите: advisor setup")
        return

    env = load_config()

    print_output("\n--- API Keys ---")
    api_keys = [
        ("GEMINI_API_KEY", "Gemini"),
        ("OPENAI_API_KEY", "OpenAI"),
        ("ANTHROPIC_API_KEY", "Anthropic"),
        ("DEEPSEEK_API_KEY", "DeepSeek"),
        ("GROQ_API_KEY", "Groq"),
        ("OPENROUTER_API_KEY", "OpenRouter"),
        ("OLLAMA_HOST", "Ollama"),
        ("OLLAMA_API_KEY", "Ollama Cloud"),
    ]

    for key, name in api_keys:
        value = env.get(key, "")
        if value:
            print_output(f"  {name}: {mask_api_key(value)}")

    print_output("\n--- Models ---")
    print_output(f"  Default (ask):     {env.get('ADVISOR_DEFAULT_MODEL', 'not set')}")
    print_output(
        f"  Compare (compare): {env.get('ADVISOR_DEFAULT_MODELS_COMPARE', 'not set')}"
    )

    print_output("\n--- Options ---")
    cache = env.get("ADVISOR_CACHE_ENABLED", "true")
    ttl = env.get("ADVISOR_CACHE_TTL", "3600")
    verbose = env.get("ADVISOR_VERBOSE", "false")
    print_output(
        f"  Cache: {'enabled' if cache == 'true' else 'disabled'} (TTL: {ttl}s)"
    )
    print_output(f"  Verbose: {'enabled' if verbose == 'true' else 'disabled'}")
    print_output("")


@config_app.command("purge")
def config_purge(
    force: bool = typer.Option(False, "--force", "-f", help="Без подтверждения"),
) -> None:
    """Удалить файл конфигурации (API ключи)."""
    from .config import CONFIG_FILE, purge_config

    if not CONFIG_FILE.exists():
        print_output("Конфигурация не найдена.")
        return

    if not force:
        print_output(f"Будет удалён: {CONFIG_FILE}")
        try:
            import questionary

            confirm = questionary.confirm(
                "Удалить конфигурацию (API ключи)?",
                default=False,
            ).ask()
            if not confirm:
                print_output("Отменено.")
                return
        except ImportError:
            print_output("Используйте --force для подтверждения", error=True)
            raise typer.Exit(1)

    if purge_config():
        print_output("✓ Конфигурация удалена")
    else:
        print_output("Ничего не удалено")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_config.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add src/advisor_cli/cli_config.py tests/test_cli_config.py
git commit -m "refactor: extract config commands to cli_config.py"
```

---

## Task 5: Create cli_mcp.py (MCP Commands)

**Files:**
- Create: `src/advisor_cli/cli_mcp.py`

**Step 1: Write the failing test**

```python
# tests/test_cli_mcp.py
"""Tests for MCP CLI commands module."""

import pytest

from advisor_cli.cli_mcp import mcp_app


class TestMcpAppExists:
    """Tests that mcp_app is properly defined."""

    def test_mcp_app_has_install_command(self):
        """mcp_app should have install command."""
        command_names = [cmd.name for cmd in mcp_app.registered_commands]
        assert "install" in command_names

    def test_mcp_app_has_uninstall_command(self):
        """mcp_app should have uninstall command."""
        command_names = [cmd.name for cmd in mcp_app.registered_commands]
        assert "uninstall" in command_names

    def test_mcp_app_has_status_command(self):
        """mcp_app should have status command."""
        command_names = [cmd.name for cmd in mcp_app.registered_commands]
        assert "status" in command_names
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_mcp.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/advisor_cli/cli_mcp.py` with all MCP commands extracted from cli.py lines 594-862.

(Full code similar to current cli.py mcp_app section, wrapped in cli_mcp.py module)

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_mcp.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/advisor_cli/cli_mcp.py tests/test_cli_mcp.py
git commit -m "refactor: extract mcp commands to cli_mcp.py"
```

---

## Task 6: Create cli_skill.py (Skill Commands)

**Files:**
- Create: `src/advisor_cli/cli_skill.py`

**Step 1: Write the failing test**

```python
# tests/test_cli_skill.py
"""Tests for Skill CLI commands module."""

import pytest

from advisor_cli.cli_skill import skill_app


class TestSkillAppExists:
    """Tests that skill_app is properly defined."""

    def test_skill_app_has_install_command(self):
        """skill_app should have install command."""
        command_names = [cmd.name for cmd in skill_app.registered_commands]
        assert "install" in command_names

    def test_skill_app_has_uninstall_command(self):
        """skill_app should have uninstall command."""
        command_names = [cmd.name for cmd in skill_app.registered_commands]
        assert "uninstall" in command_names

    def test_skill_app_has_status_command(self):
        """skill_app should have status command."""
        command_names = [cmd.name for cmd in skill_app.registered_commands]
        assert "status" in command_names
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_skill.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/advisor_cli/cli_skill.py` with all skill commands extracted from cli.py lines 865-984.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_skill.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/advisor_cli/cli_skill.py tests/test_cli_skill.py
git commit -m "refactor: extract skill commands to cli_skill.py"
```

---

## Task 7: Create cli_install.py (Unified Install + Uninstall)

**Files:**
- Create: `src/advisor_cli/cli_install.py`

**Step 1: Write the failing test**

```python
# tests/test_cli_install.py
"""Tests for install CLI commands module."""

import pytest

from advisor_cli.cli_install import install_app


class TestInstallAppExists:
    """Tests that install_app is properly defined."""

    def test_install_app_has_install_command(self):
        """install_app should have install command."""
        command_names = [cmd.name for cmd in install_app.registered_commands]
        assert "install" in command_names

    def test_install_app_has_uninstall_command(self):
        """install_app should have uninstall command."""
        command_names = [cmd.name for cmd in install_app.registered_commands]
        assert "uninstall" in command_names
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_install.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/advisor_cli/cli_install.py` with install and uninstall commands.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_install.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add src/advisor_cli/cli_install.py tests/test_cli_install.py
git commit -m "refactor: extract install commands to cli_install.py"
```

---

## Task 8: Rewrite cli.py as Entry Point

**Files:**
- Modify: `src/advisor_cli/cli.py` (rewrite to ~60 lines)

**Step 1: Write the failing test**

```python
# tests/test_cli_entry.py
"""Tests for CLI entry point."""

import pytest
from typer.testing import CliRunner

from advisor_cli.cli import app

runner = CliRunner()


class TestCliEntryPoint:
    """Tests that main app assembles all sub-apps."""

    def test_app_has_ask_command(self):
        """Main app should have ask command."""
        result = runner.invoke(app, ["ask", "--help"])
        assert result.exit_code == 0

    def test_app_has_config_subapp(self):
        """Main app should have config sub-app."""
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0

    def test_app_has_mcp_subapp(self):
        """Main app should have mcp sub-app."""
        result = runner.invoke(app, ["mcp", "--help"])
        assert result.exit_code == 0

    def test_app_has_skill_subapp(self):
        """Main app should have skill sub-app."""
        result = runner.invoke(app, ["skill", "--help"])
        assert result.exit_code == 0

    def test_app_has_install_command(self):
        """Main app should have install command."""
        result = runner.invoke(app, ["install", "--help"])
        assert result.exit_code == 0
```

**Step 2: Run test to verify current cli.py passes (baseline)**

Run: `uv run pytest tests/test_cli_entry.py -v`
Expected: PASS (tests should pass with current cli.py)

**Step 3: Rewrite cli.py as minimal entry point**

```python
#!/usr/bin/env python3
"""CLI entry point for advisor-cli.

This module assembles all CLI sub-apps into the main application.
"""

import warnings

import typer

# Suppress warnings before importing other modules
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", message="coroutine .* was never awaited")

# Import sub-apps
from .cli_config import config_app
from .cli_core import core_app
from .cli_install import install_app
from .cli_mcp import mcp_app
from .cli_skill import skill_app
from .utils import require_wizard

# Main application
app = typer.Typer(
    name="advisor",
    help="CLI для получения второго мнения от альтернативных LLM",
    no_args_is_help=True,
)

# Register core commands directly on main app
for command in core_app.registered_commands:
    app.command(command.name)(command.callback)

# Register sub-apps
app.add_typer(config_app, name="config")
app.add_typer(mcp_app, name="mcp")
app.add_typer(skill_app, name="skill")

# Register install commands directly on main app
for command in install_app.registered_commands:
    app.command(command.name)(command.callback)


@app.command()
@require_wizard
def setup(
    yes: bool = typer.Option(
        False, "-y", help="Неинтерактивный режим (использовать env vars)"
    ),
    providers: str | None = typer.Option(
        None, "-p", "--providers", help="Провайдеры через запятую"
    ),
    model: str | None = typer.Option(
        None, "-m", "--model", help="Модель по умолчанию"
    ),
) -> None:
    """Интерактивная настройка конфигурации (требует установки с [wizard])."""
    from .setup_wizard import run_setup

    provider_list = None
    if providers:
        provider_list = [p.strip() for p in providers.split(",")]

    run_setup(
        non_interactive=yes,
        providers=provider_list,
        model=model,
    )


@app.command()
def run() -> None:
    """Запустить MCP сервер (требует установки с [mcp])."""
    try:
        from .server import main as run_server

        run_server()
    except ImportError:
        from .cli_output import print_output

        print_output(
            "MCP не установлен. Установите: pip install advisor-cli[mcp]", error=True
        )
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
```

**Step 4: Run all tests to verify nothing broke**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/advisor_cli/cli.py
git commit -m "refactor: cli.py is now minimal entry point (~70 lines)"
```

---

## Task 9: Update TECHNICAL_DEBT.md

**Files:**
- Modify: `docs/TECHNICAL_DEBT.md`

**Step 1: Move completed items to Resolved section**

```markdown
### 2026-01-24: CLI Split Sprint
- ✅ Split cli.py into modules (cli_async, cli_output, cli_core, cli_config, cli_mcp, cli_skill, cli_install)
- ✅ Added TASK_TTL_SECONDS constant with documentation
- ✅ Added TASK_ID_LENGTH constant
- ✅ Improved subprocess error handling (OSError catch)
```

**Step 2: Commit**

```bash
git add docs/TECHNICAL_DEBT.md
git commit -m "docs: mark CLI split as resolved in tech debt"
```

---

## Task 10: Final Verification

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

**Step 2: Test CLI manually**

```bash
advisor --help
advisor ask --help
advisor config show
advisor mcp status
advisor skill status
```

**Step 3: Verify line counts**

```bash
wc -l src/advisor_cli/cli*.py
```

Expected output (approximate):
```
  70 src/advisor_cli/cli.py
  65 src/advisor_cli/cli_async.py
  35 src/advisor_cli/cli_output.py
 180 src/advisor_cli/cli_core.py
 120 src/advisor_cli/cli_config.py
 250 src/advisor_cli/cli_mcp.py
 120 src/advisor_cli/cli_skill.py
 100 src/advisor_cli/cli_install.py
 940 total
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "refactor: complete CLI split - cli.py reduced from 1102 to ~70 lines"
git push
```

---

## Summary

| Task | Module | Lines | Purpose |
|------|--------|-------|---------|
| 1 | cli_async.py | ~65 | Async task storage |
| 2 | cli_output.py | ~35 | Output utilities |
| 3 | cli_core.py | ~180 | ask, compare, result, status, models |
| 4 | cli_config.py | ~120 | config single/compare/format/show/purge |
| 5 | cli_mcp.py | ~250 | mcp install/uninstall/status |
| 6 | cli_skill.py | ~120 | skill install/uninstall/status |
| 7 | cli_install.py | ~100 | install, uninstall |
| 8 | cli.py | ~70 | Entry point only |

**Before:** 1102 lines in one file
**After:** ~940 lines across 8 focused modules

**Tech debt resolved:**
- ✅ #2 cli.py too large (MEDIUM)
- ✅ #3 partial: TASK_TTL_SECONDS documented (LOW)
- ✅ #1 partial: subprocess error handling improved (MEDIUM)
