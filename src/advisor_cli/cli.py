#!/usr/bin/env python3
"""CLI entry point for advisor-cli.

This module serves as the minimal entry point that:
- Creates the main Typer application
- Registers sub-apps (config, mcp, skill)
- Registers core commands on the main app
- Keeps setup and run commands (special requirements)

All command implementations live in dedicated modules:
- cli_core.py: ask, compare, result, status, models
- cli_config.py: config subcommands
- cli_mcp.py: mcp subcommands
- cli_skill.py: skill subcommands
- cli_install.py: install, uninstall
"""

import warnings
from typing import Optional

import typer


# Suppress warnings from litellm/pydantic before importing
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", message="coroutine .* was never awaited")

from . import __version__  # noqa: E402
from .cli_config import config_app  # noqa: E402
from .cli_core import core_app  # noqa: E402
from .cli_install import install_app  # noqa: E402
from .cli_mcp import mcp_app  # noqa: E402
from .cli_output import print_output  # noqa: E402
from .cli_skill import skill_app  # noqa: E402
from .utils import require_wizard  # noqa: E402


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        print(f"advisor-cli {__version__}")
        raise typer.Exit()


# Main application
app = typer.Typer(
    name="advisor",
    help="CLI for getting second opinions from alternative LLMs",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.callback()
def main(
    _version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """Advisor CLI - get second opinions from alternative LLMs."""


# Register sub-apps
app.add_typer(config_app, name="config")
app.add_typer(mcp_app, name="mcp")
app.add_typer(skill_app, name="skill")

# Register core commands on main app
for cmd in core_app.registered_commands:
    app.registered_commands.append(cmd)

# Register install commands on main app
for cmd in install_app.registered_commands:
    app.registered_commands.append(cmd)


@app.command()
def run() -> None:
    """Run MCP server (requires [mcp] installation)."""
    try:
        from .server import main as run_server

        run_server()
    except ImportError:
        print_output(
            "MCP not installed. Install with: pip install advisor-cli[mcp]", error=True
        )
        raise typer.Exit(1)


@app.command()
@require_wizard
def setup(
    yes: bool = typer.Option(False, "-y", help="Non-interactive mode (use env vars)"),
    providers: Optional[str] = typer.Option(
        None, "-p", "--providers", help="Providers comma-separated"
    ),
    model: Optional[str] = typer.Option(None, "-m", "--model", help="Default model"),
) -> None:
    """Interactive configuration setup (requires [wizard] installation)."""
    from .setup_wizard import run_setup

    provider_list = None
    if providers:
        provider_list = [p.strip() for p in providers.split(",")]

    run_setup(
        non_interactive=yes,
        providers=provider_list,
        model=model,
    )


if __name__ == "__main__":
    app()
