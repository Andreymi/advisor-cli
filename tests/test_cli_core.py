"""Tests for cli_core module - core CLI commands."""

from advisor_cli.cli_core import TASK_ID_LENGTH, core_app


def _get_command_names(app):
    """Get command names from typer app, handling both explicit and derived names."""
    names = []
    for cmd in app.registered_commands:
        # Explicit name takes precedence, otherwise use callback function name
        name = cmd.name or (cmd.callback.__name__ if cmd.callback else None)
        if name:
            names.append(name)
    return names


class TestCoreAppCommands:
    """Tests for core_app typer application commands."""

    def test_core_app_has_ask_command(self):
        """core_app should have an 'ask' command registered."""
        command_names = _get_command_names(core_app)
        assert "ask" in command_names

    def test_core_app_has_compare_command(self):
        """core_app should have a 'compare' command registered."""
        command_names = _get_command_names(core_app)
        assert "compare" in command_names

    def test_core_app_has_result_command(self):
        """core_app should have a 'result' command registered."""
        command_names = _get_command_names(core_app)
        assert "result" in command_names

    def test_core_app_has_status_command(self):
        """core_app should have a 'status' command registered."""
        command_names = _get_command_names(core_app)
        assert "status" in command_names

    def test_core_app_has_models_command(self):
        """core_app should have a 'models' command registered."""
        command_names = _get_command_names(core_app)
        assert "models" in command_names


class TestTaskIdLength:
    """Tests for TASK_ID_LENGTH constant."""

    def test_task_id_length_is_8(self):
        """TASK_ID_LENGTH should be 8 characters."""
        assert TASK_ID_LENGTH == 8
