# Quick Reference Card

## 🎨 Design System Cheat Sheet

### Colors
```python
from core.theme import ThemeColors

ThemeColors.PRIMARY         # #3B82F6 - Blue (buttons, focus)
ThemeColors.PRIMARY_HOVER   # #2563EB - Darker blue (hover)
ThemeColors.BG_PAGE         # #0F172A - Main background
ThemeColors.BG_SURFACE      # #1E293B - Cards, panels
ThemeColors.TEXT_PRIMARY    # #F1F5F9 - Main text
ThemeColors.TEXT_SECONDARY  # #94A3B8 - Muted text
ThemeColors.BORDER          # #334155 - Borders
ThemeColors.BORDER_FOCUS    # #3B82F6 - Focus borders
ThemeColors.SUCCESS         # #10B981 - Green
ThemeColors.WARNING         # #F59E0B - Amber
ThemeColors.ERROR           # #EF4444 - Red
```

### Typography
```python
from core.theme import ThemeFonts

# Load fonts first (in main window)
ThemeFonts.load_fonts()

# Apply fonts
widget.setFont(ThemeFonts.HEADING_LARGE)   # 18px, Bold
widget.setFont(ThemeFonts.HEADING_MEDIUM)  # 14px, Bold
widget.setFont(ThemeFonts.HEADING_SMALL)   # 12px, DemiBold
widget.setFont(ThemeFonts.BODY_LARGE)      # 12px, Normal
widget.setFont(ThemeFonts.BODY_MEDIUM)     # 11px, Normal
widget.setFont(ThemeFonts.BODY_SMALL)      # 10px, Normal
widget.setFont(ThemeFonts.CODE)            # 10px, Mono
```

### Spacing
```python
from core.theme import ThemeSpacing

ThemeSpacing.XS    # 4px
ThemeSpacing.SM    # 8px
ThemeSpacing.MD    # 12px
ThemeSpacing.LG    # 16px
ThemeSpacing.XL    # 20px
ThemeSpacing.XXL   # 24px
```

### Border Radius
```python
from core.theme import ThemeRadius

ThemeRadius.SM   # 4px
ThemeRadius.MD   # 6px
ThemeRadius.LG   # 8px
ThemeRadius.XL   # 12px
```

### Cursor Pointer
```python
from PySide6.QtCore import Qt

button.setCursor(Qt.CursorShape.PointingHandCursor)
```

### Button Styles
```python
# Primary button (default)
button = QPushButton("Click Me")

# Flat button (secondary)
button = QPushButton("Cancel")
button.setProperty("class", "flat")
```

### Tooltips
```python
button.setToolTip("This is a tooltip")
```

---

## 📝 Common Patterns

### Create a Styled Button
```python
from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt

button = QPushButton("Action")
button.setCursor(Qt.CursorShape.PointingHandCursor)
button.setToolTip("Perform action (Ctrl+A)")
```

### Create a Heading Label
```python
from PySide6.QtWidgets import QLabel
from core.theme import ThemeFonts

label = QLabel("Section Title")
label.setFont(ThemeFonts.HEADING_MEDIUM)
```

### Create a Styled Input
```python
from PySide6.QtWidgets import QLineEdit

input_field = QLineEdit()
input_field.setPlaceholderText("Enter text...")
# Styling applied automatically via global stylesheet
```

### Create a Code Label
```python
from PySide6.QtWidgets import QLabel
from core.theme import ThemeFonts

path_label = QLabel("/home/user/project")
path_label.setFont(ThemeFonts.CODE)
```

---

## 🎯 Component Checklist

When creating a new component:

- [ ] Apply appropriate font (HEADING, BODY, or CODE)
- [ ] Add cursor pointer to clickable elements
- [ ] Add tooltips to buttons
- [ ] Use ThemeColors for colors
- [ ] Use ThemeSpacing for margins/padding
- [ ] Use ThemeRadius for border radius
- [ ] Test hover states
- [ ] Test focus states (for inputs)

---

## 🚀 Quick Commands

### Run App
```bash
cd /home/hao/Desktop/labs/Synapse-Desktop
source .venv/bin/activate
python3 main_window.py
```

### Run Tests
```bash
source .venv/bin/activate
pytest tests/ -v
```

### Type Check
```bash
pyrefly check
```

---

## 📚 Documentation

| File | Purpose |
|------|---------|
| `MASTER.md` | Global design rules |
| `IMPLEMENTATION_GUIDE.md` | Code examples |
| `MIGRATION_GUIDE.md` | Current → New |
| `KEYBOARD_SHORTCUTS.md` | Shortcuts guide |
| `VISUAL_CHANGES.md` | What changed visually |
| `PHASE_1_2_COMPLETE.md` | Implementation summary |

---

## 🎨 Style Examples

### Primary Button
```python
btn = QPushButton("Copy Context")
btn.setCursor(Qt.CursorShape.PointingHandCursor)
btn.setToolTip("Copy selected files (Ctrl+C)")
# Automatically styled by global stylesheet
```

### Secondary Button
```python
btn = QPushButton("Cancel")
btn.setProperty("class", "flat")
btn.setCursor(Qt.CursorShape.PointingHandCursor)
```

### Input with Focus
```python
input_field = QLineEdit()
input_field.setPlaceholderText("Search...")
# Focus state (blue border) applied automatically
```

### Heading
```python
title = QLabel("Context View")
title.setFont(ThemeFonts.HEADING_MEDIUM)
```

### Muted Text
```python
hint = QLabel("Select files to include")
hint.setProperty("class", "muted")
```

---

## ⚡ Performance Tips

- Load fonts once at startup (already done in `main_window.py`)
- Use global stylesheet (already applied)
- Reuse font objects (already defined in `ThemeFonts`)
- Use `setProperty("class", "...")` for style variants

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Fonts not loading | Check `assets/fonts/` has 4 .ttf files |
| Styles not applying | Restart app, check stylesheet loaded |
| Cursor not changing | Add `.setCursor(Qt.CursorShape.PointingHandCursor)` |
| Colors wrong | Use `ThemeColors.*` constants |
| Hover not working | Check global stylesheet applied |

---

## 📞 Need Help?

1. Check `IMPLEMENTATION_GUIDE.md` for detailed examples
2. Check `MIGRATION_GUIDE.md` for migration steps
3. Check `VISUAL_CHANGES.md` to see what changed
4. Check `MASTER.md` for design rules

---

**Keep this card handy when developing! 📌**
