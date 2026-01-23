#!/usr/bin/env python3
"""Skill manager for advisor-cli."""

import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Scope(Enum):
    PROJECT = "project"
    USER = "user"


@dataclass
class SkillStatus:
    """Status of skill installation."""

    package_path: Path | None
    installed_path: Path | None
    is_installed: bool
    is_outdated: bool
    scope: Scope | None = None


def get_skill_source_path() -> Path:
    """Get path to bundled SKILL.md in package."""
    package_dir = Path(__file__).parent
    return package_dir / "data" / "skills" / "advisor" / "SKILL.md"


def get_skill_target_dir(scope: Scope = Scope.USER) -> Path:
    """Get target directory for skill installation."""
    if scope == Scope.PROJECT:
        return Path.cwd() / ".claude" / "skills" / "advisor"
    else:
        return Path.home() / ".claude" / "skills" / "advisor"


def get_skill_target_path(scope: Scope = Scope.USER) -> Path:
    """Get full path to installed skill."""
    return get_skill_target_dir(scope) / "SKILL.md"


def install_skill(scope: Scope = Scope.USER, force: bool = False) -> tuple[bool, str]:
    """Install skill to Claude skills directory.

    Args:
        scope: Where to install (project or user)
        force: Overwrite existing skill if present

    Returns:
        Tuple of (success, message)
    """
    source = get_skill_source_path()
    target_dir = get_skill_target_dir(scope)
    target = target_dir / "SKILL.md"

    if not source.exists():
        return False, "SKILL.md not found in package. Reinstall advisor-cli."

    if target.exists() and not force:
        return False, f"Skill already installed: {target}. Use --force."

    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)

    return True, str(target)


def uninstall_skill(scope: Scope = Scope.USER) -> tuple[bool, str]:
    """Remove installed skill.

    Args:
        scope: Where to uninstall from (project or user)

    Returns:
        Tuple of (success, message)
    """
    target_dir = get_skill_target_dir(scope)
    target = target_dir / "SKILL.md"

    if not target.exists():
        return False, "Skill not installed."

    target.unlink()

    # Remove empty directories
    if target_dir.exists() and not any(target_dir.iterdir()):
        target_dir.rmdir()
        # Also remove parent .claude/skills if empty
        skills_dir = target_dir.parent
        if skills_dir.exists() and not any(skills_dir.iterdir()):
            skills_dir.rmdir()

    return True, "Skill removed"


def get_skill_status(scope: Scope | None = None) -> SkillStatus:
    """Get current skill installation status.

    Args:
        scope: Check specific scope, or None to check both (user first)

    Returns:
        SkillStatus with installation details
    """
    source = get_skill_source_path()
    package_path = source if source.exists() else None

    # Check specific scope or find where installed
    if scope:
        target = get_skill_target_path(scope)
        found_scope = scope if target.exists() else None
    else:
        # Check project first, then user
        project_target = get_skill_target_path(Scope.PROJECT)
        user_target = get_skill_target_path(Scope.USER)

        if project_target.exists():
            target = project_target
            found_scope = Scope.PROJECT
        elif user_target.exists():
            target = user_target
            found_scope = Scope.USER
        else:
            target = user_target  # Default path for display
            found_scope = None

    installed_path = target if target.exists() else None
    is_installed = target.exists()

    is_outdated = False
    if is_installed and package_path:
        source_content = source.read_text()
        target_content = target.read_text()
        is_outdated = source_content != target_content

    return SkillStatus(
        package_path=package_path,
        installed_path=installed_path,
        is_installed=is_installed,
        is_outdated=is_outdated,
        scope=found_scope,
    )


def has_project_skill() -> bool:
    """Check if skill is installed in current project."""
    return get_skill_target_path(Scope.PROJECT).exists()
