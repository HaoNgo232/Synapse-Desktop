"""
Tests for domain.smart_context.config
Covers missing lines:
  - 182: ValueError on duplicate extension in _build_lookup_maps
  - 228-229: get_config_by_name returning None for unknown name
  - 234-235: get_supported_extensions
"""

import pytest
from unittest.mock import MagicMock, patch

from domain.smart_context.config import (
    LanguageConfig,
    _build_lookup_maps,
    get_config_by_name,
    get_supported_extensions,
    is_supported,
)
import domain.smart_context.config as config_module


# ---------------------------------------------------------------------------
# get_config_by_name
# ---------------------------------------------------------------------------


def test_get_config_by_name_returns_none_for_unknown():
    """get_config_by_name returns None for an unrecognised language name."""
    result = get_config_by_name("cobol_123_totally_unknown")
    assert result is None


def test_get_config_by_name_returns_config_for_known():
    """get_config_by_name returns a LanguageConfig for a supported language."""
    result = get_config_by_name("python")
    assert result is not None
    assert result.name == "python"


# ---------------------------------------------------------------------------
# get_supported_extensions
# ---------------------------------------------------------------------------


def test_get_supported_extensions_returns_list():
    """get_supported_extensions returns a non-empty list of extension strings."""
    exts = get_supported_extensions()
    assert isinstance(exts, list)
    assert len(exts) > 0
    assert "py" in exts


def test_get_supported_extensions_contains_common_langs():
    """Known extensions for common languages are present."""
    exts = get_supported_extensions()
    for expected in ("py", "js", "ts", "go", "rs", "java"):
        assert expected in exts, f"Expected extension '{expected}' to be supported"


# ---------------------------------------------------------------------------
# is_supported
# ---------------------------------------------------------------------------


def test_is_supported_returns_false_for_unknown_extension():
    """is_supported returns False for a completely unknown extension."""
    assert is_supported("xyz_notreal_789") is False


def test_is_supported_returns_true_for_python():
    """is_supported returns True for .py files."""
    assert is_supported("py") is True


# ---------------------------------------------------------------------------
# _build_lookup_maps – duplicate extension raises ValueError
# ---------------------------------------------------------------------------


def test_build_lookup_maps_raises_on_duplicate_extension():
    """_build_lookup_maps raises ValueError when two configs share an extension."""
    loader_mock = MagicMock()
    dup_config = LanguageConfig(
        name="python_duplicate",
        extensions=["py"],  # 'py' already claimed by python config
        query="",
        loader=loader_mock,
    )

    # Find the real python config to ensure 'py' is already in the list
    original = config_module.LANGUAGE_CONFIGS
    python_cfg = next(c for c in original if c.name == "python")
    dup_configs = [python_cfg, dup_config]

    with patch.object(config_module, "LANGUAGE_CONFIGS", dup_configs):
        with pytest.raises(ValueError, match="Duplicate extension"):
            _build_lookup_maps()
