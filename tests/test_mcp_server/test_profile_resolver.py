"""
Tests cho mcp_server/core/profile_resolver.py

Kiem tra resolve_profile_params xu ly dung cac truong hop:
- Profile hop le -> override defaults
- Profile khong ton tai -> ValueError
- Explicit params override profile
- Khong co profile -> giu nguyen defaults

Return format: tuple (output_format, include_git_changes, instructions,
                       max_tokens, auto_expand_dependencies, profile_name)
                       index:  0              1                2
                               3              4                5
"""

import pytest
from unittest.mock import patch, MagicMock

from mcp_server.core.profile_resolver import resolve_profile_params

# Index constants cho tuple return value
FMT = 0  # output_format
GIT = 1  # include_git_changes
INST = 2  # instructions
TOKENS = 3  # max_tokens
EXPAND = 4  # auto_expand_dependencies
PROF_NAME = 5  # resolved profile name


class TestProfileResolverWithValidProfile:
    """Kiem tra resolve_profile_params khi truyen profile hop le."""

    @patch("presentation.config.prompt_profiles.list_profiles", return_value=["review"])
    @patch("presentation.config.prompt_profiles.get_profile")
    def test_profile_overrides_defaults(self, mock_get, mock_list):
        """Profile hop le override cac gia tri mac dinh."""
        mock_profile = MagicMock()
        mock_profile.name = "review"
        mock_profile.output_format = "json"
        mock_profile.include_git_changes = True
        mock_profile.instruction_prefix = "Review carefully."
        mock_profile.max_tokens = 50000
        mock_profile.auto_expand_dependencies = True
        mock_get.return_value = mock_profile

        # Truyen default values cho cac params (xml, False, "", None, False)
        result = resolve_profile_params("review", "xml", False, "", None, False)

        assert result[FMT] == "json"
        assert result[GIT] is True
        assert "Review carefully" in result[INST]
        assert result[TOKENS] == 50000
        assert result[EXPAND] is True
        assert result[PROF_NAME] == "review"

    @patch("presentation.config.prompt_profiles.list_profiles", return_value=["review"])
    @patch("presentation.config.prompt_profiles.get_profile")
    def test_explicit_params_override_profile(self, mock_get, mock_list):
        """Explicit params duoc uu tien hon profile defaults."""
        mock_profile = MagicMock()
        mock_profile.name = "review"
        mock_profile.output_format = "json"
        mock_profile.include_git_changes = True
        mock_profile.instruction_prefix = "Profile prefix."
        mock_profile.max_tokens = 50000
        mock_profile.auto_expand_dependencies = False
        mock_get.return_value = mock_profile

        # Non-default values -> explicit overrides
        result = resolve_profile_params(
            "review",
            "plain",  # non-default (khac "xml")
            True,  # non-default (khac False)
            "My instructions",
            100000,  # non-default (khac None)
            True,  # non-default (khac False)
        )

        # Explicit values duoc uu tien
        assert result[FMT] == "plain"
        assert result[GIT] is True
        assert result[TOKENS] == 100000
        assert result[EXPAND] is True


class TestProfileResolverWithInvalidProfile:
    """Kiem tra resolve_profile_params khi profile khong ton tai."""

    @patch(
        "presentation.config.prompt_profiles.list_profiles",
        return_value=["review", "bugfix"],
    )
    @patch("presentation.config.prompt_profiles.get_profile", return_value=None)
    def test_invalid_profile_raises_error(self, mock_get, mock_list):
        """Profile khong ton tai -> ValueError."""
        with pytest.raises(ValueError, match="Unknown profile"):
            resolve_profile_params("nonexistent_profile", "xml", False, "", None, False)


class TestProfileResolverWithoutProfile:
    """Kiem tra resolve_profile_params khi khong truyen profile."""

    def test_no_profile_returns_passthrough(self):
        """Khong truyen profile -> tra ve cac params goc khong doi."""
        result = resolve_profile_params(None, "xml", False, "hello", None, False)

        assert result[FMT] == "xml"
        assert result[GIT] is False
        assert result[INST] == "hello"
        assert result[TOKENS] is None
        assert result[EXPAND] is False
        assert result[PROF_NAME] is None

    def test_no_profile_with_custom_params(self):
        """Khong co profile, custom params -> giu nguyen custom."""
        result = resolve_profile_params(None, "plain", True, "custom", 80000, True)

        assert result[FMT] == "plain"
        assert result[GIT] is True
        assert result[INST] == "custom"
        assert result[TOKENS] == 80000
        assert result[EXPAND] is True
