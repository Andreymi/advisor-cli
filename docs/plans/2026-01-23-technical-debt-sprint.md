# Technical Debt Sprint Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all high-priority technical debt items (#1-6) to improve code quality and testability.

**Architecture:** Add comprehensive tests, consolidate provider configuration, standardize code style.

**Tech Stack:** Python 3.10+, pytest, typer, pydantic

---

## Task 1: Add Tests for New Helper Functions

**Files:**
- Create: `tests/test_helpers.py`
- Create: `tests/test_config.py`

**Step 1: Create test_helpers.py with tests for CLI helpers**

```python
"""Tests for helper functions introduced during refactoring."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from advisor_cli.cli import _parse_format
from advisor_cli.core import ResponseFormat


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
        with pytest.raises(SystemExit):
            _parse_format("invalid")
```

**Step 2: Add tests for build_context**

```python
from advisor_cli.file_utils import build_context


class TestBuildContext:
    """Tests for build_context helper."""

    def test_none_inputs_returns_empty(self):
        with patch("advisor_cli.file_utils.read_stdin", return_value=None):
            assert build_context(None, None) == ""

    def test_context_only(self):
        with patch("advisor_cli.file_utils.read_stdin", return_value=None):
            assert build_context("my context", None) == "my context"

    def test_stdin_only(self):
        with patch("advisor_cli.file_utils.read_stdin", return_value="stdin data"):
            assert build_context(None, None) == "stdin data"

    def test_context_and_stdin_combined(self):
        with patch("advisor_cli.file_utils.read_stdin", return_value="stdin data"):
            result = build_context("my context", None)
            assert "my context" in result
            assert "stdin data" in result

    def test_file_context(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("file content")
        with patch("advisor_cli.file_utils.read_stdin", return_value=None):
            result = build_context(None, test_file)
            assert result == "file content"
```

**Step 3: Add tests for _build_messages**

```python
from advisor_cli.core import _build_messages


class TestBuildMessages:
    """Tests for _build_messages helper."""

    def test_query_only(self):
        messages = _build_messages("What is Python?", None, "You are helpful.")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are helpful."
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "What is Python?"

    def test_query_with_context(self):
        messages = _build_messages("Review this", "code here", "You are a reviewer.")
        assert len(messages) == 2
        assert "Контекст:" in messages[1]["content"]
        assert "code here" in messages[1]["content"]
        assert "Review this" in messages[1]["content"]
```

**Step 4: Create test_config.py**

```python
"""Tests for config module."""

import pytest
from pathlib import Path
from unittest.mock import patch
import tempfile
import os

from advisor_cli.config import (
    load_config,
    save_config,
    update_config,
    mask_api_key,
    get_config_dir,
    get_cache_dir,
)


class TestMaskApiKey:
    """Tests for mask_api_key helper."""

    def test_short_key(self):
        assert mask_api_key("abc") == "***"

    def test_normal_key(self):
        result = mask_api_key("sk-1234567890abcdef")
        assert result.startswith("sk-1")
        assert result.endswith("cdef")
        assert "***" in result

    def test_empty_key(self):
        assert mask_api_key("") == ""


class TestConfigPaths:
    """Tests for XDG path functions."""

    def test_get_config_dir_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.dict(os.environ, {"HOME": "/home/test"}):
                # Should use ~/.config/advisor
                path = get_config_dir()
                assert "advisor" in str(path)

    def test_get_config_dir_xdg(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"}):
            path = get_config_dir()
            assert "/custom/config/advisor" in str(path) or "advisor" in str(path)


class TestLoadSaveConfig:
    """Tests for load/save config."""

    def test_load_empty_config(self, tmp_path):
        with patch("advisor_cli.config.CONFIG_FILE", tmp_path / "config.env"):
            config = load_config()
            assert config == {}

    def test_save_and_load_config(self, tmp_path):
        config_file = tmp_path / "config.env"
        with patch("advisor_cli.config.CONFIG_FILE", config_file):
            save_config({"TEST_KEY": "test_value"})
            loaded = load_config()
            assert loaded["TEST_KEY"] == "test_value"


class TestUpdateConfig:
    """Tests for update_config helper."""

    def test_update_single_key(self, tmp_path):
        config_file = tmp_path / "config.env"
        with patch("advisor_cli.config.CONFIG_FILE", config_file):
            save_config({})
            update_config("NEW_KEY", "new_value")
            loaded = load_config()
            assert loaded["NEW_KEY"] == "new_value"

    def test_update_preserves_existing(self, tmp_path):
        config_file = tmp_path / "config.env"
        with patch("advisor_cli.config.CONFIG_FILE", config_file):
            save_config({"EXISTING": "value"})
            update_config("NEW_KEY", "new_value")
            loaded = load_config()
            assert loaded["EXISTING"] == "value"
            assert loaded["NEW_KEY"] == "new_value"
```

**Step 5: Add test for require_wizard decorator**

```python
from advisor_cli.utils import require_wizard


class TestRequireWizard:
    """Tests for require_wizard decorator."""

    def test_function_works_when_import_succeeds(self):
        @require_wizard
        def my_func():
            return "success"

        assert my_func() == "success"

    def test_exits_on_import_error(self):
        @require_wizard
        def my_func():
            raise ImportError("questionary not found")

        with pytest.raises(SystemExit):
            my_func()
```

**Step 6: Run tests**

```bash
uv run pytest tests/test_helpers.py tests/test_config.py -v
```

**Step 7: Commit**

```bash
git add tests/test_helpers.py tests/test_config.py
git commit -m "test: add comprehensive tests for helper functions and config"
```

---

## Task 2: Consolidate PROVIDER_INFO (Task 8 from previous plan)

**Files:**
- Modify: `src/advisor_cli/config.py` (add PROVIDER_INFO)
- Modify: `src/advisor_cli/setup_wizard.py` (import from config)
- Modify: `src/advisor_cli/core.py` (derive PROVIDERS from PROVIDER_INFO)

**Step 1: Move PROVIDER_INFO to config.py**

Add to config.py after imports:

```python
PROVIDER_INFO: dict[str, dict] = {
    "gemini": {
        "name": "Google Gemini",
        "env_key": "GEMINI_API_KEY",
        "url": "https://aistudio.google.com/apikey",
        "test_model": "gemini/gemini-2.0-flash",
        "models": [
            "gemini/gemini-2.0-flash",
            "gemini/gemini-2.0-flash-lite",
            "gemini/gemini-2.5-pro-preview-05-06",
        ],
    },
    "openai": {
        "name": "OpenAI",
        "env_key": "OPENAI_API_KEY",
        "url": "https://platform.openai.com/api-keys",
        "test_model": "openai/gpt-4o-mini",
        "models": [
            "openai/gpt-4o-mini",
            "openai/gpt-4o",
            "openai/gpt-4.1",
            "openai/o3-mini",
        ],
    },
    "anthropic": {
        "name": "Anthropic",
        "env_key": "ANTHROPIC_API_KEY",
        "url": "https://console.anthropic.com/settings/keys",
        "test_model": "anthropic/claude-3-5-haiku-latest",
        "models": [
            "anthropic/claude-3-5-haiku-latest",
            "anthropic/claude-sonnet-4-20250514",
        ],
    },
    "deepseek": {
        "name": "DeepSeek",
        "env_key": "DEEPSEEK_API_KEY",
        "url": "https://platform.deepseek.com/api_keys",
        "test_model": "deepseek/deepseek-chat",
        "models": ["deepseek/deepseek-chat", "deepseek/deepseek-reasoner"],
    },
    "groq": {
        "name": "Groq",
        "env_key": "GROQ_API_KEY",
        "url": "https://console.groq.com/keys",
        "test_model": "groq/llama-3.3-70b-versatile",
        "models": [
            "groq/llama-3.3-70b-versatile",
            "groq/llama-3.1-8b-instant",
            "groq/mixtral-8x7b-32768",
        ],
    },
    "openrouter": {
        "name": "OpenRouter",
        "env_key": "OPENROUTER_API_KEY",
        "url": "https://openrouter.ai/keys",
        "test_model": "openrouter/google/gemini-2.0-flash-001",
        "models": [
            "openrouter/google/gemini-2.0-flash-001",
            "openrouter/openai/gpt-4o-mini",
            "openrouter/anthropic/claude-3.5-haiku",
        ],
    },
    "ollama": {
        "name": "Ollama (local)",
        "env_key": None,
        "url": "https://ollama.com",
        "test_model": "ollama/llama3.2",
        "models": ["ollama/llama3.2", "ollama/mistral", "ollama/codellama"],
        "base_url": "http://localhost:11434",
    },
    "ollama-cloud": {
        "name": "Ollama Cloud",
        "env_key": "OLLAMA_CLOUD_API_KEY",
        "url": "https://ollama.com/cloud",
        "test_model": "ollama-cloud/llama3.2",
        "models": ["ollama-cloud/llama3.2", "ollama-cloud/mistral"],
        "base_url_env": "OLLAMA_CLOUD_BASE_URL",
    },
}


def get_provider_env_key(provider_id: str) -> str | None:
    """Get environment variable key for provider."""
    info = PROVIDER_INFO.get(provider_id)
    return info["env_key"] if info else None


def get_enabled_providers() -> list[str]:
    """Get list of providers with configured API keys."""
    import os
    enabled = []
    for pid, info in PROVIDER_INFO.items():
        env_key = info.get("env_key")
        if env_key is None:  # Ollama local - always enabled
            enabled.append(pid)
        elif os.getenv(env_key):
            enabled.append(pid)
    return enabled
```

**Step 2: Update setup_wizard.py imports**

Replace PROVIDER_INFO definition with import:

```python
from .config import PROVIDER_INFO, get_enabled_providers
```

Remove the PROVIDER_INFO dict from setup_wizard.py (lines ~33-97).

**Step 3: Update core.py to use PROVIDER_INFO**

Replace PROVIDERS dict with:

```python
from .config import PROVIDER_INFO

def _build_providers() -> dict:
    """Build PROVIDERS dict from PROVIDER_INFO."""
    providers = {}
    for pid, info in PROVIDER_INFO.items():
        env_key = info.get("env_key")
        providers[pid] = {
            "env_key": env_key,
            "enabled": (
                True if env_key is None  # Ollama local
                else bool(os.getenv(env_key))
            ),
        }
    return providers

PROVIDERS = _build_providers()
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

## Task 3: Standardize Docstrings to English

**Files:**
- Modify: `src/advisor_cli/core.py`
- Modify: `src/advisor_cli/cli.py`
- Modify: `src/advisor_cli/config.py`
- Modify: `src/advisor_cli/setup_wizard.py`

**Step 1: Update core.py docstrings**

Change Russian docstrings to English. Examples:

```python
# Before:
def format_error(e: Exception, include_prefix: bool = True) -> str:
    """Форматирует ошибку litellm с понятным сообщением."""

# After:
def format_error(e: Exception, include_prefix: bool = True) -> str:
    """Format litellm exception into user-friendly message."""
```

**Step 2: Update cli.py docstrings**

Keep typer help strings in Russian (user-facing), but change internal docstrings to English.

**Step 3: Update config.py and setup_wizard.py**

Same pattern - internal docstrings to English.

**Step 4: Run tests**

```bash
uv run pytest tests/ -v
```

**Step 5: Commit**

```bash
git add src/advisor_cli/
git commit -m "docs: standardize docstrings to English"
```

---

## Task 4: Add Return Type Hints to CLI Commands

**Files:**
- Modify: `src/advisor_cli/cli.py`

**Step 1: Add -> None to all CLI commands**

```python
# Before:
@app.command()
def ask(query: str = ...):

# After:
@app.command()
def ask(query: str = ...) -> None:
```

Apply to all functions:
- ask, compare, result, run, setup, status, models_cmd
- config_show, config_single, config_compare, config_format, config_purge
- uninstall, mcp_install, mcp_uninstall, mcp_status

**Step 2: Add types to helper functions**

```python
def create_async_task(...) -> None:
def get_async_result(...) -> dict | None:
def cleanup_old_tasks(...) -> None:
def print_output(...) -> None:
```

**Step 3: Run type checker (optional)**

```bash
uv run mypy src/advisor_cli/cli.py --ignore-missing-imports
```

**Step 4: Commit**

```bash
git add src/advisor_cli/cli.py
git commit -m "refactor: add return type hints to CLI commands"
```

---

## Task 5: Fix Bare Exception Handlers

**Files:**
- Modify: `src/advisor_cli/setup_wizard.py`
- Modify: `src/advisor_cli/core.py`

**Step 1: Fix setup_wizard.py bare except**

```python
# Before (line ~281):
except Exception:
    pass

# After:
except (FileNotFoundError, json.JSONDecodeError, IOError):
    pass
```

**Step 2: Fix core.py reasoning cache exception**

```python
# Before (line ~281-283):
except Exception:
    pass

# After:
except (json.JSONDecodeError, IOError, FileNotFoundError):
    pass
```

**Step 3: Add specific exception handling where needed**

Review other `except Exception` blocks and make them specific.

**Step 4: Run tests**

```bash
uv run pytest tests/ -v
```

**Step 5: Commit**

```bash
git add src/advisor_cli/setup_wizard.py src/advisor_cli/core.py
git commit -m "fix: replace bare except handlers with specific exceptions"
```

---

## Task 6: Refactor asyncio.run() Calls

**Files:**
- Modify: `src/advisor_cli/cli.py`
- Modify: `src/advisor_cli/setup_wizard.py`

**Step 1: Create async runner helper in cli.py**

```python
def _run_async(coro):
    """Run async coroutine, handling event loop properly."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already in async context
        import nest_asyncio
        nest_asyncio.apply()
        return asyncio.run(coro)
    else:
        return asyncio.run(coro)
```

**Note:** This is optional improvement. If nest_asyncio is not available, simpler approach:

```python
def _run_async(coro):
    """Run async coroutine."""
    return asyncio.run(coro)
```

The key is centralizing the pattern for future improvements.

**Step 2: Replace asyncio.run() calls in cli.py**

```python
# Before:
result = asyncio.run(consult_expert(params))

# After:
result = _run_async(consult_expert(params))
```

**Step 3: Same pattern in setup_wizard.py**

Import and use the helper.

**Step 4: Run tests**

```bash
uv run pytest tests/ -v
```

**Step 5: Commit**

```bash
git add src/advisor_cli/cli.py src/advisor_cli/setup_wizard.py
git commit -m "refactor: centralize asyncio.run() calls into _run_async helper"
```

---

## Final Verification

**Step 1: Run all tests**

```bash
uv run pytest tests/ -v
```

**Step 2: Type check**

```bash
uv run mypy src/advisor_cli/ --ignore-missing-imports || true
```

**Step 3: Manual smoke test**

```bash
uv run advisor status
uv run advisor models
echo "test" | uv run advisor ask "what is this?"
```

**Step 4: Review changes**

```bash
git log --oneline -10
git diff --stat HEAD~6
```

---

## Summary

| Task | Description | Effort |
|------|-------------|--------|
| 1 | Add tests for helpers | MEDIUM |
| 2 | Consolidate PROVIDER_INFO | MEDIUM |
| 3 | Standardize docstrings | SMALL |
| 4 | Add return type hints | SMALL |
| 5 | Fix bare exceptions | SMALL |
| 6 | Centralize asyncio.run | SMALL |

**Total:** 6 tasks, ~6 commits
