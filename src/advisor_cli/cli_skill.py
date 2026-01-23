"""Skill management commands for advisor CLI.

This module provides commands for managing Claude Code skill integration:
- skill_install: Install advisor skill to Claude Code
- skill_uninstall: Remove advisor skill from Claude Code
- skill_status: Show current skill installation status

The skill_app Typer application is intended to be mounted as a subcommand
group in the main CLI application.
"""

from typing import Optional

import typer

from .cli_output import print_output
from .skill_manager import (
    Scope,
    get_skill_status,
    has_project_skill,
    install_skill,
    uninstall_skill,
)

skill_app = typer.Typer(help="Управление Claude Code skill")


@skill_app.command("install")
def skill_install(
    scope: Optional[str] = typer.Option(
        None, "--scope", "-s", help="Scope: project или user"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Перезаписать существующий"
    ),
) -> None:
    """Установить advisor skill для Claude Code."""
    # Determine scope
    if scope:
        scope_enum = Scope.PROJECT if scope == "project" else Scope.USER
    elif has_project_skill():
        scope_enum = Scope.PROJECT
    else:
        scope_enum = Scope.USER

    success, message = install_skill(scope=scope_enum, force=force)

    if not success:
        print_output(f"Ошибка: {message}", error=True)
        if "already installed" not in message:
            raise typer.Exit(1)
        return

    loc = "project (.claude/)" if scope_enum == Scope.PROJECT else "user (~/.claude/)"
    print_output(f"Skill установлен ({loc}): {message}")
    print_output("\nИспользование в Claude Code:")
    print_output("  /advisor <query>")


@skill_app.command("uninstall")
def skill_uninstall(
    scope: Optional[str] = typer.Option(
        None, "--scope", "-s", help="Scope: project или user"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Без подтверждения"),
) -> None:
    """Удалить advisor skill из Claude Code."""
    # Determine scope
    if scope:
        scope_enum = Scope.PROJECT if scope == "project" else Scope.USER
        status = get_skill_status(scope_enum)
    else:
        status = get_skill_status()
        scope_enum = status.scope or Scope.USER

    if not status.is_installed:
        print_output("Skill не установлен.")
        return

    if not force:
        try:
            import questionary

            confirm = questionary.confirm(
                f"Удалить {status.installed_path}?",
                default=False,
            ).ask()
            if not confirm:
                print_output("Отменено.")
                return
        except ImportError:
            print_output("Используйте --force для подтверждения", error=True)
            raise typer.Exit(1)

    success, message = uninstall_skill(scope_enum)
    if success:
        print_output(f"{message}")
    else:
        print_output(message, error=True)


@skill_app.command("status")
def skill_status_cmd() -> None:
    """Показать статус установки skill."""
    print_output("\nAdvisor Skill Status\n")

    # Package
    status = get_skill_status()
    if status.package_path:
        print_output(f"  Package: {status.package_path}")
    else:
        print_output("  Package: не найден (переустановите advisor-cli)")

    # Check both scopes
    project_status = get_skill_status(Scope.PROJECT)
    user_status = get_skill_status(Scope.USER)

    print_output("")
    # Project
    if project_status.is_installed:
        mark = "outdated" if project_status.is_outdated else "installed"
        print_output(f"  Project: {mark} {project_status.installed_path}")
    else:
        print_output("  Project: не установлен")

    # User
    if user_status.is_installed:
        mark = "outdated" if user_status.is_outdated else "installed"
        print_output(f"  User:    {mark} {user_status.installed_path}")
    else:
        print_output("  User:    не установлен")

    if not project_status.is_installed and not user_status.is_installed:
        print_output("\n  Установите: advisor install")
    elif project_status.is_outdated or user_status.is_outdated:
        print_output("\n  Обновите: advisor skill install --force")

    print_output("")
