#!/usr/bin/env python3
"""Skill manager for advisor-cli."""

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SkillStatus:
    """Status of skill installation."""

    package_path: Path | None
    installed_path: Path | None
    is_installed: bool
    is_outdated: bool


def get_skill_source_path() -> Path:
    """Get path to bundled SKILL.md in package."""
    package_dir = Path(__file__).parent
    return package_dir / "data" / "skills" / "advisor" / "SKILL.md"


def get_skill_target_dir() -> Path:
    """Get target directory for skill installation."""
    return Path.home() / ".claude" / "skills" / "advisor"


def get_skill_target_path() -> Path:
    """Get full path to installed skill."""
    return get_skill_target_dir() / "SKILL.md"


def install_skill(force: bool = False) -> tuple[bool, str]:
    """Install skill to user's Claude skills directory.

    Args:
        force: Overwrite existing skill if present

    Returns:
        Tuple of (success, message)
    """
    source = get_skill_source_path()
    target_dir = get_skill_target_dir()
    target = target_dir / "SKILL.md"

    if not source.exists():
        return False, "SKILL.md не найден в пакете. Переустановите advisor-cli."

    if target.exists() and not force:
        return False, f"Skill уже установлен: {target}. Используйте --force."

    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)

    return True, str(target)


def uninstall_skill() -> tuple[bool, str]:
    """Remove installed skill.

    Returns:
        Tuple of (success, message)
    """
    target_dir = get_skill_target_dir()
    target = target_dir / "SKILL.md"

    if not target.exists():
        return False, "Skill не установлен."

    target.unlink()

    # Remove empty directory
    if target_dir.exists() and not any(target_dir.iterdir()):
        target_dir.rmdir()

    return True, "Skill удалён"


def get_skill_status() -> SkillStatus:
    """Get current skill installation status.

    Returns:
        SkillStatus with installation details
    """
    source = get_skill_source_path()
    target = get_skill_target_path()

    package_path = source if source.exists() else None
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
    )
