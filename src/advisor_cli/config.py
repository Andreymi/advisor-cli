#!/usr/bin/env python3
"""Централизованное управление путями конфигурации advisor-cli.

Следует XDG Base Directory Specification:
- ~/.config/advisor/config.env — конфигурация и API ключи
- ~/.cache/advisor/ — кэш ответов LLM
"""

import os
import shutil
from pathlib import Path

# ===== XDG-совместимые пути =====


def get_config_dir() -> Path:
    """Возвращает директорию конфигурации (XDG_CONFIG_HOME/advisor)."""
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    base = Path(xdg) if xdg else Path.home() / ".config"
    config_dir = base / "advisor"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_cache_dir() -> Path:
    """Возвращает директорию кэша (XDG_CACHE_HOME/advisor)."""
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
    """Возвращает путь к старому .env файлу, если он существует."""
    if _LEGACY_ENV_FILE.exists():
        return _LEGACY_ENV_FILE
    return None


def migrate_legacy_config(interactive: bool = True) -> bool:
    """Мигрирует конфигурацию из старого расположения в XDG.

    Args:
        interactive: Если True, запрашивает подтверждение у пользователя.

    Returns:
        True если миграция выполнена, False если нет.
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
    """Загружает конфигурацию из config.env файла.

    Автоматически проверяет наличие legacy конфигурации
    и предлагает миграцию.
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
    """Сохраняет конфигурацию в config.env файл."""
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
    """Маскирует API ключ для безопасного отображения."""
    if not key or len(key) < 8:
        return "***"
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def purge_config() -> bool:
    """Удаляет файл конфигурации (секреты).

    Returns:
        True если файл был удалён.
    """
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        return True
    return False


def purge_cache() -> bool:
    """Удаляет директорию кэша.

    Returns:
        True если директория была удалена.
    """
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        return True
    return False


def purge_all() -> tuple[bool, bool]:
    """Удаляет всю конфигурацию и кэш.

    Returns:
        Tuple (config_removed, cache_removed).
    """
    config_removed = purge_config()
    cache_removed = purge_cache()

    # Удаляем пустую директорию конфигурации
    if CONFIG_DIR.exists() and not any(CONFIG_DIR.iterdir()):
        CONFIG_DIR.rmdir()

    return config_removed, cache_removed
