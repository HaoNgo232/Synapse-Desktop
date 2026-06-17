# Assets Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate all duplicate asset directories (`presentation/assets/` and `presentation/components/assets/`) into a single root `assets/` directory and standardize path resolution across the application.

**Architecture:** Create a central path resolver function `get_assets_dir() -> Path` in `shared/utils/path_utils.py` that handles both development environments and PyInstaller packaged environments (`sys.frozen`). Refactor all components to resolve asset files through this helper.

**Tech Stack:** Python 3.10+, PySide6, Pytest.

## Global Constraints

- **Single Source of Truth**: Only `assets/` at the project root will exist. All duplicated asset directories must be deleted.
- **Support for Dynamic Styling**: The SVG files in `presentation/assets/` use `stroke="currentColor"`, which is required by `create_colored_icon()` to style icons dynamically. Keep these currentColor SVG versions.
- **Unified Resolution Path**: All UI modules must resolve asset paths through a single standardized helper function.
- **Build & Package Compatibility**: The helper must work seamlessly both during development and in packaged production builds.

---

### Task 1: Create Centralized Asset Path Helper and Unit Tests

**Files:**
- Modify: `shared/utils/path_utils.py`
- Modify: `tests/test_path_utils.py`

**Interfaces:**
- Produces: `get_assets_dir() -> Path`

- [ ] **Step 1: Write failing tests for get_assets_dir**
  Add test methods to `tests/test_path_utils.py` to assert correct asset directory resolution under normal development and packaged (frozen) scenarios.
  
  Add to `tests/test_path_utils.py`:
  ```python
  def test_get_assets_dir_development(self):
      """Test that get_assets_dir returns the project-root assets directory during dev."""
      from shared.utils.path_utils import get_assets_dir
      import sys
      
      # Ensure frozen is patched to False
      orig_frozen = getattr(sys, "frozen", None)
      if hasattr(sys, "frozen"):
          del sys.frozen
          
      try:
          assets_dir = get_assets_dir()
          assert assets_dir.exists()
          assert assets_dir.is_dir()
          assert (assets_dir / "icon.ico").exists()
      finally:
          if orig_frozen is not None:
              sys.frozen = orig_frozen

  def test_get_assets_dir_frozen(self):
      """Test that get_assets_dir respects sys._MEIPASS when sys.frozen is True."""
      from shared.utils.path_utils import get_assets_dir
      import sys
      
      orig_frozen = getattr(sys, "frozen", None)
      orig_meipass = getattr(sys, "_MEIPASS", None)
      
      sys.frozen = True
      sys._MEIPASS = "/mock/meipass"
      
      try:
          assets_dir = get_assets_dir()
          assert assets_dir == Path("/mock/meipass/assets")
      finally:
          if orig_frozen is not None:
              sys.frozen = orig_frozen
          else:
              del sys.frozen
              
          if orig_meipass is not None:
              sys._MEIPASS = orig_meipass
          else:
              del sys._MEIPASS
  ```

- [ ] **Step 2: Run tests to verify they fail**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_path_utils.py -v`
  Expected: FAIL (ImportError or AttributeError for get_assets_dir)

- [ ] **Step 3: Implement get_assets_dir in path_utils.py**
  Add the implementation to `shared/utils/path_utils.py`:
  ```python
  def get_assets_dir() -> Path:
      """
      Get the absolute path to the assets directory, supporting both
      development (source code) and production (packaged AppImage/EXE) environments.
      """
      import sys
      if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
          return Path(sys._MEIPASS) / "assets"
      
      return Path(__file__).resolve().parent.parent.parent / "assets"
  ```

- [ ] **Step 4: Run tests to verify they pass**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_path_utils.py -v`
  Expected: PASS

---

### Task 2: Merge Asset Files and Delete Duplicate Folders

**Files:**
- Delete: `presentation/assets/` (recursive)
- Delete: `presentation/components/assets/` (recursive)
- Modify: `assets/` (overwrite with currentColor SVGs)

- [ ] **Step 1: Copy files from presentation/assets/ to assets/ to overwrite static SVGs**
  Run PowerShell commands to copy files:
  ```powershell
  Copy-Item -Path "presentation/assets/*" -Destination "assets" -Recurse -Force
  ```

- [ ] **Step 2: Verify SVGs are overwritten and currentColor is present**
  Check `assets/add.svg` to verify it contains `stroke="currentColor"`.
  Run in terminal:
  ```powershell
  Get-Content assets/add.svg
  ```
  Expected output contains: `stroke="currentColor"`

- [ ] **Step 3: Delete redundant asset folders**
  Run:
  ```powershell
  Remove-Item -Path "presentation/assets" -Recurse -Force
  Remove-Item -Path "presentation/components/assets" -Recurse -Force
  ```

- [ ] **Step 4: Verify folders are removed**
  Check that they do not exist.

---

### Task 3: Refactor Theme Configuration

**Files:**
- Modify: `presentation/config/theme.py`
- Modify: `presentation/config/theme_qss.py`
- Modify: `tests/presentation/test_config_stylesheet.py`

- [ ] **Step 1: Refactor theme.py fonts path**
  Modify `presentation/config/theme.py` to use `get_assets_dir()`:
  ```python
  # Target Content around line 29:
  font_dir = Path(__file__).parent.parent / "assets" / "fonts"
  
  # Replacement Content:
  from shared.utils.path_utils import get_assets_dir
  font_dir = get_assets_dir() / "fonts"
  ```

- [ ] **Step 2: Refactor theme_qss.py asset paths**
  Modify `presentation/config/theme_qss.py` to use `get_assets_dir()`:
  ```python
  # Target Content around line 13-20:
  import sys

  if hasattr(sys, "_MEIPASS"):
      _ASSETS_DIR = os.path.join(sys._MEIPASS, "assets")
  else:
      _ASSETS_DIR = os.path.join(
          os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets"
      )
  
  # Replacement Content:
  from shared.utils.path_utils import get_assets_dir
  _ASSETS_DIR = str(get_assets_dir())
  ```

- [ ] **Step 3: Run existing stylesheet tests**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/presentation/test_config_stylesheet.py -v`
  Expected: PASS

---

### Task 4: Refactor Main Application Window and Widgets

**Files:**
- Modify: `presentation/main_window.py`
- Modify: `presentation/widgets/license_dialog.py`
- Modify: `presentation/views/settings/settings_view_qt.py`

- [ ] **Step 1: Refactor presentation/main_window.py**
  Replace asset path logic:
  ```python
  # Target Content around line 73-77:
          # Xác định đường dẫn thư mục assets (hỗ trợ cả chạy dev và chạy bundle)
          if hasattr(sys, "_MEIPASS"):
              self.assets_dir = Path(sys._MEIPASS) / "assets"
          else:
              self.assets_dir = Path(__file__).parent.parent / "assets"
  
  # Replacement Content:
          from shared.utils.path_utils import get_assets_dir
          self.assets_dir = get_assets_dir()
  ```

- [ ] **Step 2: Refactor presentation/widgets/license_dialog.py**
  Replace asset path logic:
  ```python
  # Target Content around line 40-46:
          from pathlib import Path
          import sys

          if hasattr(sys, "_MEIPASS"):
              assets_dir = Path(sys._MEIPASS) / "assets"
          else:
              assets_dir = Path(__file__).parent.parent.parent / "assets"
  
  # Replacement Content:
          from shared.utils.path_utils import get_assets_dir
          assets_dir = get_assets_dir()
  ```

- [ ] **Step 3: Refactor settings_view_qt.py**
  Replace asset path logic:
  ```python
  # Target Content around line 335-339:
          if hasattr(sys, "_MEIPASS"):
              self.assets_dir = Path(sys._MEIPASS) / "assets"
          else:
              self.assets_dir = Path(__file__).parent.parent.parent.parent / "assets"
  
  # Replacement Content:
          from shared.utils.path_utils import get_assets_dir
          self.assets_dir = get_assets_dir()
  ```

- [ ] **Step 4: Verify compilation & styling**
  Run unit tests to verify:
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v`
  Expected: PASS

---

### Task 5: Refactor UI Components and Views

**Files:**
- Modify: `presentation/views/context/ui_builder.py`
- Modify: `presentation/components/tag_chips_widget.py`
- Modify: `presentation/components/preset_widget.py`

- [ ] **Step 1: Refactor presentation/views/context/ui_builder.py**
  Replace all inline `assets_dir` setups.
  
  Change 1 (around line 122-132):
  ```python
  # Target Content:
          import sys

          if hasattr(sys, "_MEIPASS"):
              assets_dir = os.path.join(sys._MEIPASS, "assets")
          else:
              assets_dir = os.path.join(
                  os.path.dirname(
                      os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                  ),
                  "assets",
              )
  
  # Replacement Content:
          from shared.utils.path_utils import get_assets_dir
          assets_dir = str(get_assets_dir())
  ```
  
  Change 2 (around line 667-679):
  ```python
  # Target Content:
          # Find assets directory
          import sys

          if hasattr(sys, "_MEIPASS"):
              assets_dir = os.path.join(sys._MEIPASS, "assets")
          else:
              assets_dir = os.path.join(
                  os.path.dirname(
                      os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                  ),
                  "assets",
              )
  
  # Replacement Content:
          from shared.utils.path_utils import get_assets_dir
          assets_dir = str(get_assets_dir())
  ```

- [ ] **Step 2: Refactor presentation/components/tag_chips_widget.py**
  Replace `ASSETS_DIR` resolver:
  ```python
  # Target Content around line 35-37:
      ASSETS_DIR = Path(sys._MEIPASS) / "assets"
  except AttributeError:
      ASSETS_DIR = Path(__file__).parent.parent / "assets"
  
  # Replacement Content:
      from shared.utils.path_utils import get_assets_dir
      ASSETS_DIR = get_assets_dir()
  ```

- [ ] **Step 3: Refactor presentation/components/preset_widget.py**
  Replace inline detection:
  ```python
  # Target Content around line 85-94:
          # Lấy đường dẫn đến thư mục assets (hỗ trợ cả môi trường phát triển và đóng gói)
          if hasattr(sys, "_MEIPASS"):
              self._assets_dir = os.path.join(sys._MEIPASS, "assets")
          else:
              self._assets_dir = os.path.join(
                  os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "assets",
              )
  
  # Replacement Content:
          from shared.utils.path_utils import get_assets_dir
          self._assets_dir = str(get_assets_dir())
  ```

---

### Task 6: Refactor File Tree & Dialog Components

**Files:**
- Modify: `presentation/components/file_tree/file_tree_delegate.py`
- Modify: `presentation/components/file_tree/file_tree_widget.py`
- Modify: `presentation/components/dialogs/dialogs_qt.py`

- [ ] **Step 1: Refactor file_tree_delegate.py**
  Replace `ASSETS_DIR` resolver:
  ```python
  # Target Content around line 116-118:
      ASSETS_DIR = Path(sys._MEIPASS) / "assets"
  except AttributeError:
      ASSETS_DIR = Path(__file__).parent.parent.parent.parent / "assets"
  
  # Replacement Content:
      from shared.utils.path_utils import get_assets_dir
      ASSETS_DIR = get_assets_dir()
  ```

- [ ] **Step 2: Refactor file_tree_widget.py**
  Replace inline `assets_dir` resolver:
  ```python
  # Target Content around line 162-166:
              assets_dir = os.path.join(sys._MEIPASS, "assets")
          else:
              assets_dir = os.path.join(
                  os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets"
              )
  
  # Replacement Content:
              from shared.utils.path_utils import get_assets_dir
              assets_dir = str(get_assets_dir())
  ```

- [ ] **Step 3: Refactor dialogs_qt.py**
  Replace inline `assets_dir` resolver:
  ```python
  # Target Content around line 1015:
          assets_dir = Path(__file__).parent.parent.parent.parent / "assets"
  
  # Replacement Content:
          from shared.utils.path_utils import get_assets_dir
          assets_dir = get_assets_dir()
  ```

- [ ] **Step 4: Run all pytest unit tests**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v`
  Expected: PASS
