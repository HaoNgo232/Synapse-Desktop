"""
Apply View (PySide6) - Tab để paste OPX và apply changes.
"""

from pathlib import Path
from typing import Optional, List, Callable

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QFrame,
    QMessageBox,
)
from PySide6.QtCore import Qt, Slot

from core.theme import ThemeColors
from core.opx_parser import parse_opx_response
from core.file_actions import apply_file_actions, ActionResult
from services.clipboard_utils import copy_to_clipboard, get_clipboard_text
from services.history_service import add_history_entry
from services.preview_analyzer import (
    analyze_file_actions,
    PreviewRow,
    PreviewData,
    generate_preview_diff_lines,
)
from services.error_context import (
    build_error_context_for_ai,
    build_general_error_context,
    ApplyRowResult,
)
from components.diff_viewer_qt import DiffViewerWidget
from components.toast_qt import toast_success, toast_error


class ApplyViewColors:
    """Enhanced colors cho Apply View."""

    BG_CARD = "#1E293B"
    BG_EXPANDED = "#0F172A"
    ACTION_CREATE = "#22C55E"
    ACTION_CREATE_BG = "#052E16"
    ACTION_MODIFY = "#3B82F6"
    ACTION_MODIFY_BG = "#172554"
    ACTION_REWRITE = "#F59E0B"
    ACTION_REWRITE_BG = "#422006"
    ACTION_DELETE = "#EF4444"
    ACTION_DELETE_BG = "#450A0A"
    ACTION_RENAME = "#A855F7"
    ACTION_RENAME_BG = "#3B0764"
    SUCCESS_TEXT = "#4ADE80"
    ERROR_TEXT = "#FCA5A5"
    DIFF_ADD = "#4ADE80"
    DIFF_REMOVE = "#F87171"


# Action → color mapping
ACTION_COLORS = {
    "create": (ApplyViewColors.ACTION_CREATE, ApplyViewColors.ACTION_CREATE_BG),
    "modify": (ApplyViewColors.ACTION_MODIFY, ApplyViewColors.ACTION_MODIFY_BG),
    "patch": (ApplyViewColors.ACTION_MODIFY, ApplyViewColors.ACTION_MODIFY_BG),
    "rewrite": (ApplyViewColors.ACTION_REWRITE, ApplyViewColors.ACTION_REWRITE_BG),
    "delete": (ApplyViewColors.ACTION_DELETE, ApplyViewColors.ACTION_DELETE_BG),
    "rename": (ApplyViewColors.ACTION_RENAME, ApplyViewColors.ACTION_RENAME_BG),
}


class ApplyViewQt(QWidget):
    """View cho Apply tab - PySide6 version."""

    def __init__(
        self,
        get_workspace: Callable[[], Optional[Path]],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.get_workspace = get_workspace

        # State
        self.last_preview_data: Optional[PreviewData] = None
        self.last_apply_results: List[ApplyRowResult] = []
        self.last_opx_text: str = ""
        self._cached_file_actions: List = []
        self.expanded_diffs: set = set()

        self._build_ui()

    def _build_ui(self) -> None:
        """Build Apply View voi 2-panel splitter (40:60)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(3)
        splitter.setStyleSheet(
            f"""
            QSplitter::handle {{
                background-color: {ThemeColors.BORDER};
                margin: 4px 0;
            }}
            QSplitter::handle:hover {{
                background-color: {ThemeColors.PRIMARY};
            }}
        """
        )

        # Left: OPX Input (~40%)
        left = self._build_left_panel()
        splitter.addWidget(left)

        # Right: Preview/Results (~60%)
        right = self._build_right_panel()
        splitter.addWidget(right)

        # Ty le 40:60 cho input:preview
        splitter.setStretchFactor(0, 40)
        splitter.setStretchFactor(1, 60)
        splitter.setSizes([500, 750])

        layout.addWidget(splitter)

    def _build_left_panel(self) -> QFrame:
        """Build left panel: OPX input voi compact header va styled buttons."""
        panel = QFrame()
        panel.setProperty("class", "surface")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # Header: title + workspace indicator
        header = QHBoxLayout()
        header.setSpacing(8)

        title_label = QLabel("OPX Input")
        title_label.setStyleSheet(
            f"font-weight: 700; font-size: 13px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        header.addWidget(title_label)
        header.addStretch()

        # Workspace indicator nho gon
        self._workspace_label = QLabel("No workspace")
        self._workspace_label.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.TEXT_MUTED}; font-weight: 500;"
        )
        header.addWidget(self._workspace_label)
        layout.addLayout(header)

        # OPX input textarea
        self._opx_input = QPlainTextEdit()
        self._opx_input.setPlaceholderText(
            "Paste OPX XML response from AI chat...\n\n"
            'Example:\n<edit file="path/to/file" op="patch">\n  ...\n</edit>'
        )
        self._opx_input.setStyleSheet(
            f"""
            QPlainTextEdit {{
                font-family: 'Cascadia Code', 'Fira Code', monospace;
                font-size: 12px;
                background-color: {ThemeColors.BG_ELEVATED};
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 8px;
            }}
            QPlainTextEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
        """
        )
        layout.addWidget(self._opx_input, stretch=1)

        # Button row voi styled buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        # Secondary style cho Paste/Clear/Preview
        secondary_style = (
            f"QPushButton {{"
            f"  background-color: transparent;"
            f"  color: {ThemeColors.TEXT_PRIMARY};"
            f"  border: 1px solid {ThemeColors.BORDER};"
            f"  border-radius: 6px;"
            f"  padding: 7px 14px;"
            f"  font-weight: 600;"
            f"  font-size: 12px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {ThemeColors.BG_HOVER};"
            f"  border-color: {ThemeColors.BORDER_LIGHT};"
            f"}}"
        )

        # Danger style cho Clear
        danger_style = (
            f"QPushButton {{"
            f"  background-color: transparent;"
            f"  color: {ThemeColors.ERROR};"
            f"  border: 1px solid {ThemeColors.ERROR};"
            f"  border-radius: 6px;"
            f"  padding: 7px 14px;"
            f"  font-weight: 600;"
            f"  font-size: 12px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {ThemeColors.ERROR};"
            f"  color: white;"
            f"}}"
        )

        paste_btn = QPushButton("Paste")
        paste_btn.setStyleSheet(secondary_style)
        paste_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        paste_btn.clicked.connect(self._paste_from_clipboard)
        btn_row.addWidget(paste_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(danger_style)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_input)
        btn_row.addWidget(clear_btn)

        btn_row.addStretch()

        preview_btn = QPushButton("Preview")
        preview_btn.setStyleSheet(secondary_style)
        preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        preview_btn.clicked.connect(self._preview_changes)
        btn_row.addWidget(preview_btn)

        # Primary CTA: Apply Changes
        apply_btn = QPushButton("Apply Changes")
        apply_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: 700;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {ThemeColors.PRIMARY_PRESSED};
            }}
        """
        )
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(self._apply_changes)
        btn_row.addWidget(apply_btn)

        layout.addLayout(btn_row)

        return panel

    def _build_right_panel(self) -> QFrame:
        """Build right panel: Preview/Results voi scroll area."""
        panel = QFrame()
        panel.setProperty("class", "surface")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # Header: title + Copy Error Context btn
        header = QHBoxLayout()
        title = QLabel("Preview")
        title.setStyleSheet(
            f"font-weight: 700; font-size: 13px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        header.addWidget(title)
        header.addStretch()

        # Copy error context button (an mac dinh, hien khi co loi)
        self._copy_error_btn = QPushButton("Copy Error Context")
        self._copy_error_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: transparent;"
            f"  color: {ThemeColors.ERROR};"
            f"  border: 1px solid {ThemeColors.ERROR};"
            f"  border-radius: 6px;"
            f"  padding: 5px 12px;"
            f"  font-weight: 600;"
            f"  font-size: 11px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {ThemeColors.ERROR};"
            f"  color: white;"
            f"}}"
        )
        self._copy_error_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_error_btn.clicked.connect(self._copy_error_context)
        self._copy_error_btn.hide()
        header.addWidget(self._copy_error_btn)
        layout.addLayout(header)

        # Results scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._results_container = QWidget()
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(8)
        self._results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Empty state
        empty_label = QLabel("Paste OPX and click Preview to verify changes")
        empty_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED}; font-style: italic; "
            f"font-size: 12px; padding: 32px;"
        )
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._results_layout.addWidget(empty_label)

        scroll.setWidget(self._results_container)
        layout.addWidget(scroll, stretch=1)

        return panel

    # ===== Public API =====

    def set_opx_content(self, content: str) -> None:
        """Set OPX content (from History reapply)."""
        self._opx_input.setPlainText(content)

    # ===== Slots =====

    @Slot()
    def _paste_from_clipboard(self) -> None:
        success, text = get_clipboard_text()
        if success:
            self._opx_input.setPlainText(text)

    @Slot()
    def _clear_input(self) -> None:
        self._opx_input.clear()
        self._clear_results()

    @Slot()
    def _preview_changes(self) -> None:
        """Parse OPX and show preview."""
        opx_text = self._opx_input.toPlainText().strip()
        if not opx_text:
            self._show_status("No OPX content to preview", is_error=True)
            return

        workspace = self.get_workspace()
        if not workspace:
            self._show_status("No workspace selected", is_error=True)
            return

        try:
            parse_result = parse_opx_response(opx_text)
            file_actions = parse_result.file_actions
            if not file_actions:
                self._show_status("No valid OPX actions found", is_error=True)
                return

            self._cached_file_actions = file_actions
            self.last_opx_text = opx_text

            preview_data = analyze_file_actions(file_actions, workspace)

            # Generate diff lines cho từng row để DiffViewer có data hiển thị
            for i, row in enumerate(preview_data.rows):
                if i < len(file_actions):
                    row.diff_lines = generate_preview_diff_lines(
                        file_actions[i], workspace
                    )

            self.last_preview_data = preview_data

            self._render_preview(preview_data)
            self._show_status(f"Previewing {len(file_actions)} change(s)")
        except Exception as e:
            self._show_status(f"Parse error: {e}", is_error=True)

    @Slot()
    def _apply_changes(self) -> None:
        """
        Apply OPX changes.
        Sau khi apply, populate last_apply_results va last_preview_data
        de Copy Error Context co du thong tin chi tiet cho AI fix.
        """
        opx_text = self._opx_input.toPlainText().strip()
        if not opx_text:
            self._show_status("No OPX content to apply", is_error=True)
            return

        workspace = self.get_workspace()
        if not workspace:
            self._show_status("No workspace selected", is_error=True)
            return

        # Confirm
        reply = QMessageBox.question(
            self,
            "Confirm Apply",
            "Apply all changes? Backups will be created.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if self._cached_file_actions:
                file_actions = self._cached_file_actions
            else:
                parse_result = parse_opx_response(opx_text)
                file_actions = parse_result.file_actions
            if not file_actions:
                self._show_status("No valid OPX actions found", is_error=True)
                return

            # Auto-generate preview data neu chua co (user nhan Apply ma khong Preview truoc)
            if not self.last_preview_data:
                self.last_preview_data = analyze_file_actions(file_actions, workspace)
                for i, row in enumerate(self.last_preview_data.rows):
                    if i < len(file_actions):
                        row.diff_lines = generate_preview_diff_lines(
                            file_actions[i], workspace
                        )

            self.last_opx_text = opx_text

            results = apply_file_actions(file_actions, [workspace])

            # Convert ActionResult -> ApplyRowResult de Copy Error co context day du
            self.last_apply_results = _convert_to_row_results(results, file_actions)

            self._render_results(results)

            # Save to history
            success_count = sum(1 for r in results if r.success)
            action_results_dicts = [
                {
                    "action": r.action,
                    "path": r.path,
                    "success": r.success,
                    "message": r.message,
                }
                for r in results
            ]
            add_history_entry(
                workspace_path=str(workspace),
                opx_content=opx_text,
                action_results=action_results_dicts,
            )

            self._show_status(
                f"Applied {success_count}/{len(results)} changes",
                is_error=success_count < len(results),
            )
        except Exception as e:
            self._show_status(f"Apply error: {e}", is_error=True)

    @Slot()
    def _copy_error_context(self) -> None:
        """
        Copy error context day du cho AI debugging.
        Uu tien dung build_error_context_for_ai (co file content, search pattern, OPX instruction).
        Fallback sang build_general_error_context neu khong co apply results.
        """
        workspace = self.get_workspace()
        ws_str = str(workspace) if workspace else None

        if self.last_apply_results and self.last_preview_data:
            context = build_error_context_for_ai(
                preview_data=self.last_preview_data,
                row_results=self.last_apply_results,
                original_opx=self.last_opx_text,
                workspace_path=ws_str,
                include_file_content=True,
            )
        else:
            context = build_general_error_context(
                error_type="Apply Error",
                error_message="Unknown error during apply",
                additional_context=self.last_opx_text,
                workspace_path=ws_str,
            )
        copy_to_clipboard(context)
        self._show_status("Error context copied!")

    # ===== Rendering =====

    def _render_preview(self, preview_data: PreviewData) -> None:
        """Render preview cards."""
        self._clear_results()

        for row in preview_data.rows:
            card = self._create_preview_card(row)
            self._results_layout.addWidget(card)

        self._results_layout.addStretch()

    def _render_results(self, results: List[ActionResult]) -> None:
        """Render apply results."""
        self._clear_results()
        has_errors = False

        for result in results:
            card = self._create_result_card(result)
            self._results_layout.addWidget(card)
            if not result.success:
                has_errors = True

        if has_errors:
            self._copy_error_btn.show()

        self._results_layout.addStretch()

    def _create_preview_card(self, row: PreviewRow) -> QFrame:
        """Tao preview card voi left accent border theo action type va expandable diff viewer."""
        card = QFrame()

        action = row.action.lower() if hasattr(row, "action") else "modify"
        fg, bg = ACTION_COLORS.get(
            action, (ThemeColors.PRIMARY, ThemeColors.BG_ELEVATED)
        )

        # Card style: left accent border theo action color
        card.setStyleSheet(
            f"QFrame {{"
            f"  background-color: {ThemeColors.BG_ELEVATED};"
            f"  border: 1px solid {ThemeColors.BORDER};"
            f"  border-left: 3px solid {fg};"
            f"  border-radius: 6px;"
            f"  padding: 10px 12px;"
            f"}}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header: action badge + file path + diff stats
        header = QHBoxLayout()
        header.setSpacing(8)

        # Action badge
        badge = QLabel(action.upper())
        badge.setStyleSheet(
            f"color: {fg}; background-color: {bg}; "
            f"border: none; border-radius: 3px; "
            f"padding: 2px 8px; font-size: 10px; font-weight: 700;"
        )
        badge.setFixedHeight(20)
        header.addWidget(badge)

        # File path (monospace)
        file_label = QLabel(row.path)
        file_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_PRIMARY}; font-size: 12px; "
            f"font-family: 'Cascadia Code', 'Fira Code', monospace; "
            f"border: none;"
        )
        header.addWidget(file_label)
        header.addStretch()

        # Diff stats (+added / -removed)
        if row.changes:
            if row.changes.added > 0:
                add_label = QLabel(f"+{row.changes.added}")
                add_label.setStyleSheet(
                    f"color: {ApplyViewColors.DIFF_ADD}; font-size: 11px; "
                    f"font-weight: 700; border: none;"
                )
                header.addWidget(add_label)
            if row.changes.removed > 0:
                rm_label = QLabel(f"-{row.changes.removed}")
                rm_label.setStyleSheet(
                    f"color: {ApplyViewColors.DIFF_REMOVE}; font-size: 11px; "
                    f"font-weight: 700; border: none;"
                )
                header.addWidget(rm_label)

        layout.addLayout(header)

        # Description (neu co)
        if row.description:
            desc_label = QLabel(row.description)
            desc_label.setStyleSheet(
                f"color: {ThemeColors.PRIMARY}; font-size: 12px; "
                f"padding-left: 4px; border: none;"
            )
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        # Diff viewer (hidden by default, toggled by button)
        has_diff = hasattr(row, "diff_lines") and row.diff_lines

        if has_diff:
            # Container cho diff viewer - ban dau an
            diff_container = QFrame()
            diff_container.setVisible(False)
            diff_container.setStyleSheet("border: none;")
            diff_layout = QVBoxLayout(diff_container)
            diff_layout.setContentsMargins(0, 4, 0, 0)

            diff_viewer = DiffViewerWidget(row.diff_lines)
            diff_viewer.setMinimumHeight(120)
            diff_viewer.setMaximumHeight(400)
            diff_layout.addWidget(diff_viewer)

            # Toggle button
            diff_btn = QPushButton("View Diff")
            diff_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            diff_btn.setStyleSheet(
                f"QPushButton {{"
                f"  color: {ThemeColors.PRIMARY};"
                f"  background-color: transparent;"
                f"  border: 1px solid {ThemeColors.BORDER};"
                f"  border-radius: 4px;"
                f"  padding: 3px 12px;"
                f"  font-size: 11px;"
                f"  font-weight: 600;"
                f"}}"
                f"QPushButton:hover {{"
                f"  background-color: {ThemeColors.PRIMARY};"
                f"  color: white;"
                f"  border-color: {ThemeColors.PRIMARY};"
                f"}}"
            )
            diff_btn.setFixedHeight(24)

            def _toggle_diff(checked=False, container=diff_container, btn=diff_btn):
                is_visible = container.isVisible()
                container.setVisible(not is_visible)
                btn.setText("Hide Diff" if not is_visible else "View Diff")

            diff_btn.clicked.connect(_toggle_diff)

            # Button row
            btn_row = QHBoxLayout()
            btn_row.addWidget(diff_btn)
            btn_row.addStretch()
            layout.addLayout(btn_row)

            layout.addWidget(diff_container)
        elif action != "rename":
            # Khong co diff data - hien thi hint
            no_diff = QLabel("No diff available (file may not exist yet)")
            no_diff.setStyleSheet(
                f"color: {ThemeColors.TEXT_SECONDARY}; font-size: 11px; "
                f"font-style: italic; padding-left: 4px; border: none;"
            )
            layout.addWidget(no_diff)

        return card

    def _create_result_card(self, result: ActionResult) -> QFrame:
        """Tao result card (success/error) voi left accent border."""
        card = QFrame()
        action = result.action.lower() if hasattr(result, "action") else "modify"

        if result.success:
            accent_color = ApplyViewColors.SUCCESS_TEXT
            card.setStyleSheet(
                f"QFrame {{"
                f"  background-color: #052E16;"
                f"  border: 1px solid #166534;"
                f"  border-left: 3px solid {accent_color};"
                f"  border-radius: 6px;"
                f"  padding: 8px 12px;"
                f"}}"
            )
        else:
            accent_color = ApplyViewColors.ERROR_TEXT
            card.setStyleSheet(
                f"QFrame {{"
                f"  background-color: #450A0A;"
                f"  border: 1px solid #991B1B;"
                f"  border-left: 3px solid {accent_color};"
                f"  border-radius: 6px;"
                f"  padding: 8px 12px;"
                f"}}"
            )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header: status icon + action badge + file path
        header = QHBoxLayout()
        header.setSpacing(8)

        # Status icon
        icon_text = "OK" if result.success else "FAIL"
        icon_color = (
            ApplyViewColors.SUCCESS_TEXT
            if result.success
            else ApplyViewColors.ERROR_TEXT
        )
        icon_label = QLabel(icon_text)
        icon_label.setStyleSheet(
            f"color: {icon_color}; font-size: 10px; font-weight: 700; border: none;"
        )
        header.addWidget(icon_label)

        # Action badge
        fg, bg = ACTION_COLORS.get(
            action, (ThemeColors.PRIMARY, ThemeColors.BG_ELEVATED)
        )
        badge = QLabel(action.upper())
        badge.setStyleSheet(
            f"color: {fg}; background-color: {bg}; border: none; "
            f"border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 700;"
        )
        badge.setFixedHeight(18)
        header.addWidget(badge)

        # File path (monospace)
        path_label = QLabel(result.path)
        path_label.setStyleSheet(
            f"color: {icon_color}; font-size: 12px; "
            f"font-family: 'Cascadia Code', 'Fira Code', monospace; "
            f"font-weight: 600; border: none;"
        )
        header.addWidget(path_label)
        header.addStretch()
        layout.addLayout(header)

        # Error message (neu co)
        if result.message:
            msg = QLabel(result.message)
            msg.setStyleSheet(
                f"color: {ThemeColors.TEXT_SECONDARY}; font-size: 12px; "
                f"padding-left: 4px; border: none;"
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)

        return card

    def _clear_results(self) -> None:
        """Clear results area."""
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            if item and (widget := item.widget()):
                widget.deleteLater()
        self._copy_error_btn.hide()

    def _show_status(self, message: str, is_error: bool = False) -> None:
        """Hien thi thong bao qua he thong toast toan cuc."""
        if not message:
            return

        if is_error:
            toast_error(message)
        else:
            toast_success(message)


def _convert_to_row_results(
    results: List[ActionResult],
    file_actions: list,
) -> List[ApplyRowResult]:
    """
    Convert List[ActionResult] tu file_actions module sang List[ApplyRowResult]
    de error_context module co du data cho AI fix.

    Detect cascade failures: khi file da duoc modify thanh cong boi operation truoc,
    cac operation sau tren cung file co the fail do search pattern khong con match.
    """
    row_results: List[ApplyRowResult] = []
    # Track files da duoc modify thanh cong de detect cascade
    modified_files: set = set()

    for i, result in enumerate(results):
        is_cascade = not result.success and result.path in modified_files
        row_results.append(
            ApplyRowResult(
                row_index=i,
                path=result.path,
                action=result.action,
                success=result.success,
                message=result.message,
                is_cascade_failure=is_cascade,
            )
        )
        if result.success:
            modified_files.add(result.path)

    return row_results
