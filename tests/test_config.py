"""Tests for config module."""

import os
from unittest.mock import patch

from advisor_cli.config import (
    load_config,
    save_config,
    update_config,
    mask_api_key,
    get_config_dir,
    get_cache_dir,
)


class TestMaskApiKey:
    """Tests for mask_api_key helper."""

    def test_short_key(self):
        assert mask_api_key("abc") == "***"

    def test_normal_key(self):
        result = mask_api_key("sk-1234567890abcdef")
        assert result.startswith("sk-1")
        assert result.endswith("cdef")
        assert "*" in result

    def test_empty_key(self):
        # Empty string returns "***" (length < 8)
        assert mask_api_key("") == "***"

    def test_exactly_8_chars(self):
        result = mask_api_key("12345678")
        assert result == "1234" + "" + "5678"  # no asterisks in middle


class TestConfigPaths:
    """Tests for XDG path functions."""

    def test_get_config_dir_default(self):
        # When XDG_CONFIG_HOME is not set, should use ~/.config
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": ""}):
            path = get_config_dir()
            assert "advisor" in str(path)
            assert ".config" in str(path) or "config" in str(path).lower()

    def test_get_config_dir_xdg(self, tmp_path):
        custom_config = tmp_path / "custom_config"
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(custom_config)}):
            path = get_config_dir()
            assert str(custom_config) in str(path)
            assert "advisor" in str(path)

    def test_get_cache_dir_default(self):
        # When XDG_CACHE_HOME is not set, should use ~/.cache
        with patch.dict(os.environ, {"XDG_CACHE_HOME": ""}):
            path = get_cache_dir()
            assert "advisor" in str(path)

    def test_get_cache_dir_xdg(self, tmp_path):
        custom_cache = tmp_path / "custom_cache"
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(custom_cache)}):
            path = get_cache_dir()
            assert str(custom_cache) in str(path)
            assert "advisor" in str(path)


class TestLoadSaveConfig:
    """Tests for load/save config."""

    def test_load_empty_config(self, tmp_path):
        config_file = tmp_path / "config.env"
        with patch("advisor_cli.config.CONFIG_FILE", config_file):
            config = load_config()
            assert config == {}

    def test_save_and_load_config(self, tmp_path):
        config_file = tmp_path / "config.env"
        with patch("advisor_cli.config.CONFIG_FILE", config_file):
            save_config({"TEST_KEY": "test_value"})
            loaded = load_config()
            assert loaded["TEST_KEY"] == "test_value"

    def test_load_ignores_comments(self, tmp_path):
        config_file = tmp_path / "config.env"
        config_file.write_text("# This is a comment\nKEY=value\n")
        with patch("advisor_cli.config.CONFIG_FILE", config_file):
            loaded = load_config()
            assert "KEY" in loaded
            assert loaded["KEY"] == "value"
            assert "#" not in loaded

    def test_load_strips_quotes(self, tmp_path):
        config_file = tmp_path / "config.env"
        config_file.write_text("KEY1=\"quoted\"\nKEY2='single'\n")
        with patch("advisor_cli.config.CONFIG_FILE", config_file):
            loaded = load_config()
            assert loaded["KEY1"] == "quoted"
            assert loaded["KEY2"] == "single"


class TestUpdateConfig:
    """Tests for update_config helper."""

    def test_update_single_key(self, tmp_path):
        config_file = tmp_path / "config.env"
        config_file.write_text("")
        with patch("advisor_cli.config.CONFIG_FILE", config_file):
            update_config("NEW_KEY", "new_value")
            loaded = load_config()
            assert loaded["NEW_KEY"] == "new_value"

    def test_update_preserves_existing(self, tmp_path):
        config_file = tmp_path / "config.env"
        with patch("advisor_cli.config.CONFIG_FILE", config_file):
            save_config({"EXISTING": "value"})
            update_config("NEW_KEY", "new_value")
            loaded = load_config()
            assert loaded["EXISTING"] == "value"
            assert loaded["NEW_KEY"] == "new_value"

    def test_update_overwrites_existing(self, tmp_path):
        config_file = tmp_path / "config.env"
        with patch("advisor_cli.config.CONFIG_FILE", config_file):
            save_config({"KEY": "old"})
            update_config("KEY", "new")
            loaded = load_config()
            assert loaded["KEY"] == "new"
