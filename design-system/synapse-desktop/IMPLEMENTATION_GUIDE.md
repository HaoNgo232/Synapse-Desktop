# Synapse Desktop - UI Implementation Guide

> **Generated:** 2026-02-14  
> **Design System:** `design-system/synapse-desktop/MASTER.md`

---

## 🎯 Design System Summary

### Core Identity
- **Product Type:** Developer Tool / Code Editor
- **Target Users:** Developers using AI-assisted coding
- **Primary Use Case:** File context management for LLMs
- **Tech Stack:** Python + PySide6

### Visual Language
- **Style:** Vibrant & Block-based (modern, energetic, high contrast)
- **Mood:** Technical, precise, developer-focused
- **Color Strategy:** Dark syntax theme with blue accents
- **Typography:** JetBrains Mono (headings) + IBM Plex Sans (body)

---

## 🎨 Color Palette

```python
# PySide6 Theme Colors (Update in your theme config)
class ThemeColors:
    PRIMARY = "#3B82F6"      # Blue - main accent
    SECONDARY = "#1E293B"    # Dark slate - secondary elements
    CTA = "#2563EB"          # Darker blue - call-to-action buttons
    BACKGROUND = "#0F172A"   # Very dark slate - main background
    TEXT = "#F1F5F9"         # Light slate - primary text
    
    # Additional semantic colors
    SUCCESS = "#10B981"      # Green
    WARNING = "#F59E0B"      # Amber
    ERROR = "#EF4444"        # Red
    INFO = "#3B82F6"         # Blue (same as primary)
```

---

## 📝 Typography

### Font Setup

**Google Fonts Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
```

**PySide6 Font Configuration:**
```python
from PySide6.QtGui import QFont, QFontDatabase

# Load fonts
QFontDatabase.addApplicationFont("path/to/JetBrainsMono.ttf")
QFontDatabase.addApplicationFont("path/to/IBMPlexSans.ttf")

# Heading font (for titles, labels)
heading_font = QFont("JetBrains Mono", 14, QFont.Weight.Bold)

# Body font (for text, descriptions)
body_font = QFont("IBM Plex Sans", 11, QFont.Weight.Normal)

# Code font (for code snippets, file paths)
code_font = QFont("JetBrains Mono", 10, QFont.Weight.Normal)
```

### Type Scale

| Element | Font | Size | Weight |
|---------|------|------|--------|
| H1 (Window Title) | JetBrains Mono | 24px | Bold (700) |
| H2 (Section Header) | JetBrains Mono | 18px | SemiBold (600) |
| H3 (Subsection) | JetBrains Mono | 14px | Medium (500) |
| Body Text | IBM Plex Sans | 11px | Regular (400) |
| Small Text | IBM Plex Sans | 10px | Regular (400) |
| Code/Paths | JetBrains Mono | 10px | Regular (400) |

---

## 🧩 Component Guidelines

### 1. Buttons

**Primary Button (CTA):**
```python
btn_primary = QPushButton("Copy Context")
btn_primary.setStyleSheet("""
    QPushButton {
        background-color: #2563EB;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: 600;
        font-size: 11px;
    }
    QPushButton:hover {
        background-color: #1D4ED8;
    }
    QPushButton:pressed {
        background-color: #1E40AF;
    }
    QPushButton:disabled {
        background-color: #64748B;
        color: #94A3B8;
    }
""")
```

**Secondary Button:**
```python
btn_secondary = QPushButton("Cancel")
btn_secondary.setStyleSheet("""
    QPushButton {
        background-color: transparent;
        color: #3B82F6;
        border: 2px solid #3B82F6;
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: 600;
        font-size: 11px;
    }
    QPushButton:hover {
        background-color: #3B82F610;
    }
""")
```

### 2. File Tree

**Tree Widget Styling:**
```python
tree_widget.setStyleSheet("""
    QTreeWidget {
        background-color: #0F172A;
        color: #F1F5F9;
        border: 1px solid #1E293B;
        border-radius: 8px;
        padding: 8px;
        font-family: 'IBM Plex Sans';
        font-size: 11px;
    }
    QTreeWidget::item {
        padding: 6px;
        border-radius: 4px;
    }
    QTreeWidget::item:hover {
        background-color: #1E293B;
    }
    QTreeWidget::item:selected {
        background-color: #3B82F6;
        color: white;
    }
    QTreeWidget::branch {
        background-color: transparent;
    }
""")
```

### 3. Input Fields

```python
line_edit.setStyleSheet("""
    QLineEdit {
        background-color: #1E293B;
        color: #F1F5F9;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 12px 16px;
        font-size: 11px;
    }
    QLineEdit:focus {
        border: 2px solid #3B82F6;
        background-color: #0F172A;
    }
""")
```

### 4. Cards/Panels

```python
card_widget.setStyleSheet("""
    QWidget {
        background-color: #0F172A;
        border: 1px solid #1E293B;
        border-radius: 12px;
        padding: 24px;
    }
""")
```

### 5. Tabs

```python
tab_widget.setStyleSheet("""
    QTabWidget::pane {
        border: 1px solid #1E293B;
        border-radius: 8px;
        background-color: #0F172A;
    }
    QTabBar::tab {
        background-color: #1E293B;
        color: #94A3B8;
        padding: 12px 24px;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        margin-right: 4px;
        font-weight: 500;
    }
    QTabBar::tab:selected {
        background-color: #3B82F6;
        color: white;
    }
    QTabBar::tab:hover:!selected {
        background-color: #334155;
        color: #F1F5F9;
    }
""")
```

---

## ⚡ Key UX Improvements

### 1. Keyboard Navigation (Critical for Developer Tools)

**Focus States:**
```python
# Add visible focus indicators
widget.setStyleSheet("""
    QWidget:focus {
        border: 2px solid #3B82F6;
        outline: none;
    }
""")
```

**Keyboard Shortcuts:**
```python
# Essential shortcuts for Synapse Desktop
shortcuts = {
    "Ctrl+O": "Open Workspace",
    "Ctrl+C": "Copy Context",
    "Ctrl+V": "Apply OPX",
    "Ctrl+F": "Search Files",
    "Ctrl+Shift+S": "Smart Copy",
    "Ctrl+Z": "Undo Last Apply",
    "Ctrl+,": "Open Settings",
    "F5": "Refresh File Tree",
}
```

### 2. Visual Feedback

**Loading States:**
```python
# Show spinner during token counting
loading_label = QLabel("Counting tokens...")
loading_label.setStyleSheet("""
    QLabel {
        color: #94A3B8;
        font-style: italic;
        padding: 8px;
    }
""")
```

**Success/Error Messages:**
```python
# Success toast
success_msg.setStyleSheet("""
    QLabel {
        background-color: #10B981;
        color: white;
        padding: 12px 16px;
        border-radius: 8px;
        font-weight: 500;
    }
""")

# Error toast
error_msg.setStyleSheet("""
    QLabel {
        background-color: #EF4444;
        color: white;
        padding: 12px 16px;
        border-radius: 8px;
        font-weight: 500;
    }
""")
```

### 3. Hover States

**All interactive elements must have:**
- `cursor: pointer` equivalent in Qt
- Visual feedback (color change, shadow, etc.)
- Smooth transitions (200ms)

```python
button.setCursor(Qt.CursorShape.PointingHandCursor)
```

### 4. Accessibility

**Minimum Requirements:**
- All buttons have tooltips
- Focus states visible
- Color contrast 4.5:1 minimum
- Keyboard shortcuts documented

```python
button.setToolTip("Copy selected files to clipboard (Ctrl+C)")
```

---

## 🚀 Quick Wins (Implement First)

### Priority 1: Visual Polish
1. ✅ Update color palette to match design system
2. ✅ Apply JetBrains Mono + IBM Plex Sans fonts
3. ✅ Add hover states to all buttons/cards
4. ✅ Increase border radius (8px for buttons, 12px for cards)

### Priority 2: Interaction
1. ✅ Add `cursor: pointer` to all clickable elements
2. ✅ Implement keyboard shortcuts
3. ✅ Add focus indicators
4. ✅ Add loading states for async operations

### Priority 3: Feedback
1. ✅ Toast notifications for success/error
2. ✅ Progress indicators for long operations
3. ✅ Tooltips on all buttons
4. ✅ Status bar with context info

---

## 📦 Icon System

**Recommended Icon Library:** [Lucide Icons](https://lucide.dev/) or [Heroicons](https://heroicons.com/)

**Common Icons Needed:**
- Folder (open/closed)
- File types (py, js, json, etc.)
- Copy, Paste, Undo
- Settings, Help, Info
- Check, X, Warning
- Search, Filter
- Expand, Collapse

**Implementation:**
```python
from PySide6.QtGui import QIcon

# Load SVG icons
icon_copy = QIcon("icons/copy.svg")
button.setIcon(icon_copy)
button.setIconSize(QSize(16, 16))
```

---

## 🎯 Design System Usage

### When Building New Features

1. **Check page-specific overrides first:**
   - `design-system/synapse-desktop/pages/[feature].md`
   
2. **If no override exists, use MASTER.md:**
   - `design-system/synapse-desktop/MASTER.md`

3. **Create page override if needed:**
   ```bash
   python3 .agent/.shared/ui-ux-pro-max/scripts/search.py \
     "diff viewer code comparison" \
     --design-system --persist \
     -p "Synapse Desktop" \
     --page "diff-viewer"
   ```

### Example: Building a New Tab

```python
# 1. Read design system
# design-system/synapse-desktop/MASTER.md

# 2. Apply colors
tab_widget.setStyleSheet(f"""
    QWidget {{
        background-color: {ThemeColors.BACKGROUND};
        color: {ThemeColors.TEXT};
    }}
""")

# 3. Apply typography
title_label.setFont(QFont("JetBrains Mono", 18, QFont.Weight.Bold))
body_label.setFont(QFont("IBM Plex Sans", 11))

# 4. Add interactions
button.setCursor(Qt.CursorShape.PointingHandCursor)
button.setToolTip("Perform action (Ctrl+Enter)")
```

---

## 📚 References

- **Design System Master:** `design-system/synapse-desktop/MASTER.md`
- **Google Fonts:** [JetBrains Mono + IBM Plex Sans](https://fonts.google.com/share?selection.family=IBM+Plex+Sans:wght@300;400;500;600;700|JetBrains+Mono:wght@400;500;600;700)
- **Icons:** [Lucide](https://lucide.dev/) | [Heroicons](https://heroicons.com/)
- **Color Palette:** Blue (#3B82F6) + Dark Slate (#0F172A)

---

## ✅ Pre-Delivery Checklist

Before committing UI changes:

- [ ] Colors match design system
- [ ] Fonts are JetBrains Mono (headings) + IBM Plex Sans (body)
- [ ] All buttons have hover states
- [ ] All clickable elements have pointer cursor
- [ ] Focus states visible for keyboard navigation
- [ ] Tooltips on all interactive elements
- [ ] Loading states for async operations
- [ ] Error/success feedback implemented
- [ ] Keyboard shortcuts documented
- [ ] No emojis used as icons (use SVG)
- [ ] Border radius consistent (8px buttons, 12px cards)
- [ ] Transitions smooth (200ms)

---

**Next Steps:**

1. Review current UI components in `views/` and `components/`
2. Identify components that need updates
3. Apply design system incrementally (start with high-impact areas)
4. Test keyboard navigation and accessibility
5. Document any custom patterns in page-specific overrides
