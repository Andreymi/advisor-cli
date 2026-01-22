#!/usr/bin/env python3
"""File utilities for advisor-cli."""

from pathlib import Path

# Поддерживаемые расширения файлов
ALLOWED_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
    ".html",
    ".css",
    ".scss",
    ".sql",
    ".sh",
    ".bash",
    ".zsh",
}

# Максимальный размер файла (100KB)
MAX_FILE_SIZE = 100 * 1024


def read_context_file(path: Path) -> str:
    """
    Читает файл с проверками безопасности.

    Args:
        path: Путь к файлу

    Returns:
        Содержимое файла

    Raises:
        ValueError: Если файл не поддерживается или слишком большой
        FileNotFoundError: Если файл не найден
    """
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")

    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Неподдерживаемый тип файла: {path.suffix}")

    file_size = path.stat().st_size
    if file_size > MAX_FILE_SIZE:
        raise ValueError(
            f"Файл слишком большой ({file_size // 1024}KB > {MAX_FILE_SIZE // 1024}KB)"
        )

    return path.read_text(encoding="utf-8")


def get_allowed_extensions_str() -> str:
    """Возвращает строку с поддерживаемыми расширениями."""
    return ", ".join(sorted(ALLOWED_EXTENSIONS))
