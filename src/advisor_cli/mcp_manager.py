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
