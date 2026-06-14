import pytest
import warnings
from domain.prompt.copy_mode import CopyMode, CopyConfig
from presentation.config.output_format import OutputStyle

def test_copy_config_serializes_to_dict():
    config = CopyConfig(mode=CopyMode.FULL, include_git_diff=True, tree_map_only=False)
    assert config.to_dict() == {
        "mode": "full",
        "include_git_diff": True,
        "tree_map_only": False,
        "output_style": "xml"
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
