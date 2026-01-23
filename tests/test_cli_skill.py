"""Tests for cli_skill module - Skill management commands."""

from advisor_cli.cli_skill import skill_app


def _get_command_names(app):
    """Get command names from typer app, handling both explicit and derived names."""
    names = []
    for cmd in app.registered_commands:
        # Explicit name takes precedence, otherwise use callback function name
        name = cmd.name or (cmd.callback.__name__ if cmd.callback else None)
        if name:
            names.append(name)
    return names


class TestSkillAppCommands:
    """Tests for skill_app typer application commands."""

    def test_skill_app_has_install_command(self):
        """skill_app should have an 'install' command registered."""
        command_names = _get_command_names(skill_app)
        assert "install" in command_names

    def test_skill_app_has_uninstall_command(self):
        """skill_app should have an 'uninstall' command registered."""
        command_names = _get_command_names(skill_app)
        assert "uninstall" in command_names

    def test_skill_app_has_status_command(self):
        """skill_app should have a 'status' command registered."""
        command_names = _get_command_names(skill_app)
        assert "status" in command_names
