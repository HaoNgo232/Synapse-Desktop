# UI/UX Redesign Proposal: Overwrite Desktop

Chuyển đổi giao diện từ **Swiss Professional Light** sang **Dark Mode OLED** - phong cách chuẩn cho Developer Tools.

![Mockup thiết kế mới](/home/hao/.gemini/antigravity/brain/4c71b9ac-4ec0-440d-91d7-d5597b41b9c0/overwrite_redesign_mockup_1766111275610.png)

---

## Design System Mới

### Color Palette (Dark Mode)

| Role | Hex | Mô tả |
|------|-----|-------|
| **Primary** | `#3B82F6` | Blue 500 - Focus, CTAs |
| **Background Page** | `#0F172A` | Slate 900 - OLED deep black |
| **Background Surface** | `#1E293B` | Slate 800 - Cards, panels |
| **Background Elevated** | `#334155` | Slate 700 - Hover states |
| **Text Primary** | `#F1F5F9` | Slate 100 - Main text |
| **Text Secondary** | `#94A3B8` | Slate 400 - Muted |
| **Border** | `#334155` | Slate 700 - Subtle borders |
| **Success** | `#10B981` | Emerald 500 |
| **Error** | `#EF4444` | Red 500 |

### Typography

```
Heading: Space Grotesk (500, 600, 700)
Body: DM Sans (400, 500)
Code: Fira Code (ligatures enabled)
```

---

## Component Changes

### 1. Tabs (Context / Apply / Settings)

**Hiện tại:** Tabs màu nhạt trên nền trắng
**Đề xuất:** Underline tabs với primary color highlight

### 2. File Tree

**Hiện tại:** Nền trắng, icons mặc định
**Đề xuất:** 
- Nền dark (`#1E293B`)
- Folder icons: Amber (`#F59E0B`)
- File icons: Slate 400
- Hover: Background lighten 5%

### 3. Diff Viewer

**Hiện tại:** Light mode colors
**Đề xuất:**
- Added: `#052E16` (bg) + `#86EFAC` (text)
- Removed: `#450A0A` (bg) + `#FCA5A5` (text)
- Context: Transparent với text muted

### 4. Buttons

**Primary:** `#3B82F6` bg, white text, rounded-lg
**Secondary:** Transparent, border `#334155`, text `#F1F5F9`

---

## Files Cần Sửa

| File | Thay đổi |
|------|----------|
| [theme.py](file:///home/hao/Desktop/labs/overwrite-new/core/theme.py) | Cập nhật toàn bộ color palette |
| [diff_viewer.py](file:///home/hao/Desktop/labs/overwrite-new/components/diff_viewer.py) | Update DiffColors class |
| [file_tree.py](file:///home/hao/Desktop/labs/overwrite-new/components/file_tree.py) | Update icon colors |
| [main.py](file:///home/hao/Desktop/labs/overwrite-new/main.py) | Update app theme |

---

## Lợi ích

1. **Giảm mỏi mắt** - Dark mode chuẩn cho developer tools
2. **Chuyên nghiệp hơn** - Giống VS Code, JetBrains IDEs
3. **OLED friendly** - Tiết kiệm pin trên màn hình OLED
4. **Accessibility** - WCAG AAA contrast ratios
