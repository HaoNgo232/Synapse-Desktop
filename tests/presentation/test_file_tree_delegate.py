import pytest
from pathlib import Path
import json
import tempfile
import shutil

def test_material_icon_mapper():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        
        # Mock configuration JSON
        config = {
            "iconDefinitions": {
                "_file": {"iconPath": "icons/default_file.svg"},
                "_folder": {"iconPath": "icons/default_folder.svg"},
                "_folder_open": {"iconPath": "icons/default_folder_open.svg"},
                "python": {"iconPath": "icons/python.svg"},
                "folder_src": {"iconPath": "icons/folder_src.svg"},
                "folder_src_open": {"iconPath": "icons/folder_src_open.svg"}
            },
            "file": "_file",
            "folder": "_folder",
            "folderExpanded": "_folder_open",
            "fileExtensions": {
                "py": "python"
            },
            "fileNames": {
                "package.json": "nodejs"
            },
            "folderNames": {
                "src": "folder_src"
            },
            "folderNamesExpanded": {
                "src": "folder_src_open"
            }
        }
        
        # Write JSON config
        mat_dir = assets_dir / "material-icons"
        mat_dir.mkdir()
        with open(mat_dir / "material-icons.json", "w") as f:
            json.dump(config, f)
            
        # Create empty dummy icons
        icons_dir = mat_dir / "icons"
        icons_dir.mkdir()
        for key in ["default_file", "default_folder", "default_folder_open", "python", "folder_src", "folder_src_open"]:
            (icons_dir / f"{key}.svg").touch()
            
        # Test Mapper
        from presentation.components.file_tree.file_tree_delegate import MaterialIconMapper
        mapper = MaterialIconMapper(assets_dir)
        assert mapper.enabled is True
        
        # Test extensions
        p = mapper.get_icon_path("main.py", is_dir=False, is_expanded=False)
        assert p is not None
        assert Path(p).name == "python.svg"
        
        # Test folder closed
        p = mapper.get_icon_path("src", is_dir=True, is_expanded=False)
        assert p is not None
        assert Path(p).name == "folder_src.svg"
        
        # Test folder open
        p = mapper.get_icon_path("src", is_dir=True, is_expanded=True)
        assert p is not None
        assert Path(p).name == "folder_src_open.svg"


def test_file_tree_delegate_fallback():
    # Test that delegate fallback structure is present
    from presentation.components.file_tree.file_tree_delegate import FileTreeDelegate
    delegate = FileTreeDelegate()
    assert delegate._icon_mapper is not None
