"""
DiffViewer Component - Hien thi visual diff cho file changes

Su dung difflib de tinh toan diff va Flet components de render.
Mau sac:
- Xanh la (#DCFCE7): Dong duoc them (+)
- Do nhat (#FEE2E2): Dong bi xoa (-)
- Xam (#F3F4F6): Context lines
"""

import difflib
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from core.theme import ThemeColors


class DiffLineType(Enum):
    """
    Loai dong trong diff output.
    - ADDED: Dong duoc them vao (bat dau bang +)
    - REMOVED: Dong bi xoa (bat dau bang -)
    - CONTEXT: Dong khong thay doi (context)
    - HEADER: Header line (@@...@@)
    """

    ADDED = "added"
    REMOVED = "removed"
    CONTEXT = "context"
    HEADER = "header"


@dataclass
class DiffLine:
    """
    Mot dong trong diff output.

    Attributes:
        content: Noi dung dong (bao gom prefix +/-/space)
        line_type: Loai dong (ADDED, REMOVED, CONTEXT, HEADER)
        old_line_no: So dong trong file cu (None neu la dong moi)
        new_line_no: So dong trong file moi (None neu la dong bi xoa)
    """

    content: str
    line_type: DiffLineType
    old_line_no: Optional[int] = None
    new_line_no: Optional[int] = None


class DiffColors:
    """
    Mau sac cho cac loai dong trong diff.
    Dark Mode colors - van xai dark bg voi text mau ro rang.
    """

    ADDED_BG = "#052E16"  # Dark green bg - dong duoc them
    REMOVED_BG = "#450A0A"  # Dark red bg - dong bi xoa
    CONTEXT_BG = "#1E293B"  # Slate 800 - context (same as surface)
    HEADER_BG = "#1E3A5F"  # Dark blue - header @@

    # Text colors for contrast on dark backgrounds
    ADDED_TEXT = "#86EFAC"  # Light green text
    REMOVED_TEXT = "#FCA5A5"  # Light red text
    HEADER_TEXT = "#93C5FD"  # Light blue text


# Maximum lines to process for diff (performance guard)
MAX_DIFF_LINES = 10000
MAX_DIFF_OUTPUT_LINES = 2000


def generate_diff_lines(
    old_content: str, new_content: str, file_path: str = "", context_lines: int = 3
) -> List[DiffLine]:
    """
    Tao danh sach DiffLine tu old va new content.
    Su dung unified_diff de tinh toan thay doi.

    Args:
        old_content: Noi dung file cu (hoac empty string neu tao moi)
        new_content: Noi dung file moi
        file_path: Duong dan file (dung cho header)
        context_lines: So dong context xung quanh thay doi

    Returns:
        List DiffLine de hien thi
    """
    # Split content thanh lines
    old_lines = old_content.splitlines(keepends=True) if old_content else []
    new_lines = new_content.splitlines(keepends=True) if new_content else []
    
    # Guard against very large files
    if len(old_lines) > MAX_DIFF_LINES or len(new_lines) > MAX_DIFF_LINES:
        return [DiffLine(
            content=f"[File too large for diff preview: {len(old_lines)}/{len(new_lines)} lines]",
            line_type=DiffLineType.HEADER
        )]

    # Tao unified diff
    diff_generator = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{file_path}" if file_path else "a/file",
        tofile=f"b/{file_path}" if file_path else "b/file",
        lineterm="",
        n=context_lines,
    )

    # Parse diff output
    result: List[DiffLine] = []
    old_line_no = 0
    new_line_no = 0

    for line in diff_generator:
        # Strip trailing newline for display
        line = line.rstrip("\n\r")

        if line.startswith("@@"):
            # Header line - parse line numbers
            result.append(DiffLine(content=line, line_type=DiffLineType.HEADER))
            # Parse @@ -old_start,old_count +new_start,new_count @@
            # Reset line counters based on header
            try:
                parts = line.split(" ")
                old_range = parts[1][1:]  # Remove -
                new_range = parts[2][1:]  # Remove +
                old_line_no = int(old_range.split(",")[0]) - 1
                new_line_no = int(new_range.split(",")[0]) - 1
            except (IndexError, ValueError):
                pass

        elif line.startswith("---") or line.startswith("+++"):
            # File headers - skip them
            continue

        elif line.startswith("+"):
            # Dong duoc them
            new_line_no += 1
            result.append(
                DiffLine(
                    content=line, line_type=DiffLineType.ADDED, new_line_no=new_line_no
                )
            )

        elif line.startswith("-"):
            # Dong bi xoa
            old_line_no += 1
            result.append(
                DiffLine(
                    content=line,
                    line_type=DiffLineType.REMOVED,
                    old_line_no=old_line_no,
                )
            )

        else:
            # Context line (bat dau bang space)
            old_line_no += 1
            new_line_no += 1
            result.append(
                DiffLine(
                    content=line,
                    line_type=DiffLineType.CONTEXT,
                    old_line_no=old_line_no,
                    new_line_no=new_line_no,
                )
            )
        
        # Early termination for very large diffs
        if len(result) >= MAX_DIFF_OUTPUT_LINES:
            result.append(DiffLine(
                content=f"[... truncated, showing first {MAX_DIFF_OUTPUT_LINES} lines ...]",
                line_type=DiffLineType.HEADER
            ))
            break

    return result


def generate_create_diff_lines(new_content: str, file_path: str = "") -> List[DiffLine]:
    """
    Tao diff lines cho CREATE action (toan bo noi dung la moi).

    Args:
        new_content: Noi dung file moi
        file_path: Duong dan file

    Returns:
        List DiffLine voi tat ca dong la ADDED
    """
    return generate_diff_lines("", new_content, file_path)


def generate_delete_diff_lines(old_content: str, file_path: str = "") -> List[DiffLine]:
    """
    Tao diff lines cho DELETE action (toan bo noi dung bi xoa).

    Args:
        old_content: Noi dung file cu
        file_path: Duong dan file

    Returns:
        List DiffLine voi tat ca dong la REMOVED
    """
    return generate_diff_lines(old_content, "", file_path)

# Legacy Flet DiffViewer class — only defined when flet is installed.
# PySide6 app uses DiffViewerQt from diff_viewer_qt.py instead.
import importlib.util as _importlib_util

def _has_flet() -> bool:
    try:
        return _importlib_util.find_spec("flet") is not None
    except (ValueError, ModuleNotFoundError):
        return False

if _has_flet():
    import flet as ft

    class DiffViewer(ft.Column):
        """
        Flet component de hien thi visual diff (LEGACY — replaced by DiffViewerQt).

        Su dung:
            diff_lines = generate_diff_lines(old, new)
            viewer = DiffViewer(diff_lines)
            page.add(viewer)
        """

        def __init__(
            self,
            diff_lines: List[DiffLine],
            max_height: int = 300,
            show_line_numbers: bool = True,
            **kwargs,
        ):
            """
            Khoi tao DiffViewer.

            Args:
                diff_lines: Danh sach DiffLine tu generate_diff_lines()
                max_height: Chieu cao toi da cua viewer (scroll neu qua dai)
                show_line_numbers: Hien thi so dong hay khong
            """
            super().__init__(**kwargs)

            self.diff_lines = diff_lines
            self.max_height = max_height
            self.show_line_numbers = show_line_numbers

            # Build UI
            self._build_ui()

        def _build_ui(self):
            """Xay dung giao dien diff viewer"""
            self.controls = []

            if not self.diff_lines:
                self.controls.append(
                    ft.Text(
                        "No changes to display",
                        color=ThemeColors.TEXT_MUTED,
                        italic=True,
                        size=12,
                    )
                )
                return

            # Sử dụng ListView thay vì Column để hỗ trợ ảo hóa (virtualization)
            diff_rows = ft.ListView(
                controls=[self._create_diff_row(line) for line in self.diff_lines],
                spacing=0,
                auto_scroll=False,
                expand=True,
            )

            self.controls.append(
                ft.Container(
                    content=diff_rows,
                    height=self.max_height,
                    border=ft.border.all(1, ThemeColors.BORDER),
                    border_radius=4,
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                )
            )

        def _create_diff_row(self, line: DiffLine) -> ft.Container:
            """
            Tao mot row cho mot dong diff.

            Args:
                line: DiffLine object

            Returns:
                Flet Container chua row
            """
            # Chon mau background dua tren loai dong
            bg_color = {
                DiffLineType.ADDED: DiffColors.ADDED_BG,
                DiffLineType.REMOVED: DiffColors.REMOVED_BG,
                DiffLineType.CONTEXT: DiffColors.CONTEXT_BG,
                DiffLineType.HEADER: DiffColors.HEADER_BG,
            }.get(line.line_type, DiffColors.CONTEXT_BG)

            # Chon mau text
            text_color = {
                DiffLineType.ADDED: DiffColors.ADDED_TEXT,
                DiffLineType.REMOVED: DiffColors.REMOVED_TEXT,
                DiffLineType.CONTEXT: ThemeColors.TEXT_SECONDARY,
                DiffLineType.HEADER: DiffColors.HEADER_TEXT,
            }.get(line.line_type, ThemeColors.TEXT_PRIMARY)

            # Build row content
            row_content: List[ft.Control] = []

            # Line numbers (optional)
            if self.show_line_numbers and line.line_type != DiffLineType.HEADER:
                old_no = str(line.old_line_no) if line.old_line_no else ""
                new_no = str(line.new_line_no) if line.new_line_no else ""

                row_content.append(
                    ft.Container(
                        content=ft.Text(
                            old_no,
                            size=11,
                            color=ThemeColors.TEXT_MUTED,
                            font_family="monospace",
                        ),
                        width=35,
                        padding=ft.padding.only(right=4),
                        alignment=ft.Alignment.CENTER_RIGHT,
                    )
                )
                row_content.append(
                    ft.Container(
                        content=ft.Text(
                            new_no,
                            size=11,
                            color=ThemeColors.TEXT_MUTED,
                            font_family="monospace",
                        ),
                        width=35,
                        padding=ft.padding.only(right=8),
                        alignment=ft.Alignment.CENTER_RIGHT,
                        border=ft.border.only(right=ft.BorderSide(1, ThemeColors.BORDER)),
                    )
                )

            # Content
            row_content.append(
                ft.Container(
                    content=ft.Text(
                        line.content,
                        size=12,
                        color=text_color,
                        font_family="monospace",
                        no_wrap=True,
                        overflow=ft.TextOverflow.CLIP,
                    ),
                    expand=True,
                    padding=ft.padding.only(left=8),
                )
            )

            return ft.Container(
                content=ft.Row(
                    controls=row_content,
                    spacing=0,
                ),
                bgcolor=bg_color,
                padding=ft.padding.symmetric(vertical=2, horizontal=4),
            )

        def update_diff(self, diff_lines: List[DiffLine]):
            """
            Cap nhat diff lines va re-render.

            Args:
                diff_lines: Danh sach DiffLine moi
            """
            self.diff_lines = diff_lines
            self._build_ui()
            self.update()
