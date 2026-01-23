"""Tests for cli_install module - Unified install/uninstall commands."""

from advisor_cli.cli_install import install_app


def _get_command_names(app):
    """Get command names from typer app, handling both explicit and derived names."""
    names = []
    for cmd in app.registered_commands:
        # Explicit name takes precedence, otherwise use callback function name
        name = cmd.name or (cmd.callback.__name__ if cmd.callback else None)
        if name:
            names.append(name)
    return names


class TestInstallAppCommands:
    """Tests for install_app typer application commands."""

    def test_install_app_has_install_command(self):
        """install_app should have an 'install' command registered."""
        command_names = _get_command_names(install_app)
        assert "install" in command_names

    def test_install_app_has_uninstall_command(self):
        """install_app should have an 'uninstall' command registered."""
        command_names = _get_command_names(install_app)
        assert "uninstall" in command_names
