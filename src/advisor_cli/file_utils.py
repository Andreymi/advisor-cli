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

# Maximum file size for context input (100KB)
# Prevents accidental processing of large binary files or logs
MAX_FILE_SIZE_BYTES = 100 * 1024


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
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"Файл слишком большой ({file_size // 1024}KB > {MAX_FILE_SIZE_BYTES // 1024}KB)"
        )

    return path.read_text(encoding="utf-8")


def get_allowed_extensions_str() -> str:
    """Возвращает строку с поддерживаемыми расширениями."""
    return ", ".join(sorted(ALLOWED_EXTENSIONS))


def read_stdin() -> str | None:
    """Читает stdin если есть данные.

    Returns:
        Содержимое stdin или None если stdin пуст или это терминал
    """
    import sys

    if not sys.stdin.isatty():
        return sys.stdin.read()
    return None


def build_context(
    context: str | None = None,
    file: Path | None = None,
) -> str:
    """Собирает контекст из inline, stdin и файла.

    Args:
        context: Inline context string
        file: Path to context file

    Returns:
        Combined context string

    Raises:
        ValueError: If file not found or too large
        FileNotFoundError: If file doesn't exist
    """
    final_context = context or ""

    # Из stdin
    stdin_data = read_stdin()
    if stdin_data:
        final_context = (
            stdin_data if not final_context else f"{final_context}\n\n{stdin_data}"
        )

    # Из файла
    if file:
        file_content = read_context_file(file)
        final_context = (
            file_content if not final_context else f"{final_context}\n\n{file_content}"
        )

    return final_context
