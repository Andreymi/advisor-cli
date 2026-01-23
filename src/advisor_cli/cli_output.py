"""Output utilities for advisor CLI.

This module provides output formatting and printing functions:
- print_output: Simple output to stdout/stderr with newline
- _parse_format: Parse format string to ResponseFormat enum (private)

These utilities are used throughout the CLI for consistent output handling.
"""

import sys

import typer

from .core import ResponseFormat


def print_output(text: str, error: bool = False) -> None:
    """Print text to stdout or stderr with trailing newline.

    Args:
        text: The text to print
        error: If True, write to stderr instead of stdout
    """
    if error:
        sys.stderr.write(text + "\n")
    else:
        sys.stdout.write(text + "\n")


def _parse_format(format: str | None) -> ResponseFormat:
    """Parse format string to ResponseFormat enum.

    Handles case-insensitive format parsing with sensible defaults.

    Args:
        format: Format string ('json' or 'markdown'), or None for default

    Returns:
        ResponseFormat.JSON or ResponseFormat.MARKDOWN

    Raises:
        typer.Exit: If format string is not recognized (exit code 1)
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
