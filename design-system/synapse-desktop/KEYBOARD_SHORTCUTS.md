# Keyboard Shortcuts - Synapse Desktop

> **Design Principle:** Developer tools MUST have comprehensive keyboard shortcuts.  
> Power users should be able to perform all actions without touching the mouse.

---

## 🎯 Essential Shortcuts (Implement First)

### File Operations
| Shortcut | Action | Priority |
|----------|--------|----------|
| `Ctrl+O` | Open Workspace | ⭐⭐⭐ |
| `Ctrl+W` | Close Workspace | ⭐⭐ |
| `Ctrl+R` | Refresh File Tree | ⭐⭐⭐ |
| `Ctrl+F` | Search Files | ⭐⭐⭐ |
| `Ctrl+Shift+F` | Search in Files | ⭐⭐ |

### Context Operations
| Shortcut | Action | Priority |
|----------|--------|----------|
| `Ctrl+C` | Copy Context | ⭐⭐⭐ |
| `Ctrl+Shift+C` | Copy Smart Context | ⭐⭐⭐ |
| `Ctrl+Shift+D` | Copy Diff Only | ⭐⭐ |
| `Ctrl+A` | Select All Files | ⭐⭐ |
| `Ctrl+Shift+A` | Deselect All | ⭐⭐ |

### Apply Operations
| Shortcut | Action | Priority |
|----------|--------|----------|
| `Ctrl+V` | Paste & Preview OPX | ⭐⭐⭐ |
| `Ctrl+Enter` | Apply Changes | ⭐⭐⭐ |
| `Ctrl+Z` | Undo Last Apply | ⭐⭐⭐ |
| `Ctrl+Shift+Z` | Redo | ⭐⭐ |
| `Escape` | Cancel Preview | ⭐⭐⭐ |

### Navigation
| Shortcut | Action | Priority |
|----------|--------|----------|
| `Ctrl+1` | Go to Context Tab | ⭐⭐⭐ |
| `Ctrl+2` | Go to Apply Tab | ⭐⭐⭐ |
| `Ctrl+3` | Go to History Tab | ⭐⭐ |
| `Ctrl+4` | Go to Logs Tab | ⭐ |
| `Ctrl+Tab` | Next Tab | ⭐⭐ |
| `Ctrl+Shift+Tab` | Previous Tab | ⭐⭐ |

### Tree Navigation
| Shortcut | Action | Priority |
|----------|--------|----------|
| `↑` / `↓` | Navigate Files | ⭐⭐⭐ |
| `←` / `→` | Collapse/Expand Folder | ⭐⭐⭐ |
| `Space` | Toggle Selection | ⭐⭐⭐ |
| `Ctrl+↑` / `Ctrl+↓` | Jump to Parent/Child | ⭐⭐ |
| `Home` | Jump to Top | ⭐⭐ |
| `End` | Jump to Bottom | ⭐⭐ |

### Application
| Shortcut | Action | Priority |
|----------|--------|----------|
| `Ctrl+,` | Open Settings | ⭐⭐⭐ |
| `Ctrl+Shift+P` | Command Palette | ⭐⭐ |
| `F1` | Help / Documentation | ⭐⭐ |
| `Ctrl+Q` | Quit Application | ⭐⭐⭐ |

---

## 🔧 Implementation Guide

### 1. Define Shortcuts in Config

**Create `config/shortcuts.py`:**

```python
from PySide6.QtGui import QKeySequence
from PySide6.QtCore import Qt

class Shortcuts:
    """Keyboard shortcuts configuration"""
    
    # File Operations
    OPEN_WORKSPACE = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_O)
    CLOSE_WORKSPACE = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_W)
    REFRESH_TREE = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_R)
    SEARCH_FILES = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_F)
    
    # Context Operations
    COPY_CONTEXT = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_C)
    COPY_SMART = QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_C)
    COPY_DIFF = QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_D)
    SELECT_ALL = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_A)
    
    # Apply Operations
    PASTE_OPX = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_V)
    APPLY_CHANGES = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Return)
    UNDO = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Z)
    CANCEL = QKeySequence(Qt.Key.Key_Escape)
    
    # Navigation
    TAB_CONTEXT = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_1)
    TAB_APPLY = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_2)
    TAB_HISTORY = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_3)
    TAB_LOGS = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_4)
    
    # Application
    SETTINGS = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Comma)
    QUIT = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Q)
```

### 2. Register Shortcuts in Main Window

**Update `main_window.py`:**

```python
from PySide6.QtGui import QShortcut
from config.shortcuts import Shortcuts

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._setup_shortcuts()
    
    def _setup_shortcuts(self):
        """Register all keyboard shortcuts"""
        
        # File Operations
        QShortcut(Shortcuts.OPEN_WORKSPACE, self, self._on_open_workspace)
        QShortcut(Shortcuts.REFRESH_TREE, self, self._on_refresh_tree)
        QShortcut(Shortcuts.SEARCH_FILES, self, self._on_search_files)
        
        # Context Operations
        QShortcut(Shortcuts.COPY_CONTEXT, self, self._on_copy_context)
        QShortcut(Shortcuts.COPY_SMART, self, self._on_copy_smart)
        QShortcut(Shortcuts.SELECT_ALL, self, self._on_select_all)
        
        # Apply Operations
        QShortcut(Shortcuts.PASTE_OPX, self, self._on_paste_opx)
        QShortcut(Shortcuts.APPLY_CHANGES, self, self._on_apply_changes)
        QShortcut(Shortcuts.UNDO, self, self._on_undo)
        QShortcut(Shortcuts.CANCEL, self, self._on_cancel)
        
        # Navigation
        QShortcut(Shortcuts.TAB_CONTEXT, self, lambda: self.tabs.setCurrentIndex(0))
        QShortcut(Shortcuts.TAB_APPLY, self, lambda: self.tabs.setCurrentIndex(1))
        QShortcut(Shortcuts.TAB_HISTORY, self, lambda: self.tabs.setCurrentIndex(2))
        
        # Application
        QShortcut(Shortcuts.SETTINGS, self, self._on_open_settings)
        QShortcut(Shortcuts.QUIT, self, self.close)
    
    def _on_open_workspace(self):
        """Handle Ctrl+O"""
        # Implementation
        pass
    
    def _on_copy_context(self):
        """Handle Ctrl+C"""
        # Implementation
        pass
    
    # ... other handlers
```

### 3. Add Tooltips with Shortcuts

**Update button creation:**

```python
from config.shortcuts import Shortcuts

# Before
copy_button = QPushButton("Copy Context")

# After
copy_button = QPushButton("Copy Context")
copy_button.setToolTip(f"Copy selected files to clipboard ({Shortcuts.COPY_CONTEXT.toString()})")
copy_button.setShortcut(Shortcuts.COPY_CONTEXT)
```

### 4. Show Shortcuts in UI

**Create shortcuts help dialog:**

```python
class ShortcutsDialog(QDialog):
    """Display all keyboard shortcuts"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(self)
        
        # Create table
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Action", "Shortcut"])
        
        shortcuts = [
            ("Open Workspace", "Ctrl+O"),
            ("Copy Context", "Ctrl+C"),
            ("Copy Smart Context", "Ctrl+Shift+C"),
            ("Apply Changes", "Ctrl+Enter"),
            ("Undo", "Ctrl+Z"),
            # ... add all shortcuts
        ]
        
        table.setRowCount(len(shortcuts))
        for i, (action, shortcut) in enumerate(shortcuts):
            table.setItem(i, 0, QTableWidgetItem(action))
            table.setItem(i, 1, QTableWidgetItem(shortcut))
        
        layout.addWidget(table)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
```

**Add menu item:**

```python
# In main_window.py
help_menu = self.menuBar().addMenu("Help")
shortcuts_action = help_menu.addAction("Keyboard Shortcuts")
shortcuts_action.setShortcut(QKeySequence(Qt.Key.Key_F1))
shortcuts_action.triggered.connect(self._show_shortcuts_dialog)

def _show_shortcuts_dialog(self):
    dialog = ShortcutsDialog(self)
    dialog.exec()
```

---

## 🎨 Visual Indicators

### 1. Shortcut Hints in Buttons

```python
# Show shortcut in button text
button.setText("Copy Context (Ctrl+C)")

# Or in tooltip only (cleaner)
button.setText("Copy Context")
button.setToolTip("Copy selected files to clipboard\nShortcut: Ctrl+C")
```

### 2. Status Bar Hints

```python
# Show current context shortcuts in status bar
self.statusBar().showMessage("Ctrl+C: Copy | Ctrl+Shift+C: Smart Copy | Ctrl+V: Apply")
```

### 3. Context-Aware Hints

```python
# Change hints based on current tab
def _on_tab_changed(self, index):
    if index == 0:  # Context tab
        self.statusBar().showMessage("Ctrl+C: Copy | Ctrl+A: Select All | Ctrl+F: Search")
    elif index == 1:  # Apply tab
        self.statusBar().showMessage("Ctrl+V: Paste | Ctrl+Enter: Apply | Esc: Cancel")
    elif index == 2:  # History tab
        self.statusBar().showMessage("Ctrl+Z: Undo | Enter: View Details")
```

---

## 🧪 Testing Checklist

After implementing shortcuts:

### Functionality
- [ ] All shortcuts work as expected
- [ ] No conflicts between shortcuts
- [ ] Shortcuts work in all tabs
- [ ] Shortcuts respect focus (e.g., Ctrl+C in text field copies text, not context)

### Discoverability
- [ ] Tooltips show shortcuts
- [ ] Help dialog lists all shortcuts
- [ ] Status bar shows context-aware hints
- [ ] Menu items show shortcuts

### Accessibility
- [ ] Tab order logical
- [ ] Focus indicators visible
- [ ] Shortcuts don't conflict with screen readers
- [ ] All actions accessible via keyboard

### Platform Compatibility
- [ ] Shortcuts work on Linux
- [ ] Shortcuts work on Windows
- [ ] Shortcuts work on macOS (Cmd instead of Ctrl)

---

## 🍎 macOS Considerations

**Detect platform and adjust:**

```python
import sys
from PySide6.QtCore import Qt

def get_modifier():
    """Get platform-specific modifier key"""
    if sys.platform == "darwin":  # macOS
        return Qt.Modifier.META  # Cmd key
    else:  # Linux, Windows
        return Qt.Modifier.CTRL

# Usage
COPY_CONTEXT = QKeySequence(get_modifier() | Qt.Key.Key_C)
```

**Display shortcuts correctly:**

```python
def format_shortcut(shortcut: QKeySequence) -> str:
    """Format shortcut for display"""
    text = shortcut.toString()
    if sys.platform == "darwin":
        text = text.replace("Ctrl", "Cmd")
        text = text.replace("Alt", "Option")
    return text

# Usage
tooltip = f"Copy Context ({format_shortcut(Shortcuts.COPY_CONTEXT)})"
```

---

## 📚 Best Practices

### 1. Consistency
- Use standard shortcuts (Ctrl+C, Ctrl+V, Ctrl+Z)
- Follow platform conventions
- Group related shortcuts (Ctrl+C, Ctrl+Shift+C)

### 2. Discoverability
- Show shortcuts in tooltips
- Provide help dialog (F1)
- Use status bar for hints

### 3. Conflicts
- Don't override system shortcuts
- Respect text editing shortcuts in input fields
- Test with screen readers

### 4. Documentation
- Document all shortcuts in README
- Include in user guide
- Show in first-run tutorial

---

## ✅ Implementation Checklist

- [ ] Create `config/shortcuts.py`
- [ ] Register shortcuts in `main_window.py`
- [ ] Add tooltips with shortcuts to all buttons
- [ ] Create shortcuts help dialog (F1)
- [ ] Add status bar hints
- [ ] Test all shortcuts
- [ ] Handle macOS differences
- [ ] Document in README
- [ ] Add to user guide

---

**Priority:** ⭐⭐⭐ High - Essential for developer tool UX

**Estimated Time:** 2-3 hours for full implementation

**Impact:** Massive - Power users will love it!
