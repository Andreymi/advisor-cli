"""Tests for cli_config module - configuration commands."""

from advisor_cli.cli_config import config_app


def _get_command_names(app):
    """Get command names from typer app, handling both explicit and derived names."""
    names = []
    for cmd in app.registered_commands:
        # Explicit name takes precedence, otherwise use callback function name
        name = cmd.name or (cmd.callback.__name__ if cmd.callback else None)
        if name:
            names.append(name)
    return names


class TestConfigAppCommands:
    """Tests for config_app typer application commands."""

    def test_config_app_has_single_command(self):
        """config_app should have a 'single' command registered."""
        command_names = _get_command_names(config_app)
        assert "single" in command_names

    def test_config_app_has_compare_command(self):
        """config_app should have a 'compare' command registered."""
        command_names = _get_command_names(config_app)
        assert "compare" in command_names

    def test_config_app_has_format_command(self):
        """config_app should have a 'format' command registered."""
        command_names = _get_command_names(config_app)
        assert "format" in command_names

    def test_config_app_has_show_command(self):
        """config_app should have a 'show' command registered."""
        command_names = _get_command_names(config_app)
        assert "show" in command_names

    def test_config_app_has_purge_command(self):
        """config_app should have a 'purge' command registered."""
        command_names = _get_command_names(config_app)
        assert "purge" in command_names
