from unittest.mock import MagicMock
import pytest
from domain.config.output_format import OutputStyle
from domain.prompt.copy_mode import CopyMode, CopyConfig


def test_copy_config_serializes_to_dict():
    config = CopyConfig(mode=CopyMode.FULL, include_git_diff=True, tree_map_only=False)
    assert config.to_dict() == {
        "mode": "full",
        "include_git_diff": True,
        "tree_map_only": False,
        "output_style": "xml",
        "git_commit_depth": 0,
    }


def test_legacy_compress_string_loads_as_smart():
    with pytest.deprecated_call():
        config = CopyConfig.from_dict({"mode": "compress"})
    assert config.mode == CopyMode.SMART


def test_legacy_strings_all_map_correctly():
    c1 = CopyConfig.from_dict({"mode": "copy_context"})
    assert c1.mode == CopyMode.FULL
    c2 = CopyConfig.from_dict({"mode": "search_replace"})
    assert c2.mode == CopyMode.APPLY


def test_tree_map_only_overrides_mode():
    config = CopyConfig.from_dict({"mode": "full", "tree_map_only": True})
    assert config.tree_map_only is True


def test_all_modes_have_display_name():
    for m in CopyMode:
        assert len(m.display_name) > 0
        assert len(m.description) > 0


def test_invalid_mode_string_raises_value_error():
    with pytest.raises(ValueError):
        CopyConfig.from_dict({"mode": "invalid_mode"})


def test_copy_mode_unknown_display_name_and_description_raises_error() -> None:
    """Kiểm tra thuộc tính display_name và description quăng lỗi khi CopyMode không xác định."""
    mock_mode = MagicMock()
    with pytest.raises(ValueError, match="Unknown mode"):
        CopyMode.display_name.fget(mock_mode)

    with pytest.raises(ValueError, match="Unknown mode"):
        CopyMode.description.fget(mock_mode)


def test_invalid_output_style_defaults_to_xml() -> None:
    """Kiểm tra định dạng style không hợp lệ sẽ mặc định quay về XML."""
    config = CopyConfig.from_dict({"mode": "full", "output_style": "invalid_style"})
    assert config.output_style == OutputStyle.XML
