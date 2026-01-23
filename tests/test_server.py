"""Tests for MCP Advisor core functionality."""

import pytest
from pydantic import ValidationError

from advisor_cli.core import (
    get_provider,
    check_model_allowed,
    format_error,
    get_enabled_models_hint,
    ConsultExpertInput,
    CompareExpertsInput,
    ResponseFormat,
    PROVIDERS,
)

# Aliases for backwards compatibility with test names
_get_provider = get_provider
_check_model_allowed = check_model_allowed
_format_error = format_error
_get_enabled_models_hint = get_enabled_models_hint


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

    def test_gemini_invalid_api_key(self):
        """Test Gemini's 400 'API key not valid' error is handled."""
        error = _format_error(
            Exception('{"error": {"code": 400, "message": "API key not valid"}}')
        )
        assert "GEMINI_API_KEY" in error


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


class TestCacheManager:
    """Tests for CacheManager class."""

    def test_singleton_pattern(self):
        """get_cache_manager should return the same instance."""
        from advisor_cli.core import get_cache_manager

        manager1 = get_cache_manager()
        manager2 = get_cache_manager()
        assert manager1 is manager2

    def test_initial_state(self):
        """CacheManager should start with cache inactive."""
        from advisor_cli.core import CacheManager

        manager = CacheManager()
        assert manager.llm_cache_active is False
        assert manager.reasoning_cache == {}

    def test_reasoning_cache_operations(self, tmp_path):
        """CacheManager should handle reasoning cache operations."""
        from unittest.mock import patch
        from advisor_cli.core import CacheManager

        manager = CacheManager()

        # Mock CACHE_DIR to use tmp_path
        with patch("advisor_cli.core.CACHE_DIR", tmp_path):
            # Initially empty
            assert manager.get_reasoning_type("gpt-4") is None

            # Set and retrieve
            manager.set_reasoning_type("gpt-4", "thinking")
            assert manager.get_reasoning_type("gpt-4") == "thinking"

            # Check is_model_cached
            assert manager.is_model_cached("gpt-4") is True
            assert manager.is_model_cached("unknown-model") is False

    def test_reasoning_cache_persistence(self, tmp_path):
        """Reasoning cache should persist to disk."""
        from unittest.mock import patch
        from advisor_cli.core import CacheManager

        with patch("advisor_cli.core.CACHE_DIR", tmp_path):
            # First manager sets value
            manager1 = CacheManager()
            manager1.set_reasoning_type("test-model", "thinking")

            # Verify file was created
            cache_file = tmp_path / "reasoning_models.json"
            assert cache_file.exists()

            # New manager loads from disk
            manager2 = CacheManager()
            manager2.load_reasoning_cache()
            assert manager2.get_reasoning_type("test-model") == "thinking"

    def test_clear_reasoning_cache(self, tmp_path):
        """clear_reasoning_cache should remove all entries and delete file."""
        from unittest.mock import patch
        from advisor_cli.core import CacheManager

        with patch("advisor_cli.core.CACHE_DIR", tmp_path):
            manager = CacheManager()
            manager.set_reasoning_type("model-1", "thinking")
            manager.set_reasoning_type("model-2", "reasoning_effort")

            cache_file = tmp_path / "reasoning_models.json"
            assert cache_file.exists()

            count = manager.clear_reasoning_cache()
            assert count == 2
            assert not cache_file.exists()
            assert manager.reasoning_cache == {}

    def test_refresh_reasoning_cache(self, tmp_path):
        """refresh_reasoning_cache should reload from disk."""
        import json
        from unittest.mock import patch
        from advisor_cli.core import CacheManager

        with patch("advisor_cli.core.CACHE_DIR", tmp_path):
            # Create cache file directly
            cache_file = tmp_path / "reasoning_models.json"
            tmp_path.mkdir(exist_ok=True)
            cache_file.write_text(json.dumps({"disk-model": "thinking"}))

            manager = CacheManager()
            # Manually add in-memory entry
            manager.reasoning_cache["memory-model"] = "reasoning_effort"
            manager._reasoning_cache_loaded = True

            # Refresh should discard memory and load from disk
            manager.refresh_reasoning_cache()
            assert "disk-model" in manager.reasoning_cache
            assert "memory-model" not in manager.reasoning_cache
