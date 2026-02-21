"""
Tests cho AppSettings dataclass va typed settings API.

Coverage:
- AppSettings.from_dict() voi day du fields, partial fields, extra keys
- AppSettings.to_dict() roundtrip
- get_excluded_patterns_list() parsing
- load_app_settings() / save_app_settings() / update_app_setting()
- Backward compat voi legacy API
"""

import json
import pytest
from unittest.mock import patch

from config.app_settings import AppSettings


# ============================================================
# AppSettings dataclass tests
# ============================================================


class TestAppSettings:
    """Test AppSettings dataclass creation va methods."""

    def test_default_values(self):
        """Test AppSettings co default values dung."""
        settings = AppSettings()
        assert settings.model_id == "claude-sonnet-4.5"
        assert settings.output_format == "xml"
        assert settings.include_git_changes is True
        assert settings.enable_security_check is True
        assert settings.use_gitignore is True
        assert settings.use_relative_paths is True
        assert "node_modules" in settings.excluded_folders

    def test_from_dict_full(self):
        """Test from_dict voi tat ca fields."""
        data = {
            "excluded_folders": "vendor\nbin",
            "use_gitignore": False,
            "model_id": "gpt-4",
            "output_format": "markdown",
            "include_git_changes": False,
            "use_relative_paths": False,
            "enable_security_check": False,
        }
        settings = AppSettings.from_dict(data)
        assert settings.excluded_folders == "vendor\nbin"
        assert settings.use_gitignore is False
        assert settings.model_id == "gpt-4"
        assert settings.output_format == "markdown"
        assert settings.include_git_changes is False
        assert settings.use_relative_paths is False
        assert settings.enable_security_check is False

    def test_from_dict_partial(self):
        """Test from_dict voi chi mot so fields - con lai la defaults."""
        data = {"model_id": "gpt-4"}
        settings = AppSettings.from_dict(data)
        assert settings.model_id == "gpt-4"
        # Defaults cho cac fields con lai
        assert settings.use_gitignore is True
        assert settings.enable_security_check is True

    def test_from_dict_extra_keys_ignored(self):
        """Test from_dict bo qua cac keys khong phai AppSettings field."""
        data = {
            "model_id": "gpt-4",
            "unknown_key": "should_be_ignored",
            "another_extra": 42,
        }
        settings = AppSettings.from_dict(data)
        assert settings.model_id == "gpt-4"
        # Extra keys bi bo qua, khong raise loi
        assert not hasattr(settings, "unknown_key")

    def test_from_dict_empty(self):
        """Test from_dict voi dict rong -> tat ca defaults."""
        settings = AppSettings.from_dict({})
        defaults = AppSettings()
        assert settings.to_dict() == defaults.to_dict()

    def test_to_dict_roundtrip(self):
        """Test from_dict(to_dict()) cho ket qua giong nhau."""
        original = AppSettings(
            model_id="gpt-4",
            output_format="markdown",
            include_git_changes=False,
        )
        restored = AppSettings.from_dict(original.to_dict())
        assert original.to_dict() == restored.to_dict()

    def test_to_dict_keys(self):
        """Test to_dict tra ve tat ca expected keys."""
        settings = AppSettings()
        d = settings.to_dict()
        expected_keys = {
            "excluded_folders",
            "use_gitignore",
            "model_id",
            "output_format",
            "include_git_changes",
            "use_relative_paths",
            "enable_security_check",
            "instruction_history",
        }
        assert set(d.keys()) == expected_keys

    def test_get_excluded_patterns_list(self):
        """Test parse excluded_folders string thanh list patterns."""
        settings = AppSettings(
            excluded_folders="node_modules\n  dist  \n\n# comment\nbuild"
        )
        patterns = settings.get_excluded_patterns_list()
        assert patterns == ["node_modules", "dist", "build"]

    def test_get_excluded_patterns_list_empty(self):
        """Test excluded patterns rong."""
        settings = AppSettings(excluded_folders="")
        assert settings.get_excluded_patterns_list() == []

    def test_get_excluded_patterns_list_comments_only(self):
        """Test excluded patterns chi co comments."""
        settings = AppSettings(excluded_folders="# comment1\n# comment2")
        assert settings.get_excluded_patterns_list() == []


# ============================================================
# Typed settings manager API tests
# ============================================================


class TestTypedSettingsManager:
    """Test load_app_settings, save_app_settings, update_app_setting."""

    def test_load_app_settings_no_file(self, tmp_path):
        """Test load khi file chua ton tai -> defaults."""
        from services.settings_manager import load_app_settings

        fake_file = tmp_path / "nonexistent.json"
        with patch("services.settings_manager.SETTINGS_FILE", fake_file):
            settings = load_app_settings()
            assert isinstance(settings, AppSettings)
            assert settings.model_id == "claude-sonnet-4.5"

    def test_load_app_settings_with_file(self, tmp_path):
        """Test load tu existing file."""
        from services.settings_manager import load_app_settings

        settings_file = tmp_path / "settings.json"
        settings_file.write_text(
            json.dumps(
                {
                    "model_id": "gpt-4",
                    "enable_security_check": False,
                }
            )
        )

        with patch("services.settings_manager.SETTINGS_FILE", settings_file):
            settings = load_app_settings()
            assert settings.model_id == "gpt-4"
            assert settings.enable_security_check is False
            # Default cho cac fields khong co trong file
            assert settings.use_gitignore is True

    def test_load_app_settings_invalid_json(self, tmp_path):
        """Test load khi file corrupt -> defaults."""
        from services.settings_manager import load_app_settings

        settings_file = tmp_path / "settings.json"
        settings_file.write_text("not json {{{")

        with patch("services.settings_manager.SETTINGS_FILE", settings_file):
            settings = load_app_settings()
            assert settings.model_id == "claude-sonnet-4.5"

    def test_save_app_settings(self, tmp_path):
        """Test save -> load roundtrip."""
        from services.settings_manager import (
            load_app_settings,
            save_app_settings,
        )

        settings_file = tmp_path / "settings.json"

        with patch("services.settings_manager.SETTINGS_FILE", settings_file):
            original = AppSettings(model_id="gpt-4", use_gitignore=False)
            assert save_app_settings(original) is True

            loaded = load_app_settings()
            assert loaded.model_id == "gpt-4"
            assert loaded.use_gitignore is False

    def test_save_preserves_extra_keys(self, tmp_path):
        """Test save bao toan extra keys trong file (keys khong thuoc AppSettings)."""
        from services.settings_manager import save_app_settings

        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({"custom_key": "custom_value"}))

        with patch("services.settings_manager.SETTINGS_FILE", settings_file):
            assert save_app_settings(AppSettings()) is True

            saved = json.loads(settings_file.read_text())
            assert saved["custom_key"] == "custom_value"  # Extra key van con
            assert saved["model_id"] == "claude-sonnet-4.5"

    def test_update_app_setting_single(self, tmp_path):
        """Test update 1 field."""
        from services.settings_manager import (
            load_app_settings,
            update_app_setting,
        )

        settings_file = tmp_path / "settings.json"

        with patch("services.settings_manager.SETTINGS_FILE", settings_file):
            assert update_app_setting(model_id="gpt-4") is True
            settings = load_app_settings()
            assert settings.model_id == "gpt-4"

    def test_update_app_setting_multiple(self, tmp_path):
        """Test update nhieu fields cung luc."""
        from services.settings_manager import (
            load_app_settings,
            update_app_setting,
        )

        settings_file = tmp_path / "settings.json"

        with patch("services.settings_manager.SETTINGS_FILE", settings_file):
            assert (
                update_app_setting(
                    model_id="gpt-4",
                    enable_security_check=False,
                )
                is True
            )

            settings = load_app_settings()
            assert settings.model_id == "gpt-4"
            assert settings.enable_security_check is False

    def test_update_app_setting_invalid_field(self, tmp_path):
        """Test update voi field khong ton tai -> TypeError."""
        from services.settings_manager import update_app_setting

        settings_file = tmp_path / "settings.json"

        with patch("services.settings_manager.SETTINGS_FILE", settings_file):
            with pytest.raises(TypeError, match="not a valid AppSettings field"):
                update_app_setting(invalid_field="value")


# ============================================================
# Backward compatibility tests
# ============================================================


class TestBackwardCompat:
    """Dam bao legacy API van hoat dong dung."""

    def test_load_settings_returns_dict(self, tmp_path):
        """load_settings() van tra ve Dict."""
        from services.settings_manager import load_settings

        settings_file = tmp_path / "nonexistent.json"
        with patch("services.settings_manager.SETTINGS_FILE", settings_file):
            result = load_settings()
            assert isinstance(result, dict)
            assert "model_id" in result

    def test_get_setting_works(self, tmp_path):
        """get_setting() van lay dung value."""
        from services.settings_manager import get_setting

        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({"model_id": "gpt-4"}))

        with patch("services.settings_manager.SETTINGS_FILE", settings_file):
            assert get_setting("model_id") == "gpt-4"

    def test_set_setting_works(self, tmp_path):
        """set_setting() van luu dung value."""
        from services.settings_manager import set_setting, get_setting

        settings_file = tmp_path / "settings.json"

        with patch("services.settings_manager.SETTINGS_FILE", settings_file):
            assert set_setting("model_id", "gpt-4") is True
            assert get_setting("model_id") == "gpt-4"

    def test_save_settings_dict(self, tmp_path):
        """save_settings() van nhan Dict va luu dung."""
        from services.settings_manager import save_settings, load_settings

        settings_file = tmp_path / "settings.json"

        with patch("services.settings_manager.SETTINGS_FILE", settings_file):
            assert save_settings({"model_id": "gpt-4"}) is True
            result = load_settings()
            assert result["model_id"] == "gpt-4"
