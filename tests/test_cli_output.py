"""Tests for cli_output module - output utilities."""

import sys
from io import StringIO
from unittest.mock import patch

import pytest
import typer

from advisor_cli.cli_output import print_output, parse_format
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
    """Tests for parse_format function."""

    def test_none_returns_markdown(self):
        """parse_format(None) should return MARKDOWN."""
        result = parse_format(None)
        assert result == ResponseFormat.MARKDOWN

    def test_json_lowercase(self):
        """parse_format('json') should return JSON."""
        result = parse_format("json")
        assert result == ResponseFormat.JSON

    def test_json_uppercase(self):
        """parse_format('JSON') should return JSON."""
        result = parse_format("JSON")
        assert result == ResponseFormat.JSON

    def test_markdown_lowercase(self):
        """parse_format('markdown') should return MARKDOWN."""
        result = parse_format("markdown")
        assert result == ResponseFormat.MARKDOWN

    def test_markdown_mixed_case(self):
        """parse_format('MarkDown') should return MARKDOWN."""
        result = parse_format("MarkDown")
        assert result == ResponseFormat.MARKDOWN

    def test_invalid_format_exits(self):
        """parse_format with invalid format should raise typer.Exit."""
        with pytest.raises(typer.Exit) as exc_info:
            parse_format("invalid_format")

        assert exc_info.value.exit_code == 1
