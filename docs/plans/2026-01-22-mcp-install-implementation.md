# MCP Install & Distribution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `advisor mcp install/uninstall/status` commands, non-interactive setup mode, and prepare for PyPI distribution.

**Architecture:** New `mcp_manager.py` module handles all MCP config operations. Setup wizard gets `-y` flag for non-interactive mode. CLI gets `mcp` command group.

**Tech Stack:** Python, typer, questionary, pathlib, json

---

## Task 1: Create mcp_manager.py — Config Paths & Detection

**Files:**
- Create: `src/advisor_cli/mcp_manager.py`

**Step 1: Create file with config paths and detection functions**

```python
#!/usr/bin/env python3
"""MCP configuration manager for advisor-cli."""

import json
import platform
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class Scope(Enum):
    PROJECT = "project"
    USER = "user"


class Target(Enum):
    CLAUDE_CODE = "claude-code"
    DESKTOP = "desktop"
    ALL = "all"


class ConflictType(Enum):
    DUPLICATE = "duplicate"
    OVERRIDE = "override"
    NAME_COLLISION = "name_collision"
    OUTDATED = "outdated"


@dataclass
class Conflict:
    type: ConflictType
    location: str
    message: str
    current_config: Optional[dict] = None


def get_config_paths() -> dict[str, Path]:
    """Get paths to all Claude configuration files."""
    home = Path.home()
    system = platform.system()

    paths = {
        "claude_code_user": home / ".claude.json",
        "claude_code_project": Path.cwd() / ".mcp.json",
    }

    if system == "Darwin":  # macOS
        paths["claude_desktop"] = home / "Library/Application Support/Claude/claude_desktop_config.json"
    elif system == "Linux":
        paths["claude_desktop"] = home / ".config/Claude/claude_desktop_config.json"
    elif system == "Windows":
        paths["claude_desktop"] = home / "AppData/Roaming/Claude/claude_desktop_config.json"

    return paths


def get_advisor_path() -> str:
    """Get absolute path to advisor executable."""
    path = shutil.which("advisor")
    return path or "advisor"


def get_advisor_config_for_claude_code() -> dict:
    """Get MCP config for Claude Code (uses PATH)."""
    return {
        "advisor_mcp": {
            "command": "advisor",
            "args": ["run"]
        }
    }


def get_advisor_config_for_desktop() -> dict:
    """Get MCP config for Claude Desktop (needs absolute path)."""
    return {
        "advisor_mcp": {
            "command": get_advisor_path(),
            "args": ["run"]
        }
    }


def has_project_mcp_config() -> bool:
    """Check if .mcp.json exists in current directory."""
    return (Path.cwd() / ".mcp.json").exists()
```

**Step 2: Commit**

```bash
git add src/advisor_cli/mcp_manager.py
git commit -m "feat(mcp): add config paths and detection"
```

---

## Task 2: Add Config Read/Write Functions

**Files:**
- Modify: `src/advisor_cli/mcp_manager.py`

**Step 1: Add read/write functions**

```python
def read_config(path: Path) -> dict:
    """Read JSON config file, return empty dict if not exists."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, IOError):
        return {}


def write_config(path: Path, config: dict) -> None:
    """Write JSON config file, creating parent dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")


def get_mcp_servers(config: dict) -> dict:
    """Extract mcpServers from config."""
    return config.get("mcpServers", {})


def set_mcp_server(config: dict, name: str, server_config: dict) -> dict:
    """Add or update MCP server in config."""
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    config["mcpServers"][name] = server_config
    return config


def remove_mcp_server(config: dict, name: str) -> dict:
    """Remove MCP server from config."""
    if "mcpServers" in config and name in config["mcpServers"]:
        del config["mcpServers"][name]
    return config
```

**Step 2: Commit**

```bash
git add src/advisor_cli/mcp_manager.py
git commit -m "feat(mcp): add config read/write functions"
```

---

## Task 3: Add Conflict Detection

**Files:**
- Modify: `src/advisor_cli/mcp_manager.py`

**Step 1: Add conflict detection function**

```python
def is_advisor_config(server_config: dict) -> bool:
    """Check if config looks like advisor_mcp."""
    cmd = server_config.get("command", "")
    args = server_config.get("args", [])

    # Check for advisor command
    if "advisor" in cmd:
        return True
    # Check for old mcp-advisor command
    if "mcp-advisor" in cmd or "mcp-advisor" in str(args):
        return True
    return False


def is_outdated_config(server_config: dict) -> bool:
    """Check if config uses old mcp-advisor command."""
    cmd = server_config.get("command", "")
    args = server_config.get("args", [])

    # Old style: uv run mcp-advisor or just mcp-advisor
    if "mcp-advisor" in cmd:
        return True
    if "mcp-advisor" in args:
        return True
    # Old style: uv run --directory ... mcp-advisor
    if len(args) >= 1 and args[-1] == "mcp-advisor":
        return True
    return False


def check_conflicts(scope: Scope, target: Target) -> list[Conflict]:
    """Check for conflicts before installation."""
    conflicts = []
    paths = get_config_paths()

    # Check Claude Code user config
    if target in (Target.ALL, Target.CLAUDE_CODE) and scope == Scope.USER:
        config = read_config(paths["claude_code_user"])
        servers = get_mcp_servers(config)

        if "advisor_mcp" in servers:
            server = servers["advisor_mcp"]
            if is_outdated_config(server):
                conflicts.append(Conflict(
                    type=ConflictType.OUTDATED,
                    location="~/.claude.json",
                    message="Устаревшая команда (mcp-advisor → advisor run)",
                    current_config=server,
                ))
            elif is_advisor_config(server):
                conflicts.append(Conflict(
                    type=ConflictType.DUPLICATE,
                    location="~/.claude.json",
                    message="advisor_mcp уже установлен",
                    current_config=server,
                ))
            else:
                conflicts.append(Conflict(
                    type=ConflictType.NAME_COLLISION,
                    location="~/.claude.json",
                    message="advisor_mcp указывает на другой сервер",
                    current_config=server,
                ))

    # Check Claude Code project config
    if target in (Target.ALL, Target.CLAUDE_CODE) and scope == Scope.PROJECT:
        config = read_config(paths["claude_code_project"])
        servers = get_mcp_servers(config)

        if "advisor_mcp" in servers:
            server = servers["advisor_mcp"]
            if is_outdated_config(server):
                conflicts.append(Conflict(
                    type=ConflictType.OUTDATED,
                    location=".mcp.json",
                    message="Устаревшая команда (mcp-advisor → advisor run)",
                    current_config=server,
                ))
            elif is_advisor_config(server):
                conflicts.append(Conflict(
                    type=ConflictType.DUPLICATE,
                    location=".mcp.json",
                    message="advisor_mcp уже установлен",
                    current_config=server,
                ))
            else:
                conflicts.append(Conflict(
                    type=ConflictType.NAME_COLLISION,
                    location=".mcp.json",
                    message="advisor_mcp указывает на другой сервер",
                    current_config=server,
                ))

        # Check if project overrides user
        user_config = read_config(paths["claude_code_user"])
        if "advisor_mcp" in get_mcp_servers(user_config):
            conflicts.append(Conflict(
                type=ConflictType.OVERRIDE,
                location=".mcp.json",
                message="Проектный конфиг перекроет глобальный (~/.claude.json)",
            ))

    # Check Claude Desktop
    if target in (Target.ALL, Target.DESKTOP):
        desktop_path = paths.get("claude_desktop")
        if desktop_path:
            config = read_config(desktop_path)
            servers = get_mcp_servers(config)

            if "advisor_mcp" in servers:
                server = servers["advisor_mcp"]
                if is_outdated_config(server):
                    conflicts.append(Conflict(
                        type=ConflictType.OUTDATED,
                        location="Claude Desktop",
                        message="Устаревшая команда (mcp-advisor → advisor run)",
                        current_config=server,
                    ))
                elif is_advisor_config(server):
                    conflicts.append(Conflict(
                        type=ConflictType.DUPLICATE,
                        location="Claude Desktop",
                        message="advisor_mcp уже установлен",
                        current_config=server,
                    ))
                else:
                    conflicts.append(Conflict(
                        type=ConflictType.NAME_COLLISION,
                        location="Claude Desktop",
                        message="advisor_mcp указывает на другой сервер",
                        current_config=server,
                    ))

    return conflicts
```

**Step 2: Commit**

```bash
git add src/advisor_cli/mcp_manager.py
git commit -m "feat(mcp): add conflict detection"
```

---

## Task 4: Add Install/Uninstall Functions

**Files:**
- Modify: `src/advisor_cli/mcp_manager.py`

**Step 1: Add install/uninstall functions**

```python
def install_to_claude_code(scope: Scope) -> bool:
    """Install advisor_mcp to Claude Code config."""
    paths = get_config_paths()

    if scope == Scope.PROJECT:
        path = paths["claude_code_project"]
    else:
        path = paths["claude_code_user"]

    config = read_config(path)
    advisor_config = get_advisor_config_for_claude_code()
    config = set_mcp_server(config, "advisor_mcp", advisor_config["advisor_mcp"])
    write_config(path, config)
    return True


def install_to_desktop() -> bool:
    """Install advisor_mcp to Claude Desktop config."""
    paths = get_config_paths()
    desktop_path = paths.get("claude_desktop")

    if not desktop_path:
        return False

    config = read_config(desktop_path)
    advisor_config = get_advisor_config_for_desktop()
    config = set_mcp_server(config, "advisor_mcp", advisor_config["advisor_mcp"])
    write_config(desktop_path, config)
    return True


def uninstall_from_claude_code(scope: Scope) -> bool:
    """Remove advisor_mcp from Claude Code config."""
    paths = get_config_paths()

    if scope == Scope.PROJECT:
        path = paths["claude_code_project"]
    else:
        path = paths["claude_code_user"]

    if not path.exists():
        return False

    config = read_config(path)
    if "advisor_mcp" not in get_mcp_servers(config):
        return False

    config = remove_mcp_server(config, "advisor_mcp")
    write_config(path, config)
    return True


def uninstall_from_desktop() -> bool:
    """Remove advisor_mcp from Claude Desktop config."""
    paths = get_config_paths()
    desktop_path = paths.get("claude_desktop")

    if not desktop_path or not desktop_path.exists():
        return False

    config = read_config(desktop_path)
    if "advisor_mcp" not in get_mcp_servers(config):
        return False

    config = remove_mcp_server(config, "advisor_mcp")
    write_config(desktop_path, config)
    return True


def get_installation_status() -> dict[str, dict]:
    """Get advisor_mcp installation status for all configs."""
    paths = get_config_paths()
    status = {}

    # Claude Code user
    config = read_config(paths["claude_code_user"])
    servers = get_mcp_servers(config)
    if "advisor_mcp" in servers:
        status["claude_code_user"] = {
            "installed": True,
            "outdated": is_outdated_config(servers["advisor_mcp"]),
            "config": servers["advisor_mcp"],
        }
    else:
        status["claude_code_user"] = {"installed": False}

    # Claude Code project
    config = read_config(paths["claude_code_project"])
    servers = get_mcp_servers(config)
    if "advisor_mcp" in servers:
        status["claude_code_project"] = {
            "installed": True,
            "outdated": is_outdated_config(servers["advisor_mcp"]),
            "config": servers["advisor_mcp"],
        }
    else:
        status["claude_code_project"] = {"installed": False}

    # Claude Desktop
    desktop_path = paths.get("claude_desktop")
    if desktop_path:
        config = read_config(desktop_path)
        servers = get_mcp_servers(config)
        if "advisor_mcp" in servers:
            status["claude_desktop"] = {
                "installed": True,
                "outdated": is_outdated_config(servers["advisor_mcp"]),
                "config": servers["advisor_mcp"],
            }
        else:
            status["claude_desktop"] = {"installed": False}

    return status
```

**Step 2: Commit**

```bash
git add src/advisor_cli/mcp_manager.py
git commit -m "feat(mcp): add install/uninstall functions"
```

---

## Task 5: Add CLI mcp Commands

**Files:**
- Modify: `src/advisor_cli/cli.py`

**Step 1: Add mcp command group after config_app**

Add after line 42 (`app.add_typer(config_app, name="config")`):

```python
# Группа команд mcp
mcp_app = typer.Typer(help="Управление MCP интеграцией")
app.add_typer(mcp_app, name="mcp")
```

**Step 2: Add mcp install command**

Add at the end of the file before `if __name__ == "__main__":`:

```python
@mcp_app.command("install")
def mcp_install(
    scope: Optional[str] = typer.Option(
        None, "--scope", "-s", help="Scope: project или user"
    ),
    target: str = typer.Option(
        "all", "--target", "-t", help="Target: claude-code, desktop или all"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Перезаписать без вопросов"),
    yes: bool = typer.Option(False, "-y", help="Неинтерактивный режим"),
):
    """Установить MCP интеграцию для Claude."""
    from .mcp_manager import (
        Scope, Target, ConflictType,
        has_project_mcp_config, check_conflicts,
        install_to_claude_code, install_to_desktop,
    )
    from .setup_wizard import load_existing_env

    # Check if providers configured
    env = load_existing_env()
    has_providers = any(
        env.get(key) for key in [
            "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
            "DEEPSEEK_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY",
        ]
    )

    if not has_providers:
        if yes:
            print_output("Ошибка: Нет настроенных провайдеров. Установите API ключи.", error=True)
            raise typer.Exit(1)
        else:
            print_output("Нет настроенных провайдеров.")
            try:
                import questionary
                run_setup_q = questionary.confirm("Запустить настройку?", default=True).ask()
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
                    questionary.Choice("Глобально (Claude Code + Claude Desktop)", value="user"),
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
```

**Step 3: Add mcp uninstall command**

```python
@mcp_app.command("uninstall")
def mcp_uninstall(
    scope: Optional[str] = typer.Option(
        None, "--scope", "-s", help="Scope: project или user"
    ),
    all_scopes: bool = typer.Option(False, "--all", "-a", help="Удалить отовсюду"),
    yes: bool = typer.Option(False, "-y", help="Неинтерактивный режим"),
):
    """Удалить MCP интеграцию из Claude."""
    from .mcp_manager import (
        Scope, uninstall_from_claude_code, uninstall_from_desktop,
        get_installation_status,
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
        locations = []

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
                choices = [questionary.Choice(loc, value=(loc, scope_val)) for loc, scope_val in locations]
                selected = questionary.checkbox(
                    "Откуда удалить advisor_mcp?",
                    choices=choices,
                ).ask()

                for loc, scope_val in (selected or []):
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
```

**Step 4: Add mcp status command**

```python
@mcp_app.command("status")
def mcp_status():
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
```

**Step 5: Commit**

```bash
git add src/advisor_cli/cli.py
git commit -m "feat(cli): add mcp install/uninstall/status commands"
```

---

## Task 6: Add -y Flag to Setup Wizard

**Files:**
- Modify: `src/advisor_cli/setup_wizard.py`

**Step 1: Add non-interactive setup function**

Add after `get_custom_providers()` function (around line 210):

```python
def setup_from_env() -> bool:
    """Setup from environment variables (non-interactive mode)."""
    env_vars = {}
    enabled_providers = []

    # Check for API keys in environment
    for provider_id, info in PROVIDER_INFO.items():
        env_key = info["env_key"]
        value = os.environ.get(env_key)
        if value:
            env_vars[env_key] = value
            enabled_providers.append(provider_id)

    if not enabled_providers:
        return False

    # Set defaults
    first_provider = enabled_providers[0]
    default_model = PROVIDER_INFO[first_provider]["models"][0]
    env_vars["ADVISOR_DEFAULT_MODEL"] = default_model

    # Compare models: one from each provider
    compare_models = []
    for provider_id in enabled_providers[:3]:  # Max 3 for compare
        compare_models.append(PROVIDER_INFO[provider_id]["models"][0])
    env_vars["ADVISOR_DEFAULT_MODELS_COMPARE"] = ",".join(compare_models)

    # Default options
    env_vars["ADVISOR_CACHE_ENABLED"] = "true"
    env_vars["ADVISOR_CACHE_TTL"] = "3600"
    env_vars["ADVISOR_VERBOSE"] = "false"

    # Merge with existing
    existing = load_existing_env()
    existing.update(env_vars)
    save_env(existing)

    return True
```

**Step 2: Update run_setup to accept parameters**

Replace `def run_setup():` signature and beginning:

```python
def run_setup(
    non_interactive: bool = False,
    providers: Optional[list[str]] = None,
    model: Optional[str] = None,
):
    """Главная функция wizard'а.

    Args:
        non_interactive: If True, use defaults and env vars without prompts
        providers: List of provider IDs to configure (for -y mode)
        model: Default model to set (for -y mode)
    """
    if non_interactive:
        success = setup_from_env()
        if success:
            console.print("[green]✓ Конфигурация создана из переменных окружения[/green]")
        else:
            console.print("[red]✗ Не найдены API ключи в окружении[/red]")
            console.print("[dim]Установите GEMINI_API_KEY, OPENAI_API_KEY и т.д.[/dim]")
        return

    # ... rest of the function unchanged
```

**Step 3: Update CLI setup command**

In `cli.py`, update the `setup` command:

```python
@app.command()
def setup(
    yes: bool = typer.Option(False, "-y", help="Неинтерактивный режим (использовать env vars)"),
    providers: Optional[str] = typer.Option(None, "-p", "--providers", help="Провайдеры через запятую"),
    model: Optional[str] = typer.Option(None, "-m", "--model", help="Модель по умолчанию"),
):
    """Интерактивная настройка конфигурации (требует установки с [wizard])."""
    try:
        from .setup_wizard import run_setup

        provider_list = None
        if providers:
            provider_list = [p.strip() for p in providers.split(",")]

        run_setup(
            non_interactive=yes,
            providers=provider_list,
            model=model,
        )
    except ImportError:
        print_output(
            "Wizard не установлен. Установите: pip install advisor-cli[wizard]",
            error=True,
        )
        raise typer.Exit(1)
```

**Step 4: Commit**

```bash
git add src/advisor_cli/setup_wizard.py src/advisor_cli/cli.py
git commit -m "feat(setup): add -y non-interactive mode"
```

---

## Task 7: Update pyproject.toml for PyPI

**Files:**
- Modify: `pyproject.toml`

**Step 1: Update metadata**

```toml
[project]
name = "advisor-cli"
version = "0.2.0"
description = "Get second opinions from alternative LLMs (Gemini, GPT, DeepSeek, Ollama)"
readme = "README.md"
license = "MIT"
authors = [{ name = "Andrey Miroshkin", email = "your@email.com" }]
keywords = ["llm", "cli", "mcp", "ai", "gemini", "openai", "claude", "anthropic"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries :: Python Modules",
]
requires-python = ">=3.10"
dependencies = [
    "litellm>=1.0.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
    "typer>=0.12.0",
]

[project.optional-dependencies]
mcp = ["mcp>=1.0.0", "diskcache>=5.0.0"]
wizard = ["questionary>=2.0.0", "rich>=13.0.0"]
all = ["advisor-cli[mcp,wizard]"]

[project.urls]
Homepage = "https://github.com/mironovdm/advisor-cli"
Repository = "https://github.com/mironovdm/advisor-cli"
Documentation = "https://github.com/mironovdm/advisor-cli#readme"

[project.scripts]
advisor = "advisor_cli.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/advisor_cli"]

[dependency-groups]
dev = [
    "pytest>=9.0.2",
]
```

**Step 2: Commit**

```bash
git add pyproject.toml
git commit -m "chore: update pyproject.toml for PyPI"
```

---

## Task 8: Create install.sh

**Files:**
- Create: `install.sh`

**Step 1: Create install script**

```bash
#!/bin/sh
set -e

echo "🔧 Installing advisor-cli..."
echo ""

# 1. Check/install uv
if ! command -v uv >/dev/null 2>&1; then
    echo "📦 Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    echo ""
fi

# 2. Install advisor-cli
echo "📦 Installing advisor-cli..."
uv tool install advisor-cli
echo ""

# 3. Auto-setup if API keys in env
if [ -n "$GEMINI_API_KEY" ] || [ -n "$OPENAI_API_KEY" ] || [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "🔑 API keys found, configuring..."
    advisor setup -y
    echo ""
    echo "📡 Installing MCP integration..."
    advisor mcp install -y
else
    echo "✅ Installed! Next steps:"
    echo ""
    echo "   advisor setup        # Configure API keys"
    echo "   advisor mcp install  # Add to Claude"
    echo ""
    echo "Or run with API keys:"
    echo "   GEMINI_API_KEY=xxx advisor setup -y"
fi

echo ""
echo "📖 Usage:"
echo "   advisor ask 'your question'"
echo "   advisor compare 'question for multiple models'"
```

**Step 2: Make executable and commit**

```bash
chmod +x install.sh
git add install.sh
git commit -m "feat: add install.sh onboarding script"
```

---

## Task 9: Verification

**Step 1: Test mcp status**

```bash
uv run advisor mcp status
```

Expected: Shows installation status for all targets

**Step 2: Test mcp install (interactive)**

```bash
uv run advisor mcp install --target claude-code --scope project
```

Expected: Adds to .mcp.json

**Step 3: Test mcp install -y**

```bash
uv run advisor mcp install -y --target claude-code --scope user
```

Expected: Adds to ~/.claude.json without prompts

**Step 4: Test mcp uninstall**

```bash
uv run advisor mcp uninstall --scope project
```

Expected: Removes from .mcp.json

**Step 5: Test setup -y**

```bash
GEMINI_API_KEY=test uv run advisor setup -y
```

Expected: Creates .env with defaults

**Step 6: Test conflict detection**

```bash
uv run advisor mcp install
uv run advisor mcp install  # Should detect duplicate
```

Expected: Shows "уже установлен"

**Step 7: Final commit**

```bash
git add -A
git commit -m "test: verify mcp commands work"
```

---

## Summary

| Task | Files | Purpose |
|------|-------|---------|
| 1 | mcp_manager.py | Config paths & detection |
| 2 | mcp_manager.py | Read/write functions |
| 3 | mcp_manager.py | Conflict detection |
| 4 | mcp_manager.py | Install/uninstall |
| 5 | cli.py | mcp command group |
| 6 | setup_wizard.py, cli.py | -y flag |
| 7 | pyproject.toml | PyPI metadata |
| 8 | install.sh | Onboarding script |
| 9 | - | Verification |
