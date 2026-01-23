"""Unified install/uninstall commands for advisor CLI.

This module provides installation management:
- install: Unified install (MCP + Skill) for Claude Code
- uninstall: Remove all data (config + cache)

These commands handle the complete advisor-cli installation lifecycle.
"""

from typing import Optional

import typer

from .cli_output import print_output

install_app = typer.Typer()


@install_app.command("install")
def install(
    scope: Optional[str] = typer.Option(
        None, "--scope", "-s", help="Scope: project or user"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing"),
    yes: bool = typer.Option(False, "-y", help="Non-interactive mode"),
) -> None:
    """Install MCP integration and Skill for Claude Code."""
    from .mcp_manager import Scope as McpScope
    from .mcp_manager import has_project_mcp_config, install_to_claude_code
    from .skill_manager import Scope as SkillScope
    from .skill_manager import install_skill

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
        print_output("No configured providers.")
        if yes:
            print_output("Run: advisor setup", error=True)
            raise typer.Exit(1)
        try:
            import questionary

            run_setup_q = questionary.confirm("Run setup?", default=True).ask()
            if run_setup_q:
                from .setup_wizard import run_setup

                run_setup()
            else:
                raise typer.Exit(1)
        except ImportError:
            print_output("Run: advisor setup", error=True)
            raise typer.Exit(1)

    # Determine scope
    if scope:
        mcp_scope = McpScope.PROJECT if scope == "project" else McpScope.USER
        skill_scope = SkillScope.PROJECT if scope == "project" else SkillScope.USER
    elif has_project_mcp_config():
        mcp_scope = McpScope.PROJECT
        skill_scope = SkillScope.PROJECT
        if not yes:
            print_output("Found .mcp.json in current project.")
    elif yes:
        mcp_scope = McpScope.USER
        skill_scope = SkillScope.USER
    else:
        try:
            import questionary

            choice = questionary.select(
                "Where to install?",
                choices=[
                    questionary.Choice("Project (this project only)", value="project"),
                    questionary.Choice("Global (all projects)", value="user"),
                ],
            ).ask()
            mcp_scope = McpScope.PROJECT if choice == "project" else McpScope.USER
            skill_scope = SkillScope.PROJECT if choice == "project" else SkillScope.USER
        except ImportError:
            mcp_scope = McpScope.USER
            skill_scope = SkillScope.USER

    loc = "project" if mcp_scope == McpScope.PROJECT else "user"
    print_output(f"\nInstalling to {loc}...\n")

    # Install MCP
    if install_to_claude_code(mcp_scope):
        mcp_path = ".mcp.json" if mcp_scope == McpScope.PROJECT else "~/.claude.json"
        print_output(f"MCP installed: {mcp_path}")
    else:
        print_output("MCP not installed", error=True)

    # Install Skill
    success, message = install_skill(scope=skill_scope, force=force)
    if success:
        print_output(f"Skill installed: {message}")
    else:
        if "already installed" in message and not force:
            print_output("  Skill already installed (use --force to update)")
        else:
            print_output(f"Skill: {message}", error=True)

    print_output("\nRestart Claude to apply changes.")


@install_app.command("uninstall")
def uninstall(
    force: bool = typer.Option(False, "--force", "-f", help="Without confirmation"),
) -> None:
    """Remove all advisor-cli data (config + cache)."""
    from .config import CACHE_DIR, CONFIG_DIR, CONFIG_FILE, purge_all

    print_output("\n=== Advisor CLI Uninstall ===\n")
    print_output("Will be removed:")

    if CONFIG_FILE.exists():
        print_output(f"  - {CONFIG_FILE} (API keys)")
    if CACHE_DIR.exists():
        print_output(f"  - {CACHE_DIR}/ (response cache)")
    if CONFIG_DIR.exists():
        print_output(f"  - {CONFIG_DIR}/ (config directory)")

    print_output("\nTo remove the package itself run:")
    print_output("  uv tool uninstall advisor-cli")
    print_output("  # or: pip uninstall advisor-cli")

    if not force:
        try:
            import questionary

            confirm = questionary.confirm(
                "\nRemove all data?",
                default=False,
            ).ask()
            if not confirm:
                print_output("Cancelled.")
                return
        except ImportError:
            print_output("\nUse --force to confirm", error=True)
            raise typer.Exit(1)

    config_removed, cache_removed = purge_all()

    print_output("")
    if config_removed:
        print_output("Config removed")
    if cache_removed:
        print_output("Cache removed")

    if not config_removed and not cache_removed:
        print_output("Nothing to remove.")
    else:
        print_output("\nAdvisor-cli data removed.")
