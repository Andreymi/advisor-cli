# Code Simplification Refactoring Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate code duplication across advisor-cli modules, reducing ~235 lines while improving maintainability.

**Architecture:** Extract common patterns into utility functions in appropriate modules. Consolidate error handling into `core.py`, context building into `file_utils.py`, config operations into `config.py`.

**Tech Stack:** Python 3.10+, typer, pydantic, litellm

---

## Task 1: Consolidate Error Formatting

**Files:**
- Modify: `src/advisor_cli/core.py:181-220` (keep and enhance `format_error`)
- Modify: `src/advisor_cli/setup_wizard.py:119-162` (replace `parse_litellm_error` with import)

**Step 1: Enhance format_error in core.py**

Add missing cases from `parse_litellm_error` to `format_error`:

```python
def format_error(e: Exception, include_prefix: bool = True) -> str:
    """Форматирует ошибку litellm с понятным сообщением.

    Args:
        e: Exception to format
        include_prefix: If True, prefix with "Ошибка: "
    """
    error_type = type(e).__name__
    error_msg = str(e).strip()

    # AuthenticationError с пустым или неинформативным сообщением
    if "AuthenticationError" in error_type or "AuthenticationError" in error_msg:
        if not error_msg or error_msg.endswith(":") or len(error_msg) < 30:
            msg = "Неверный API ключ или ключ не имеет доступа к модели"
            return f"Ошибка: {msg}" if include_prefix else msg

    # Проверяем конкретные коды/типы ошибок
    error_map = [
        (["401", "Unauthorized"], "Неверный API ключ"),
        (["429", "rate limit", "RateLimitError"], "Превышен лимит запросов. Подождите и попробуйте снова"),
        (["timeout", "Timeout"], "Таймаут запроса. Попробуйте позже"),
        (["404", "NotFoundError", "not found"], "Модель не найдена. Проверьте название"),
        (["APIConnectionError", "Connection"], "Не удалось подключиться к API. Проверьте сеть"),
    ]

    error_msg_lower = error_msg.lower()
    for patterns, message in error_map:
        for pattern in patterns:
            if pattern.lower() in error_msg_lower or pattern in error_type:
                return f"Ошибка: {message}" if include_prefix else message

    # Очистка сообщения от типичных префиксов litellm
    for prefix in ["litellm.", "AuthenticationError:", "APIError:"]:
        if error_msg.startswith(prefix):
            error_msg = error_msg[len(prefix):].strip()

    # Обрезаем слишком длинные сообщения
    if len(error_msg) > 150:
        error_msg = error_msg[:150] + "..."

    if not error_msg:
        error_msg = "Неизвестная ошибка API"

    return f"Ошибка: {error_msg}" if include_prefix else error_msg
```

**Step 2: Update setup_wizard.py to use format_error**

Replace `parse_litellm_error` with import:

```python
# At top of file, add import
from .core import format_error

# Replace parse_litellm_error function with:
def parse_litellm_error(e: Exception) -> str:
    """Парсит ошибки litellm. Deprecated: use core.format_error."""
    return format_error(e, include_prefix=False)
```

**Step 3: Run tests**

```bash
uv run pytest tests/ -v
```

Expected: All 19 tests pass

**Step 4: Commit**

```bash
git add src/advisor_cli/core.py src/advisor_cli/setup_wizard.py
git commit -m "refactor: consolidate error formatting into core.format_error"
```

---

## Task 2: Extract Context Assembly Helper

**Files:**
- Modify: `src/advisor_cli/file_utils.py` (add `build_context` function)
- Modify: `src/advisor_cli/cli.py:128-149, 197-218` (use new helper)

**Step 1: Add build_context to file_utils.py**

```python
def build_context(
    context: str | None,
    file: "Path | None",
    read_stdin_fn: callable = None,
    read_file_fn: callable = None,
) -> str:
    """Собирает контекст из inline, stdin и файла.

    Args:
        context: Inline context string
        file: Path to context file
        read_stdin_fn: Function to read stdin (default: read_stdin)
        read_file_fn: Function to read file (default: read_context_file)

    Returns:
        Combined context string

    Raises:
        ValueError: If file not found or too large
    """
    if read_stdin_fn is None:
        read_stdin_fn = read_stdin
    if read_file_fn is None:
        read_file_fn = read_context_file

    final_context = context or ""

    # Из stdin
    stdin_data = read_stdin_fn()
    if stdin_data:
        final_context = (
            stdin_data if not final_context else f"{final_context}\n\n{stdin_data}"
        )

    # Из файла
    if file:
        file_content = read_file_fn(file)
        final_context = (
            file_content if not final_context else f"{final_context}\n\n{file_content}"
        )

    return final_context
```

**Step 2: Update cli.py ask command**

Replace lines 128-149 with:

```python
from .file_utils import build_context

# In ask():
try:
    final_context = build_context(context, file)
except (ValueError, FileNotFoundError) as e:
    print_output(str(e), error=True)
    raise typer.Exit(1)
```

**Step 3: Update cli.py compare command**

Replace lines 197-218 with same pattern.

**Step 4: Run tests**

```bash
uv run pytest tests/ -v
```

**Step 5: Manual test**

```bash
echo "test content" | uv run advisor ask "what is this?"
```

**Step 6: Commit**

```bash
git add src/advisor_cli/file_utils.py src/advisor_cli/cli.py
git commit -m "refactor: extract context assembly into build_context helper"
```

---

## Task 3: Extract Format Validation Helper

**Files:**
- Modify: `src/advisor_cli/cli.py` (add `_parse_format` helper, use in ask/compare)

**Step 1: Add _parse_format helper in cli.py**

Add after imports:

```python
def _parse_format(format_str: str | None) -> ResponseFormat:
    """Парсит строку формата в ResponseFormat enum.

    Args:
        format_str: "json", "markdown", or None

    Returns:
        ResponseFormat enum value

    Raises:
        typer.Exit: If format is invalid
    """
    if not format_str:
        return ResponseFormat.MARKDOWN

    format_lower = format_str.lower()
    if format_lower == "json":
        return ResponseFormat.JSON
    elif format_lower == "markdown":
        return ResponseFormat.MARKDOWN
    else:
        print_output(
            f"Неизвестный формат: {format_str}. Используйте markdown или json",
            error=True,
        )
        raise typer.Exit(1)
```

**Step 2: Update ask command**

Replace format validation block with:

```python
response_format = _parse_format(format)
```

**Step 3: Update compare command**

Same replacement.

**Step 4: Run tests and manual check**

```bash
uv run pytest tests/ -v
uv run advisor ask "test" --format json
uv run advisor ask "test" --format invalid  # should error
```

**Step 5: Commit**

```bash
git add src/advisor_cli/cli.py
git commit -m "refactor: extract format validation into _parse_format helper"
```

---

## Task 4: Create Optional Import Helper

**Files:**
- Create: `src/advisor_cli/utils.py`
- Modify: `src/advisor_cli/cli.py` (use new helper in 16 places)

**Step 1: Create utils.py with require_wizard decorator**

```python
"""Utility functions for advisor-cli."""

import functools
from typing import Callable, TypeVar

import typer

from .cli import print_output  # Will need to handle circular import

T = TypeVar("T")


class WizardNotInstalled(Exception):
    """Raised when wizard module is not installed."""
    pass


def require_wizard(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator that ensures wizard module is available.

    Usage:
        @require_wizard
        def my_command():
            from .setup_wizard import run_setup
            run_setup()
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ImportError:
            # Import here to avoid circular dependency
            from rich.console import Console
            console = Console()
            console.print(
                "[red]Wizard не установлен.[/red]\n"
                "[dim]Установите: pip install advisor-cli[wizard][/dim]"
            )
            raise typer.Exit(1)
    return wrapper
```

**Step 2: Update cli.py to use decorator**

Example for setup command:

```python
from .utils import require_wizard

@app.command()
@require_wizard
def setup(yes: bool = typer.Option(False, "-y", help="Non-interactive")):
    """Интерактивная настройка."""
    from .setup_wizard import run_setup
    run_setup(non_interactive=yes)
```

**Step 3: Apply to all 16 places with ImportError handling**

Search and replace pattern in cli.py.

**Step 4: Run tests**

```bash
uv run pytest tests/ -v
```

**Step 5: Commit**

```bash
git add src/advisor_cli/utils.py src/advisor_cli/cli.py
git commit -m "refactor: add require_wizard decorator to reduce ImportError boilerplate"
```

---

## Task 5: Simplify Config Update Operations

**Files:**
- Modify: `src/advisor_cli/config.py` (add `update_config` helper)
- Modify: `src/advisor_cli/cli.py` (use in config commands)

**Step 1: Add update_config to config.py**

```python
def update_config(key: str, value: str) -> None:
    """Обновляет одно значение в конфигурации.

    Args:
        key: Environment variable name (e.g., "ADVISOR_DEFAULT_MODEL")
        value: New value
    """
    env = load_config()
    env[key] = value
    save_config(env)
```

**Step 2: Update config_single in cli.py**

```python
@config_app.command("single")
def config_single(model: str = typer.Argument(...)):
    """Установить модель для ask."""
    from .config import update_config
    update_config("ADVISOR_DEFAULT_MODEL", model)
    print_output(f"Модель по умолчанию: {model}")
```

**Step 3: Update config_compare and config_format similarly**

**Step 4: Run tests**

```bash
uv run pytest tests/ -v
uv run advisor config single gemini/gemini-2.0-flash
uv run advisor config show
```

**Step 5: Commit**

```bash
git add src/advisor_cli/config.py src/advisor_cli/cli.py
git commit -m "refactor: add update_config helper for simpler config operations"
```

---

## Task 6: Remove Wrapper Functions in setup_wizard.py

**Files:**
- Modify: `src/advisor_cli/setup_wizard.py` (remove wrappers, use direct imports)

**Step 1: Remove load_existing_env and save_env wrappers**

Delete these functions:

```python
# DELETE these functions (lines ~99-116)
def load_existing_env() -> dict[str, str]:
    ...

def save_env(env_vars: dict[str, str]) -> None:
    ...
```

**Step 2: Update all usages to import from config**

At top of file:

```python
from .config import load_config, save_config
```

Replace all occurrences:
- `load_existing_env()` → `load_config()`
- `save_env(...)` → `save_config(...)`

**Step 3: Run tests**

```bash
uv run pytest tests/ -v
```

**Step 4: Commit**

```bash
git add src/advisor_cli/setup_wizard.py
git commit -m "refactor: remove wrapper functions, use config.py directly"
```

---

## Task 7: Extract Message Building Helper

**Files:**
- Modify: `src/advisor_cli/core.py` (add `_build_messages` helper)

**Step 1: Add _build_messages helper**

```python
def _build_messages(query: str, context: str | None, role: str) -> list[dict]:
    """Создаёт список сообщений для LLM запроса.

    Args:
        query: User query
        context: Optional context
        role: System role

    Returns:
        List of message dicts for litellm
    """
    user_content = f"{query}\n\nКонтекст:\n{context}" if context else query
    return [
        {"role": "system", "content": role},
        {"role": "user", "content": user_content},
    ]
```

**Step 2: Update consult_expert to use helper**

Replace message building with:

```python
messages = _build_messages(params.query, params.context, params.role)
```

**Step 3: Update compare_experts similarly**

**Step 4: Run tests**

```bash
uv run pytest tests/ -v
```

**Step 5: Commit**

```bash
git add src/advisor_cli/core.py
git commit -m "refactor: extract message building into _build_messages helper"
```

---

## Task 8: Consolidate Provider Info (Optional)

**Files:**
- Modify: `src/advisor_cli/config.py` (add PROVIDER_INFO)
- Modify: `src/advisor_cli/setup_wizard.py` (import from config)
- Modify: `src/advisor_cli/core.py` (use shared PROVIDER_INFO for PROVIDERS)

**Note:** This is lower priority and more invasive. Can be skipped if time constrained.

**Step 1: Move PROVIDER_INFO to config.py**

Move the full PROVIDER_INFO dict from setup_wizard.py to config.py.

**Step 2: Update imports**

In setup_wizard.py:
```python
from .config import PROVIDER_INFO
```

**Step 3: Derive PROVIDERS from PROVIDER_INFO in core.py**

```python
from .config import PROVIDER_INFO

PROVIDERS = {
    pid: {
        "env_key": info["env_key"],
        "enabled": lambda k=info["env_key"]: bool(os.getenv(k)),
    }
    for pid, info in PROVIDER_INFO.items()
}
```

**Step 4: Run tests**

```bash
uv run pytest tests/ -v
```

**Step 5: Commit**

```bash
git add src/advisor_cli/config.py src/advisor_cli/setup_wizard.py src/advisor_cli/core.py
git commit -m "refactor: consolidate PROVIDER_INFO into config.py"
```

---

## Final Verification

**Step 1: Run all tests**

```bash
uv run pytest tests/ -v
```

**Step 2: Manual smoke test**

```bash
uv run advisor status
uv run advisor models
uv run advisor config show
echo "hello" | uv run advisor ask "what is this?" --format json
```

**Step 3: Final commit (if any remaining changes)**

```bash
git status
# If clean, done!
```

---

## Summary

| Task | Description | Lines Saved |
|------|-------------|-------------|
| 1 | Consolidate error formatting | ~50 |
| 2 | Extract context assembly | ~40 |
| 3 | Extract format validation | ~20 |
| 4 | Create optional import helper | ~60 |
| 5 | Simplify config operations | ~15 |
| 6 | Remove wrapper functions | ~20 |
| 7 | Extract message building | ~15 |
| 8 | Consolidate provider info | ~30 |

**Total:** ~250 lines reduced, 8 commits
