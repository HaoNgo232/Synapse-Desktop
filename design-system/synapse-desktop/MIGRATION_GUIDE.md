# Migration Guide: Current Theme → Design System

> **Status:** ✅ Your current theme is 95% aligned with the design system!  
> **Action Required:** Minor adjustments only

---

## 🎯 Current vs Design System

### Colors: ✅ Already Aligned!

Your `core/theme.py` already matches the design system perfectly:

| Element | Current (`ThemeColors`) | Design System | Status |
|---------|------------------------|---------------|--------|
| Primary | `#3B82F6` | `#3B82F6` | ✅ Match |
| Background | `#0F172A` | `#0F172A` | ✅ Match |
| Surface | `#1E293B` | `#1E293B` | ✅ Match |
| Text | `#F1F5F9` | `#F1F5F9` | ✅ Match |
| Success | `#10B981` | `#10B981` | ✅ Match |
| Warning | `#F59E0B` | `#F59E0B` | ✅ Match |
| Error | `#EF4444` | `#EF4444` | ✅ Match |

**No changes needed!** Your color palette is already perfect.

---

## 📝 Typography: Action Required

### Current State
Your app likely uses default Qt fonts or system fonts.

### Required Changes

**1. Add Font Files**

Download and add to `assets/fonts/`:
- `JetBrainsMono-Regular.ttf`
- `JetBrainsMono-Bold.ttf`
- `IBMPlexSans-Regular.ttf`
- `IBMPlexSans-SemiBold.ttf`

**2. Update `core/theme.py`**

Add font loading:

```python
from PySide6.QtGui import QFont, QFontDatabase
from pathlib import Path

class ThemeFonts:
    """Typography System"""
    
    @staticmethod
    def load_fonts():
        """Load custom fonts from assets"""
        font_dir = Path(__file__).parent.parent / "assets" / "fonts"
        
        # Load JetBrains Mono
        QFontDatabase.addApplicationFont(str(font_dir / "JetBrainsMono-Regular.ttf"))
        QFontDatabase.addApplicationFont(str(font_dir / "JetBrainsMono-Bold.ttf"))
        
        # Load IBM Plex Sans
        QFontDatabase.addApplicationFont(str(font_dir / "IBMPlexSans-Regular.ttf"))
        QFontDatabase.addApplicationFont(str(font_dir / "IBMPlexSans-SemiBold.ttf"))
    
    # Heading fonts (for titles, section headers)
    HEADING_LARGE = QFont("JetBrains Mono", 18, QFont.Weight.Bold)
    HEADING_MEDIUM = QFont("JetBrains Mono", 14, QFont.Weight.Bold)
    HEADING_SMALL = QFont("JetBrains Mono", 12, QFont.Weight.DemiBold)
    
    # Body fonts (for descriptions, labels)
    BODY_LARGE = QFont("IBM Plex Sans", 12, QFont.Weight.Normal)
    BODY_MEDIUM = QFont("IBM Plex Sans", 11, QFont.Weight.Normal)
    BODY_SMALL = QFont("IBM Plex Sans", 10, QFont.Weight.Normal)
    
    # Code fonts (for file paths, code snippets)
    CODE = QFont("JetBrains Mono", 10, QFont.Weight.Normal)
```

**3. Update `main_window.py`**

Load fonts on startup:

```python
from core.theme import ThemeFonts

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Load custom fonts
        ThemeFonts.load_fonts()
        
        # ... rest of initialization
```

**4. Apply Fonts to Components**

Example for file tree:

```python
from core.theme import ThemeFonts

# In your component initialization
self.file_tree.setFont(ThemeFonts.BODY_MEDIUM)
self.section_header.setFont(ThemeFonts.HEADING_MEDIUM)
self.file_path_label.setFont(ThemeFonts.CODE)
```

---

## 🎨 Component Updates

### 1. Buttons (Minor Polish)

**Current:** Likely using default Qt button styles  
**Recommended:** Add hover states and transitions

**Update `components/` button styles:**

```python
# In your button creation
button.setStyleSheet(f"""
    QPushButton {{
        background-color: {ThemeColors.PRIMARY};
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {ThemeColors.PRIMARY_HOVER};
    }}
    QPushButton:pressed {{
        background-color: #1E40AF;
    }}
""")

# Add pointer cursor
button.setCursor(Qt.CursorShape.PointingHandCursor)
```

### 2. File Tree (Add Hover States)

**Update `components/file_tree.py`:**

```python
self.tree.setStyleSheet(f"""
    QTreeWidget {{
        background-color: {ThemeColors.BG_PAGE};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: 8px;
        padding: 8px;
    }}
    QTreeWidget::item {{
        padding: 6px;
        border-radius: 4px;
    }}
    QTreeWidget::item:hover {{
        background-color: {ThemeColors.BG_SURFACE};
        cursor: pointer;
    }}
    QTreeWidget::item:selected {{
        background-color: {ThemeColors.PRIMARY};
        color: white;
    }}
""")
```

### 3. Input Fields (Add Focus States)

```python
line_edit.setStyleSheet(f"""
    QLineEdit {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: 8px;
        padding: 12px 16px;
    }}
    QLineEdit:focus {{
        border: 2px solid {ThemeColors.BORDER_FOCUS};
        background-color: {ThemeColors.BG_PAGE};
    }}
""")
```

---

## ⚡ Quick Wins (30 Minutes)

### Phase 1: Typography (15 min)
1. Download fonts → `assets/fonts/`
2. Add `ThemeFonts` class to `core/theme.py`
3. Load fonts in `main_window.py`
4. Apply to 3 main components (file tree, buttons, headers)

### Phase 2: Interactions (15 min)
1. Add `cursor: pointer` to all buttons
2. Add hover states to file tree items
3. Add focus states to input fields
4. Add tooltips to main buttons

---

## 🧪 Testing Checklist

After migration:

- [ ] Fonts render correctly (JetBrains Mono for headings)
- [ ] All buttons have hover states
- [ ] File tree items highlight on hover
- [ ] Input fields show focus indicator
- [ ] Cursor changes to pointer on clickable elements
- [ ] Colors remain consistent (no visual regression)
- [ ] Performance unchanged (font loading is fast)

---

## 📦 Font Download Links

**JetBrains Mono:**
- https://fonts.google.com/specimen/JetBrains+Mono
- Download → Select Regular (400) and Bold (700)

**IBM Plex Sans:**
- https://fonts.google.com/specimen/IBM+Plex+Sans
- Download → Select Regular (400) and SemiBold (600)

**Alternative:** Use Google Fonts API (requires internet):
```python
# Not recommended for desktop apps, but possible
# Better to bundle fonts locally
```

---

## 🎯 Priority Order

1. **High Priority (Do First):**
   - ✅ Typography (JetBrains Mono + IBM Plex Sans)
   - ✅ Hover states on buttons
   - ✅ Cursor pointer on clickable elements

2. **Medium Priority (Next):**
   - ✅ Focus states on inputs
   - ✅ Tooltips on buttons
   - ✅ Hover states on file tree

3. **Low Priority (Polish):**
   - ✅ Smooth transitions (200ms)
   - ✅ Loading states
   - ✅ Toast notifications

---

## 🚀 Implementation Example

**Before (Current):**
```python
# components/file_tree.py
self.tree = QTreeWidget()
# Uses default Qt styling
```

**After (Design System):**
```python
# components/file_tree.py
from core.theme import ThemeColors, ThemeFonts

self.tree = QTreeWidget()
self.tree.setFont(ThemeFonts.BODY_MEDIUM)
self.tree.setStyleSheet(f"""
    QTreeWidget {{
        background-color: {ThemeColors.BG_PAGE};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: 8px;
    }}
    QTreeWidget::item:hover {{
        background-color: {ThemeColors.BG_SURFACE};
    }}
    QTreeWidget::item:selected {{
        background-color: {ThemeColors.PRIMARY};
    }}
""")
```

---

## ✅ Summary

**What's Already Good:**
- ✅ Color palette (100% match)
- ✅ Dark mode implementation
- ✅ Semantic color naming

**What Needs Update:**
- 📝 Typography (add custom fonts)
- 🎨 Hover states (add visual feedback)
- 🖱️ Cursor styles (add pointer on clickable)
- 🎯 Focus states (add keyboard navigation indicators)

**Estimated Time:** 30-60 minutes for full migration

**Impact:** High (significantly improves professional appearance)

---

**Next Steps:**

1. Download fonts
2. Update `core/theme.py` with `ThemeFonts`
3. Apply to main components
4. Test and iterate

Need help with any specific component? Let me know!
