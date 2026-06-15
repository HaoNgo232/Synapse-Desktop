from pathlib import Path
from shared.config.paths import APP_DIR, get_app_dir, APP_NAME

def test_paths_integrity():
    assert APP_NAME == "synapse-desktop"
    assert isinstance(APP_DIR, Path)
    assert get_app_dir() == APP_DIR
