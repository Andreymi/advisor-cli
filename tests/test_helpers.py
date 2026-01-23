"""Tests for helper functions introduced during refactoring."""

import pytest
from click.exceptions import Exit as ClickExit
from unittest.mock import patch

from advisor_cli.cli_output import _parse_format
from advisor_cli.core import ResponseFormat


class TestParseFormat:
    """Tests for _parse_format helper."""

    def test_none_returns_markdown(self):
        assert _parse_format(None) == ResponseFormat.MARKDOWN

    def test_json_lowercase(self):
        assert _parse_format("json") == ResponseFormat.JSON

    def test_json_uppercase(self):
        assert _parse_format("JSON") == ResponseFormat.JSON

    def test_markdown_lowercase(self):
        assert _parse_format("markdown") == ResponseFormat.MARKDOWN

    def test_markdown_mixed_case(self):
        assert _parse_format("Markdown") == ResponseFormat.MARKDOWN

    def test_invalid_format_exits(self):
        with pytest.raises(ClickExit):
            _parse_format("invalid")


class TestBuildContext:
    """Tests for build_context helper."""

    def test_none_inputs_returns_empty(self):
        from advisor_cli.file_utils import build_context

        with patch("advisor_cli.file_utils.read_stdin", return_value=None):
            assert build_context(None, None) == ""

    def test_context_only(self):
        from advisor_cli.file_utils import build_context

        with patch("advisor_cli.file_utils.read_stdin", return_value=None):
            assert build_context("my context", None) == "my context"

    def test_stdin_only(self):
        from advisor_cli.file_utils import build_context

        with patch("advisor_cli.file_utils.read_stdin", return_value="stdin data"):
            assert build_context(None, None) == "stdin data"

    def test_context_and_stdin_combined(self):
        from advisor_cli.file_utils import build_context

        with patch("advisor_cli.file_utils.read_stdin", return_value="stdin data"):
            result = build_context("my context", None)
            assert "my context" in result
            assert "stdin data" in result

    def test_file_context(self, tmp_path):
        from advisor_cli.file_utils import build_context

        test_file = tmp_path / "test.py"
        test_file.write_text("file content")
        with patch("advisor_cli.file_utils.read_stdin", return_value=None):
            result = build_context(None, test_file)
            assert result == "file content"


class TestBuildMessages:
    """Tests for _build_messages helper."""

    def test_query_only(self):
        from advisor_cli.core import _build_messages

        messages = _build_messages("What is Python?", None, "You are helpful.")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are helpful."
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "What is Python?"

    def test_query_with_context(self):
        from advisor_cli.core import _build_messages

        messages = _build_messages("Review this", "code here", "You are a reviewer.")
        assert len(messages) == 2
        assert "Контекст:" in messages[1]["content"]
        assert "code here" in messages[1]["content"]
        assert "Review this" in messages[1]["content"]

    def test_empty_context_treated_as_none(self):
        from advisor_cli.core import _build_messages

        messages = _build_messages("Question?", "", "System role")
        assert len(messages) == 2
        # Empty string is falsy, so context should not be included
        assert "Контекст:" not in messages[1]["content"]
        assert messages[1]["content"] == "Question?"


class TestRequireWizard:
    """Tests for require_wizard decorator."""

    def test_function_works_when_import_succeeds(self):
        from advisor_cli.utils import require_wizard

        @require_wizard
        def my_func():
            return "success"

        assert my_func() == "success"

    def test_exits_on_import_error(self):
        from advisor_cli.utils import require_wizard

        @require_wizard
        def my_func():
            raise ImportError("questionary not found")

        with pytest.raises(ClickExit):
            my_func()

    def test_error_message_contains_install_command(self, capsys):
        """Verify error message shows correct install command with [wizard]."""
        from advisor_cli.utils import require_wizard

        @require_wizard
        def my_func():
            raise ImportError("questionary not found")

        with pytest.raises(ClickExit):
            my_func()

        captured = capsys.readouterr()
        # Critical: [wizard] must not be eaten by rich markup parser
        assert "[wizard]" in captured.out, (
            f"Install command missing [wizard]. Got: {captured.out!r}"
        )
