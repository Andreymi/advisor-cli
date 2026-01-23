"""Tests for cli_output module - output utilities."""

import sys
from io import StringIO
from unittest.mock import patch

import pytest
import typer

from advisor_cli.cli_output import _parse_format, print_output
from advisor_cli.core import ResponseFormat


class TestPrintOutput:
    """Tests for print_output function."""

    def test_prints_to_stdout(self):
        """print_output should write to stdout by default."""
        captured = StringIO()
        with patch.object(sys, "stdout", captured):
            print_output("Hello world")

        assert captured.getvalue() == "Hello world\n"

    def test_prints_to_stderr_when_error(self):
        """print_output with error=True should write to stderr."""
        captured = StringIO()
        with patch.object(sys, "stderr", captured):
            print_output("Error message", error=True)

        assert captured.getvalue() == "Error message\n"


class TestParseFormat:
    """Tests for _parse_format function."""

    def test_none_returns_markdown(self):
        """_parse_format(None) should return MARKDOWN."""
        result = _parse_format(None)
        assert result == ResponseFormat.MARKDOWN

    def test_json_lowercase(self):
        """_parse_format('json') should return JSON."""
        result = _parse_format("json")
        assert result == ResponseFormat.JSON

    def test_json_uppercase(self):
        """_parse_format('JSON') should return JSON."""
        result = _parse_format("JSON")
        assert result == ResponseFormat.JSON

    def test_markdown_lowercase(self):
        """_parse_format('markdown') should return MARKDOWN."""
        result = _parse_format("markdown")
        assert result == ResponseFormat.MARKDOWN

    def test_markdown_mixed_case(self):
        """_parse_format('MarkDown') should return MARKDOWN."""
        result = _parse_format("MarkDown")
        assert result == ResponseFormat.MARKDOWN

    def test_invalid_format_exits(self):
        """_parse_format with invalid format should raise typer.Exit."""
        with pytest.raises(typer.Exit) as exc_info:
            _parse_format("invalid_format")

        assert exc_info.value.exit_code == 1
