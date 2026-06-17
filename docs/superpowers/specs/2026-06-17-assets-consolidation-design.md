# Design Spec: Assets Consolidation

## 1. Goal & Description

The goal of this task is to consolidate all system assets (icons, fonts, and images) into a single directory located at the project root (`assets/`). 

Currently, asset files are duplicated across three different locations:
1. `assets/` (project root)
2. `presentation/assets/`
3. `presentation/components/assets/`

This duplication leads to wasted storage, high risk of asset mismatch (e.g., updating an icon in one folder but forgetting to update it in others), and packaging issues. We want a clean, single source of truth for all UI assets.

## 2. Requirements & Constraints

1. **Single Source of Truth**: Only `assets/` at the project root will exist. All duplicated asset directories must be deleted.
2. **Support for Dynamic Styling**: The SVG files in `presentation/assets/` use `stroke="currentColor"`, which is required by `create_colored_icon()` to style icons dynamically. The SVG files in the root `assets/` directory use hardcoded colors (like `#FFFFFF` or `white`). We must ensure that we preserve the `currentColor` SVG files when consolidating.
3. **Unified Resolution Path**: All UI modules must resolve asset paths through a single standardized helper function, eliminating repetitive `if hasattr(sys, "_MEIPASS"): ...` blocks.
4. **Build & Package Compatibility**: The helper must work seamlessly both during development (source code execution) and in packaged production builds (Windows EXE and Linux AppImage) without changing the build scripts.

## 3. Proposed Changes

### 3.1. File System Cleanup & Merging

1. Copy all contents of `presentation/assets/` into `assets/` at the project root. This ensures that the SVG files optimized with `currentColor` overwrite the static ones at the root.
2. Delete the directory `presentation/assets/`.
3. Delete the directory `presentation/components/assets/`.

### 3.2. Shared Path Helper

We will add a centralized path helper `get_assets_dir()` to `shared/utils/path_utils.py` to handle both frozen (packaged) and unfrozen (dev) path resolution.

#### [MODIFY] [path_utils.py](file:///d:/share_vm/Synapse-Desktop/shared/utils/path_utils.py)
Add the following helper function:

```python
def get_assets_dir() -> Path:
    """
    Get the absolute path to the assets directory, supporting both
    development (source code) and production (packaged AppImage/EXE) environments.
    """
    import sys
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets"
    
    # In development, shared/utils/path_utils.py is at:
    # <project_root>/shared/utils/path_utils.py
    # So .parent.parent.parent is <project_root>
    return Path(__file__).resolve().parent.parent.parent / "assets"
```

### 3.3. Refactoring Codebase References

We will update all files that resolve `assets` paths to import and use `get_assets_dir()`.

#### [MODIFY] [main_window.py](file:///d:/share_vm/Synapse-Desktop/presentation/main_window.py)
Replace the inline path detection:
```python
        # OLD
        if hasattr(sys, "_MEIPASS"):
            self.assets_dir = Path(sys._MEIPASS) / "assets"
        else:
            self.assets_dir = Path(__file__).parent.parent / "assets"
```
with:
```python
        from shared.utils.path_utils import get_assets_dir
        self.assets_dir = get_assets_dir()
```

#### [MODIFY] [theme.py](file:///d:/share_vm/Synapse-Desktop/presentation/config/theme.py)
Replace:
```python
        font_dir = Path(__file__).parent.parent / "assets" / "fonts"
```
with:
```python
        from shared.utils.path_utils import get_assets_dir
        font_dir = get_assets_dir() / "fonts"
```

#### [MODIFY] [theme_qss.py](file:///d:/share_vm/Synapse-Desktop/presentation/config/theme_qss.py)
Replace:
```python
if hasattr(sys, "_MEIPASS"):
    _ASSETS_DIR = os.path.join(sys._MEIPASS, "assets")
else:
    _ASSETS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets"
    )
```
with:
```python
from shared.utils.path_utils import get_assets_dir
_ASSETS_DIR = str(get_assets_dir())
```

#### [MODIFY] [license_dialog.py](file:///d:/share_vm/Synapse-Desktop/presentation/widgets/license_dialog.py)
Replace inline detection with `get_assets_dir()`.

#### [MODIFY] [settings_view_qt.py](file:///d:/share_vm/Synapse-Desktop/presentation/views/settings/settings_view_qt.py)
Replace inline detection with `get_assets_dir()`.

#### [MODIFY] [ui_builder.py](file:///d:/share_vm/Synapse-Desktop/presentation/views/context/ui_builder.py)
Replace all local definitions of `assets_dir` with `get_assets_dir()`.

#### [MODIFY] [tag_chips_widget.py](file:///d:/share_vm/Synapse-Desktop/presentation/components/tag_chips_widget.py)
Replace:
```python
    ASSETS_DIR = Path(sys._MEIPASS) / "assets"
    # ...
    ASSETS_DIR = Path(__file__).parent.parent / "assets"
```
with:
```python
from shared.utils.path_utils import get_assets_dir
ASSETS_DIR = get_assets_dir()
```

#### [MODIFY] [preset_widget.py](file:///d:/share_vm/Synapse-Desktop/presentation/components/preset_widget.py)
Replace:
```python
            self._assets_dir = os.path.join(sys._MEIPASS, "assets")
            # ...
```
with:
```python
        from shared.utils.path_utils import get_assets_dir
        self._assets_dir = str(get_assets_dir())
```

#### [MODIFY] [file_tree_delegate.py](file:///d:/share_vm/Synapse-Desktop/presentation/components/file_tree/file_tree_delegate.py)
Replace:
```python
    ASSETS_DIR = Path(sys._MEIPASS) / "assets"
    # ...
    ASSETS_DIR = Path(__file__).parent.parent.parent.parent / "assets"
```
with:
```python
from shared.utils.path_utils import get_assets_dir
ASSETS_DIR = get_assets_dir()
```

#### [MODIFY] [file_tree_widget.py](file:///d:/share_vm/Synapse-Desktop/presentation/components/file_tree/file_tree_widget.py)
Replace inline detection of `assets_dir` with `get_assets_dir()`.

#### [MODIFY] [dialogs_qt.py](file:///d:/share_vm/Synapse-Desktop/presentation/components/dialogs/dialogs_qt.py)
Replace:
```python
        assets_dir = Path(__file__).parent.parent.parent.parent / "assets"
```
with:
```python
        from shared.utils.path_utils import get_assets_dir
        assets_dir = get_assets_dir()
```

## 4. Verification Plan

### 4.1. Automated Tests
Run unit tests to ensure that the code refactoring hasn't broken the application startup, fonts, or stylesheets:
```bash
pytest tests/ -v
```

### 4.2. Manual Verification
1. Run the application from source code (`python main_window.py` or `./start.sh`) and verify:
   - No errors in startup logs.
   - UI fonts are correctly loaded (Cascadia Code in code panes and IBM Plex Sans in labels/buttons).
   - Icons on the tab bar, toolbar, file tree, settings panel are visible, properly colored, and responsive.
2. Build the Windows EXE to ensure packaging handles the new setup perfectly:
   ```powershell
   .\build-windows.ps1 -NoLicense
   ```
3. Run the packaged executable and verify that all assets (fonts, icons, window icon) render properly.
