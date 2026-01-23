#!/usr/bin/env python3
"""Centralized configuration path management for advisor-cli.

Follows XDG Base Directory Specification:
- ~/.config/advisor/config.env — configuration and API keys
- ~/.cache/advisor/ — LLM response cache
"""

import os
import shutil
from pathlib import Path
from typing import Any

# ===== XDG-совместимые пути =====


def get_config_dir() -> Path:
    """Return configuration directory (XDG_CONFIG_HOME/advisor)."""
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    base = Path(xdg) if xdg else Path.home() / ".config"
    config_dir = base / "advisor"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_cache_dir() -> Path:
    """Return cache directory (XDG_CACHE_HOME/advisor)."""
    xdg = os.environ.get("XDG_CACHE_HOME", "")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    cache_dir = base / "advisor"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


# ===== Основные константы =====
CONFIG_DIR = get_config_dir()
CONFIG_FILE = CONFIG_DIR / "config.env"
CACHE_DIR = get_cache_dir()

# Легаси путь (для миграции)
_LEGACY_PROJECT_ROOT = Path(__file__).parent.parent.parent
_LEGACY_ENV_FILE = _LEGACY_PROJECT_ROOT / ".env"
_LEGACY_CACHE_DIR = _LEGACY_PROJECT_ROOT / ".mcp_cache"


# ===== Миграция =====


def get_legacy_env_path() -> Path | None:
    """Return path to legacy .env file if it exists."""
    if _LEGACY_ENV_FILE.exists():
        return _LEGACY_ENV_FILE
    return None


def migrate_legacy_config(interactive: bool = True) -> bool:
    """Migrate configuration from legacy location to XDG.

    Args:
        interactive: If True, prompts user for confirmation.

    Returns:
        True if migration was performed, False otherwise.
    """
    legacy_path = get_legacy_env_path()

    if not legacy_path:
        return False

    if CONFIG_FILE.exists():
        # Новый конфиг уже существует, не перезаписываем
        return False

    if interactive:
        try:
            import questionary

            migrate = questionary.confirm(
                f"Найден старый конфиг в {legacy_path}.\nМигрировать в {CONFIG_FILE}?",
                default=True,
            ).ask()

            if not migrate:
                return False
        except ImportError:
            # Без questionary мигрируем автоматически
            pass

    # Копируем файл
    shutil.copy2(legacy_path, CONFIG_FILE)

    # Мигрируем кэш если есть
    if _LEGACY_CACHE_DIR.exists() and not CACHE_DIR.exists():
        shutil.copytree(_LEGACY_CACHE_DIR, CACHE_DIR)

    return True


def load_config() -> dict[str, str]:
    """Load configuration from config.env file.

    Automatically checks for legacy configuration
    and offers migration.
    """
    # Пытаемся мигрировать legacy конфиг
    migrate_legacy_config(interactive=False)

    env_vars: dict[str, str] = {}

    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip().strip('"').strip("'")

    return env_vars


def save_config(env_vars: dict[str, str]) -> None:
    """Save configuration to config.env file."""
    lines = [
        "# Advisor CLI Configuration",
        f"# Config location: {CONFIG_FILE}",
        "",
    ]

    # Группируем переменные
    for key, value in sorted(env_vars.items()):
        if value:
            lines.append(f"{key}={value}")

    CONFIG_FILE.write_text("\n".join(lines) + "\n")


def mask_api_key(key: str) -> str:
    """Mask API key for safe display."""
    if not key or len(key) < 8:
        return "***"
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def update_config(key: str, value: str) -> None:
    """Update single value in configuration.

    Args:
        key: Environment variable name (e.g., "ADVISOR_DEFAULT_MODEL")
        value: New value
    """
    env = load_config()
    env[key] = value
    save_config(env)


def purge_config() -> bool:
    """Delete configuration file (secrets).

    Returns:
        True if file was deleted.
    """
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        return True
    return False


def purge_cache() -> bool:
    """Delete cache directory.

    Returns:
        True if directory was deleted.
    """
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        return True
    return False


def purge_all() -> tuple[bool, bool]:
    """Delete all configuration and cache.

    Returns:
        Tuple (config_removed, cache_removed).
    """
    config_removed = purge_config()
    cache_removed = purge_cache()

    # Удаляем пустую директорию конфигурации
    if CONFIG_DIR.exists() and not any(CONFIG_DIR.iterdir()):
        CONFIG_DIR.rmdir()

    return config_removed, cache_removed


# ===== Provider Configuration =====
# Single source of truth for provider information

PROVIDER_INFO: dict[str, dict[str, Any]] = {
    "gemini": {
        "name": "Google Gemini",
        "env_key": "GEMINI_API_KEY",
        "url": "https://aistudio.google.com/apikey",
        "test_model": "gemini/gemini-2.0-flash",
        "models": ["gemini/gemini-2.0-flash", "gemini/gemini-2.5-pro-preview-06-05"],
    },
    "openai": {
        "name": "OpenAI",
        "env_key": "OPENAI_API_KEY",
        "url": "https://platform.openai.com/api-keys",
        "test_model": "openai/gpt-4o-mini",
        "models": ["openai/gpt-4o-mini", "openai/gpt-4o", "openai/o1-mini"],
    },
    "anthropic": {
        "name": "Anthropic",
        "env_key": "ANTHROPIC_API_KEY",
        "url": "https://console.anthropic.com/settings/keys",
        "test_model": "anthropic/claude-3-5-haiku-20241022",
        "models": [
            "anthropic/claude-3-5-haiku-20241022",
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
        "models": ["groq/llama-3.3-70b-versatile", "groq/mixtral-8x7b-32768"],
    },
    "openrouter": {
        "name": "OpenRouter",
        "env_key": "OPENROUTER_API_KEY",
        "url": "https://openrouter.ai/keys",
        "test_model": "openrouter/google/gemini-2.0-flash-001",
        "models": [
            "openrouter/google/gemini-2.0-flash-001",
            "openrouter/anthropic/claude-3.5-sonnet",
        ],
    },
    "ollama": {
        "name": "Ollama (локальный)",
        "env_key": "OLLAMA_HOST",
        "url": "https://ollama.ai/download",
        "test_model": "ollama/llama3.2",
        "models": ["ollama/llama3.2", "ollama/mistral"],
        "default_value": "http://localhost:11434",
    },
    "ollama-cloud": {
        "name": "Ollama Cloud",
        "env_key": "OLLAMA_API_KEY",
        "url": "https://ollama.com",
        "test_model": "ollama-cloud/gpt-oss:120b-cloud",
        "models": ["ollama-cloud/gpt-oss:120b-cloud"],
        "base_url_env": "OLLAMA_CLOUD_BASE_URL",
    },
}


def get_provider_env_key(provider_id: str) -> str | None:
    """Get environment variable key for provider."""
    info = PROVIDER_INFO.get(provider_id)
    return info["env_key"] if info else None


def get_enabled_providers() -> list[str]:
    """Get list of providers with configured API keys."""
    enabled = []
    for pid, info in PROVIDER_INFO.items():
        env_key = info.get("env_key")
        if env_key is None:
            enabled.append(pid)
        elif os.getenv(env_key):
            enabled.append(pid)
    return enabled
