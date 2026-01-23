"""Utility functions for advisor-cli."""

import functools
from typing import Callable, TypeVar

import typer
from rich.console import Console

T = TypeVar("T")


def require_wizard(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator that ensures wizard module is available.

    Catches ImportError raised by the decorated function and prints
    a user-friendly message before exiting.

    Usage:
        @app.command()
        @require_wizard
        def my_command():
            from .setup_wizard import run_setup
            run_setup()
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except ImportError:
            console = Console()
            console.print(
                "[red]Wizard not installed.[/red]\n"
                "[dim]Install with: pip install advisor-cli[wizard][/dim]"
            )
            raise typer.Exit(1)

    return wrapper
