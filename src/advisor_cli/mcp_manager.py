#!/usr/bin/env python3
"""MCP configuration manager for advisor-cli."""

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
        paths["claude_desktop"] = (
            home / "Library/Application Support/Claude/claude_desktop_config.json"
        )
    elif system == "Linux":
        paths["claude_desktop"] = home / ".config/Claude/claude_desktop_config.json"
    elif system == "Windows":
        paths["claude_desktop"] = (
            home / "AppData/Roaming/Claude/claude_desktop_config.json"
        )

    return paths


def get_advisor_path() -> str:
    """Get absolute path to advisor executable."""
    path = shutil.which("advisor")
    return path or "advisor"


def get_advisor_config_for_claude_code() -> dict:
    """Get MCP config for Claude Code (uses PATH)."""
    return {"advisor_mcp": {"command": "advisor", "args": ["run"]}}


def get_advisor_config_for_desktop() -> dict:
    """Get MCP config for Claude Desktop (needs absolute path)."""
    return {"advisor_mcp": {"command": get_advisor_path(), "args": ["run"]}}


def has_project_mcp_config() -> bool:
    """Check if .mcp.json exists in current directory."""
    return (Path.cwd() / ".mcp.json").exists()


def read_config(path: Path) -> dict:
    """Read JSON config file, return empty dict if not exists."""
    import json

    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, IOError):
        return {}


def write_config(path: Path, config: dict) -> None:
    """Write JSON config file, creating parent dirs if needed."""
    import json

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

    # Extract just the command name (basename)
    cmd_name = Path(cmd).name if cmd else ""

    # Old style: command is mcp-advisor
    if cmd_name == "mcp-advisor":
        return True
    # Old style: mcp-advisor in args (e.g., uv run mcp-advisor)
    if "mcp-advisor" in args:
        return True
    # Old style: uv run --directory ... mcp-advisor
    if len(args) >= 1 and args[-1] == "mcp-advisor":
        return True
    return False


def _check_config_conflicts(
    config: dict, location: str, conflicts: list[Conflict]
) -> None:
    """Helper to check conflicts in a single config."""
    servers = get_mcp_servers(config)

    if "advisor_mcp" in servers:
        server = servers["advisor_mcp"]
        if is_outdated_config(server):
            conflicts.append(
                Conflict(
                    type=ConflictType.OUTDATED,
                    location=location,
                    message="Устаревшая команда (mcp-advisor → advisor run)",
                    current_config=server,
                )
            )
        elif is_advisor_config(server):
            conflicts.append(
                Conflict(
                    type=ConflictType.DUPLICATE,
                    location=location,
                    message="advisor_mcp уже установлен",
                    current_config=server,
                )
            )
        else:
            conflicts.append(
                Conflict(
                    type=ConflictType.NAME_COLLISION,
                    location=location,
                    message="advisor_mcp указывает на другой сервер",
                    current_config=server,
                )
            )


def check_conflicts(scope: Scope, target: Target) -> list[Conflict]:
    """Check for conflicts before installation."""
    conflicts: list[Conflict] = []
    paths = get_config_paths()

    # Check Claude Code user config
    if target in (Target.ALL, Target.CLAUDE_CODE) and scope == Scope.USER:
        config = read_config(paths["claude_code_user"])
        _check_config_conflicts(config, "~/.claude.json", conflicts)

    # Check Claude Code project config
    if target in (Target.ALL, Target.CLAUDE_CODE) and scope == Scope.PROJECT:
        config = read_config(paths["claude_code_project"])
        _check_config_conflicts(config, ".mcp.json", conflicts)

        # Check if project overrides user
        user_config = read_config(paths["claude_code_user"])
        if "advisor_mcp" in get_mcp_servers(user_config):
            conflicts.append(
                Conflict(
                    type=ConflictType.OVERRIDE,
                    location=".mcp.json",
                    message="Проектный конфиг перекроет глобальный (~/.claude.json)",
                )
            )

    # Check Claude Desktop
    if target in (Target.ALL, Target.DESKTOP):
        desktop_path = paths.get("claude_desktop")
        if desktop_path:
            config = read_config(desktop_path)
            _check_config_conflicts(config, "Claude Desktop", conflicts)

    return conflicts


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
    status: dict[str, dict] = {}

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
