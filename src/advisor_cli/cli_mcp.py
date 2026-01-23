"""MCP integration commands for advisor CLI.

This module provides MCP (Model Context Protocol) management commands:
- install: Install MCP integration for Claude Code/Desktop
- uninstall: Remove MCP integration
- status: Show MCP integration status

These commands manage the advisor MCP server configuration.
"""

from typing import Optional

import typer

from .cli_output import print_output

mcp_app = typer.Typer(help="Управление MCP интеграцией")


@mcp_app.command("install")
def mcp_install(
    scope: Optional[str] = typer.Option(
        None, "--scope", "-s", help="Scope: project или user"
    ),
    target: str = typer.Option(
        "all", "--target", "-t", help="Target: claude-code, desktop или all"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Перезаписать без вопросов"
    ),
    yes: bool = typer.Option(False, "-y", help="Неинтерактивный режим"),
) -> None:
    """Установить MCP интеграцию для Claude."""
    from .mcp_manager import (
        ConflictType,
        Scope,
        Target,
        check_conflicts,
        has_project_mcp_config,
        install_to_claude_code,
        install_to_desktop,
    )

    # Check if providers configured
    try:
        from .config import load_config

        env = load_config()
    except ImportError:
        env = {}

    has_providers = any(
        env.get(key)
        for key in [
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "DEEPSEEK_API_KEY",
            "GROQ_API_KEY",
            "OPENROUTER_API_KEY",
        ]
    )

    if not has_providers:
        if yes:
            print_output(
                "Ошибка: Нет настроенных провайдеров. Установите API ключи.", error=True
            )
            raise typer.Exit(1)
        else:
            print_output("Нет настроенных провайдеров.")
            try:
                import questionary

                run_setup_q = questionary.confirm(
                    "Запустить настройку?", default=True
                ).ask()
                if run_setup_q:
                    from .setup_wizard import run_setup

                    run_setup()
                else:
                    raise typer.Exit(1)
            except ImportError:
                print_output("Запустите: advisor setup", error=True)
                raise typer.Exit(1)

    # Determine scope
    scope_enum: Scope
    if scope:
        scope_enum = Scope.PROJECT if scope == "project" else Scope.USER
    elif has_project_mcp_config():
        scope_enum = Scope.PROJECT
        if not yes:
            print_output("Обнаружен .mcp.json в текущем проекте.")
    elif yes:
        scope_enum = Scope.USER
    else:
        try:
            import questionary

            choice = questionary.select(
                "Куда установить advisor?",
                choices=[
                    questionary.Choice("В проект (.mcp.json)", value="project"),
                    questionary.Choice(
                        "Глобально (Claude Code + Claude Desktop)", value="user"
                    ),
                ],
            ).ask()
            scope_enum = Scope.PROJECT if choice == "project" else Scope.USER
        except ImportError:
            scope_enum = Scope.USER

    # Parse target
    target_enum = Target.ALL
    if target == "claude-code":
        target_enum = Target.CLAUDE_CODE
    elif target == "desktop":
        target_enum = Target.DESKTOP

    # Check conflicts
    conflicts = check_conflicts(scope_enum, target_enum)

    for conflict in conflicts:
        if conflict.type == ConflictType.OVERRIDE:
            print_output(f"⚠ {conflict.location}: {conflict.message}")
        elif conflict.type == ConflictType.OUTDATED:
            print_output(f"⚠ {conflict.location}: {conflict.message}")
            if not force and not yes:
                try:
                    import questionary

                    update = questionary.confirm("Обновить?", default=True).ask()
                    if not update:
                        continue
                except ImportError:
                    pass
        elif conflict.type == ConflictType.DUPLICATE:
            if not force:
                print_output(f"✓ {conflict.location}: {conflict.message}")
                continue
        elif conflict.type == ConflictType.NAME_COLLISION:
            print_output(f"✗ {conflict.location}: {conflict.message}", error=True)
            if not force:
                raise typer.Exit(1)

    # Install
    installed = []

    if target_enum in (Target.ALL, Target.CLAUDE_CODE):
        if install_to_claude_code(scope_enum):
            loc = ".mcp.json" if scope_enum == Scope.PROJECT else "~/.claude.json"
            installed.append(loc)

    if target_enum in (Target.ALL, Target.DESKTOP):
        if install_to_desktop():
            installed.append("Claude Desktop")

    if installed:
        for loc in installed:
            print_output(f"✓ Установлено в {loc}")
        print_output("\nПерезапустите Claude для применения изменений.")
    else:
        print_output("Ничего не установлено.", error=True)


@mcp_app.command("uninstall")
def mcp_uninstall(
    scope: Optional[str] = typer.Option(
        None, "--scope", "-s", help="Scope: project или user"
    ),
    all_scopes: bool = typer.Option(False, "--all", "-a", help="Удалить отовсюду"),
    yes: bool = typer.Option(False, "-y", help="Неинтерактивный режим"),
) -> None:
    """Удалить MCP интеграцию из Claude."""
    from .mcp_manager import (
        Scope,
        get_installation_status,
        uninstall_from_claude_code,
        uninstall_from_desktop,
    )

    removed = []

    if all_scopes:
        if uninstall_from_claude_code(Scope.PROJECT):
            removed.append(".mcp.json")
        if uninstall_from_claude_code(Scope.USER):
            removed.append("~/.claude.json")
        if uninstall_from_desktop():
            removed.append("Claude Desktop")
    elif scope:
        scope_enum = Scope.PROJECT if scope == "project" else Scope.USER
        if uninstall_from_claude_code(scope_enum):
            loc = ".mcp.json" if scope_enum == Scope.PROJECT else "~/.claude.json"
            removed.append(loc)
    else:
        # Interactive mode
        status = get_installation_status()
        locations: list[tuple[str, Scope | None]] = []

        if status.get("claude_code_project", {}).get("installed"):
            locations.append((".mcp.json", Scope.PROJECT))
        if status.get("claude_code_user", {}).get("installed"):
            locations.append(("~/.claude.json", Scope.USER))
        if status.get("claude_desktop", {}).get("installed"):
            locations.append(("Claude Desktop", None))

        if not locations:
            print_output("advisor_mcp не установлен нигде.")
            return

        if yes:
            # Remove from all found locations
            for loc, scope_val in locations:
                if scope_val:
                    if uninstall_from_claude_code(scope_val):
                        removed.append(loc)
                else:
                    if uninstall_from_desktop():
                        removed.append(loc)
        else:
            try:
                import questionary

                choices = [
                    questionary.Choice(loc, value=(loc, scope_val))
                    for loc, scope_val in locations
                ]
                selected = questionary.checkbox(
                    "Откуда удалить advisor_mcp?",
                    choices=choices,
                ).ask()

                for loc, scope_val in selected or []:
                    if scope_val:
                        if uninstall_from_claude_code(scope_val):
                            removed.append(loc)
                    else:
                        if uninstall_from_desktop():
                            removed.append(loc)
            except ImportError:
                print_output("Укажите --scope или --all", error=True)
                raise typer.Exit(1)

    if removed:
        for loc in removed:
            print_output(f"✓ Удалено из {loc}")
        print_output("\nПерезапустите Claude для применения изменений.")
    else:
        print_output("Ничего не удалено.")


@mcp_app.command("status")
def mcp_status() -> None:
    """Показать статус MCP интеграции."""
    from .mcp_manager import get_installation_status

    status = get_installation_status()

    print_output("\nMCP Integration Status\n")

    labels = {
        "claude_code_user": "Claude Code (user)",
        "claude_code_project": "Claude Code (project)",
        "claude_desktop": "Claude Desktop",
    }

    any_installed = False

    for key, label in labels.items():
        info = status.get(key, {})
        if info.get("installed"):
            any_installed = True
            if info.get("outdated"):
                print_output(f"  {label}: ⚠ установлен (устаревшая версия)")
            else:
                print_output(f"  {label}: ✓ установлен")
        else:
            print_output(f"  {label}: ✗ не установлен")

    if not any_installed:
        print_output("\nЗапустите: advisor mcp install")
    elif any(s.get("outdated") for s in status.values()):
        print_output("\nДля обновления: advisor mcp install --force")

    print_output("")
