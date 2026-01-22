"""Tests for MCP Advisor server."""

import pytest
from pydantic import ValidationError

from mcp_advisor.server import (
    _get_provider,
    _check_model_allowed,
    _format_error,
    _get_enabled_models_hint,
    ConsultExpertInput,
    CompareExpertsInput,
    ResponseFormat,
    PROVIDERS,
)


class TestGetProvider:
    """Tests for _get_provider function."""

    def test_extracts_provider_from_model(self):
        assert _get_provider("gemini/gemini-2.0-flash") == "gemini"
        assert _get_provider("openai/gpt-4o") == "openai"
        assert _get_provider("ollama-cloud/llama3.2") == "ollama-cloud"

    def test_returns_model_if_no_slash(self):
        assert _get_provider("gpt-4o") == "gpt-4o"
        assert _get_provider("llama3.2") == "llama3.2"


class TestCheckModelAllowed:
    """Tests for _check_model_allowed function."""

    def test_unknown_provider_returns_error(self):
        error = _check_model_allowed("unknown/model")
        assert error is not None
        assert "Неизвестный провайдер" in error

    def test_known_provider_format(self):
        # Should not raise, may return None or error depending on env
        result = _check_model_allowed("gemini/gemini-2.0-flash")
        # Result depends on whether GEMINI_API_KEY is set
        assert result is None or "не включён" in result


class TestFormatError:
    """Tests for _format_error function."""

    def test_unauthorized_error(self):
        error = _format_error(Exception("401 Unauthorized"))
        assert "Неверный API ключ" in error

    def test_rate_limit_error(self):
        error = _format_error(Exception("429 rate limit exceeded"))
        assert "лимит запросов" in error

    def test_timeout_error(self):
        error = _format_error(Exception("Request timeout"))
        assert "Таймаут" in error

    def test_generic_error(self):
        error = _format_error(Exception("Something went wrong"))
        assert "Something went wrong" in error


class TestGetEnabledModelsHint:
    """Tests for _get_enabled_models_hint function."""

    def test_returns_string(self):
        hint = _get_enabled_models_hint()
        assert isinstance(hint, str)
        # Should mention providers or "нет включённых"
        assert "провайдер" in hint.lower()


class TestConsultExpertInput:
    """Tests for ConsultExpertInput Pydantic model."""

    def test_valid_input(self):
        input_data = ConsultExpertInput(query="Test question")
        assert input_data.query == "Test question"
        assert input_data.response_format == ResponseFormat.MARKDOWN

    def test_query_required(self):
        with pytest.raises(ValidationError):
            ConsultExpertInput()

    def test_query_min_length(self):
        with pytest.raises(ValidationError):
            ConsultExpertInput(query="")

    def test_response_format_enum(self):
        input_data = ConsultExpertInput(
            query="Test", response_format=ResponseFormat.JSON
        )
        assert input_data.response_format == ResponseFormat.JSON

    def test_reasoning_pattern(self):
        # Valid values
        for level in ["low", "medium", "high"]:
            input_data = ConsultExpertInput(query="Test", reasoning=level)
            assert input_data.reasoning == level

        # Invalid value
        with pytest.raises(ValidationError):
            ConsultExpertInput(query="Test", reasoning="invalid")

    def test_strips_whitespace(self):
        input_data = ConsultExpertInput(query="  Test question  ")
        assert input_data.query == "Test question"


class TestCompareExpertsInput:
    """Tests for CompareExpertsInput Pydantic model."""

    def test_valid_input(self):
        input_data = CompareExpertsInput(query="Test question")
        assert input_data.query == "Test question"

    def test_models_default(self):
        input_data = CompareExpertsInput(query="Test")
        assert input_data.models  # Should have default value

    def test_custom_models(self):
        input_data = CompareExpertsInput(
            query="Test", models="gemini/gemini-2.0-flash,openai/gpt-4o"
        )
        assert "gemini" in input_data.models
        assert "openai" in input_data.models


class TestProvidersConfig:
    """Tests for PROVIDERS configuration."""

    def test_providers_structure(self):
        required_providers = [
            "gemini",
            "openai",
            "deepseek",
            "ollama",
            "ollama-cloud",
            "anthropic",
        ]
        for provider in required_providers:
            assert provider in PROVIDERS
            assert "env_key" in PROVIDERS[provider]
            assert "enabled" in PROVIDERS[provider]
