"""
Apply View (PySide6) - Tab để paste OPX và apply changes.
"""

from pathlib import Path
from typing import Optional, List, Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QPlainTextEdit, QScrollArea,
    QFrame, QMessageBox,
)
from PySide6.QtCore import Qt, Slot, QTimer

from core.theme import ThemeColors
from core.opx_parser import parse_opx_response
from core.file_actions import apply_file_actions, ActionResult
from services.clipboard_utils import copy_to_clipboard, get_clipboard_text
from services.history_service import add_history_entry
from services.preview_analyzer import (
    analyze_file_actions, PreviewRow, PreviewData,
    generate_preview_diff_lines,
)
from services.error_context import (
    build_error_context_for_ai, build_general_error_context, ApplyRowResult,
)
from components.diff_viewer_qt import DiffViewerWidget


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
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: OPX Input
        left = self._build_left_panel()
        splitter.addWidget(left)
        
        # Right: Preview/Results
        right = self._build_right_panel()
        splitter.addWidget(right)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
    
    def _build_left_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("class", "surface")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header = QHBoxLayout()
        title_layout = QHBoxLayout()
        title_layout.setSpacing(8)
        title_label = QLabel("OPX Input")
        title_label.setStyleSheet(
            f"font-weight: 600; font-size: 15px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        title_layout.addWidget(title_label)
        header.addLayout(title_layout)
        header.addStretch()
        
        # Workspace indicator
        self._workspace_label = QLabel("No workspace selected")
        self._workspace_label.setStyleSheet(
            f"font-size: 12px; color: {ThemeColors.TEXT_MUTED}; "
            f"background-color: {ApplyViewColors.BG_CARD}; "
            f"border-radius: 6px; padding: 4px 10px;"
        )
        header.addWidget(self._workspace_label)
        layout.addLayout(header)
        
        # Description
        desc = QLabel("Paste OPX code from AI chat below:")
        desc.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_MUTED};")
        layout.addWidget(desc)
        
        # OPX input
        self._opx_input = QPlainTextEdit()
        self._opx_input.setPlaceholderText(
            'Paste the LLM\'s OPX XML response here...\n\n'
            'Example:\n<edit file="path/to/file" op="patch">\n  ...\n</edit>'
        )
        layout.addWidget(self._opx_input, stretch=1)
        
        # Buttons
        btn_row = QHBoxLayout()
        
        paste_btn = QPushButton("Paste")
        paste_btn.setProperty("class", "outlined")
        paste_btn.clicked.connect(self._paste_from_clipboard)
        btn_row.addWidget(paste_btn)
        
        clear_btn = QPushButton("Clear")
        clear_btn.setProperty("class", "outlined")
        clear_btn.clicked.connect(self._clear_input)
        btn_row.addWidget(clear_btn)
        
        btn_row.addStretch()
        
        preview_btn = QPushButton("Preview")
        preview_btn.setProperty("class", "outlined")
        preview_btn.clicked.connect(self._preview_changes)
        btn_row.addWidget(preview_btn)
        
        apply_btn = QPushButton("Apply Changes")
        apply_btn.setProperty("class", "primary")
        apply_btn.clicked.connect(self._apply_changes)
        btn_row.addWidget(apply_btn)
        
        layout.addLayout(btn_row)
        
        # Status
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"font-size: 12px;")
        layout.addWidget(self._status_label)
        
        return panel
    
    def _build_right_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("class", "surface")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Preview")
        title.setStyleSheet(
            f"font-weight: 600; font-size: 15px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        header.addWidget(title)
        header.addStretch()
        
        # Copy error context button
        self._copy_error_btn = QPushButton("Copy Error Context")
        self._copy_error_btn.setProperty("class", "danger")
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
        self._results_layout.setSpacing(12)
        self._results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Empty state
        empty_label = QLabel("Paste OPX code and click Preview to see changes")
        empty_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED}; font-style: italic; padding: 40px;"
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
        """Apply OPX changes."""
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
            self, "Confirm Apply",
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
            
            results = apply_file_actions(file_actions, [workspace])
            self._render_results(results)
            
            # Save to history
            success_count = sum(1 for r in results if r.success)
            action_results_dicts = [
                {"action": r.action, "path": r.path, "success": r.success, "message": r.message}
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
        """Copy error context for AI debugging."""
        if self.last_apply_results and self.last_preview_data:
            context = build_error_context_for_ai(
                preview_data=self.last_preview_data,
                row_results=self.last_apply_results,
                original_opx=self.last_opx_text,
            )
        else:
            context = build_general_error_context(
                error_type="Apply Error",
                error_message="Unknown error during apply",
                additional_context=self.last_opx_text,
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
        """Create a preview card widget with expandable diff viewer."""
        card = QFrame()
        card.setStyleSheet(
            f"background-color: {ApplyViewColors.BG_CARD}; "
            f"border: 1px solid {ThemeColors.BORDER}; "
            f"border-radius: 8px; padding: 12px;"
        )
        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        
        # Header: action badge + file path + diff stats + View Diff button
        header = QHBoxLayout()
        
        action = row.action.lower() if hasattr(row, 'action') else "modify"
        fg, bg = ACTION_COLORS.get(action, (ThemeColors.PRIMARY, ThemeColors.BG_ELEVATED))
        
        badge = QLabel(action.upper())
        badge.setStyleSheet(
            f"color: {fg}; background-color: {bg}; "
            f"border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: bold;"
        )
        badge.setFixedHeight(22)
        header.addWidget(badge)
        
        file_label = QLabel(row.path)
        file_label.setStyleSheet(f"color: {ThemeColors.TEXT_PRIMARY}; font-size: 13px;")
        header.addWidget(file_label)
        header.addStretch()
        
        # Diff stats
        if row.changes:
            if row.changes.added > 0:
                add_label = QLabel(f"+{row.changes.added}")
                add_label.setStyleSheet(f"color: {ApplyViewColors.DIFF_ADD}; font-size: 12px;")
                header.addWidget(add_label)
            if row.changes.removed > 0:
                rm_label = QLabel(f"-{row.changes.removed}")
                rm_label.setStyleSheet(f"color: {ApplyViewColors.DIFF_REMOVE}; font-size: 12px;")
                header.addWidget(rm_label)
        
        layout.addLayout(header)
        
        # Description (nếu có)
        if row.description:
            desc_label = QLabel(row.description)
            desc_label.setStyleSheet(
                f"color: {ThemeColors.TEXT_SECONDARY}; font-size: 12px; "
                f"padding-left: 4px;"
            )
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
        
        # Diff viewer (hidden by default, toggled by button)
        has_diff = hasattr(row, 'diff_lines') and row.diff_lines
        
        if has_diff:
            # Container cho diff viewer — ban đầu ẩn
            diff_container = QFrame()
            diff_container.setVisible(False)
            diff_layout = QVBoxLayout(diff_container)
            diff_layout.setContentsMargins(0, 4, 0, 0)
            
            diff_viewer = DiffViewerWidget(row.diff_lines)
            diff_viewer.setMinimumHeight(120)
            diff_viewer.setMaximumHeight(400)
            diff_layout.addWidget(diff_viewer)
            
            # "View Diff" toggle button
            diff_btn = QPushButton("▶ View Diff")
            diff_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            diff_btn.setStyleSheet(
                f"QPushButton {{"
                f"  color: {ThemeColors.PRIMARY}; "
                f"  background-color: transparent; "
                f"  border: 1px solid {ThemeColors.PRIMARY}; "
                f"  border-radius: 4px; "
                f"  padding: 3px 12px; "
                f"  font-size: 11px; "
                f"  font-weight: 600;"
                f"}}"
                f"QPushButton:hover {{"
                f"  background-color: {ThemeColors.PRIMARY}; "
                f"  color: #FFFFFF;"
                f"}}"
            )
            diff_btn.setFixedHeight(24)
            
            def _toggle_diff(checked=False, container=diff_container, btn=diff_btn):
                is_visible = container.isVisible()
                container.setVisible(not is_visible)
                btn.setText("▼ Hide Diff" if not is_visible else "▶ View Diff")
            
            diff_btn.clicked.connect(_toggle_diff)
            
            # Button row
            btn_row = QHBoxLayout()
            btn_row.addWidget(diff_btn)
            btn_row.addStretch()
            layout.addLayout(btn_row)
            
            layout.addWidget(diff_container)
        elif action != "rename":
            # Không có diff data — hiển thị hint
            no_diff = QLabel("No diff available (file may not exist yet)")
            no_diff.setStyleSheet(
                f"color: {ThemeColors.TEXT_MUTED}; font-size: 11px; "
                f"font-style: italic; padding-left: 4px;"
            )
            layout.addWidget(no_diff)
        
        return card
    
    def _create_result_card(self, result: ActionResult) -> QFrame:
        """Create a result card (success/error)."""
        card = QFrame()
        
        if result.success:
            card.setStyleSheet(
                f"background-color: #052E16; border: 1px solid #166534; "
                f"border-radius: 8px; padding: 12px;"
            )
        else:
            card.setStyleSheet(
                f"background-color: #450A0A; border: 1px solid #991B1B; "
                f"border-radius: 8px; padding: 12px;"
            )
        
        layout = QVBoxLayout(card)
        
        icon = "✅" if result.success else "❌"
        status_label = QLabel(f"{icon} {result.path}")
        status_label.setStyleSheet(
            f"color: {ApplyViewColors.SUCCESS_TEXT if result.success else ApplyViewColors.ERROR_TEXT}; "
            f"font-size: 13px;"
        )
        layout.addWidget(status_label)
        
        if result.message:
            msg = QLabel(result.message)
            msg.setStyleSheet(f"color: {ThemeColors.TEXT_SECONDARY}; font-size: 12px;")
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
        color = ThemeColors.ERROR if is_error else ThemeColors.SUCCESS
        self._status_label.setStyleSheet(f"font-size: 12px; color: {color};")
        self._status_label.setText(message)
        if message and not is_error:
            QTimer.singleShot(5000, lambda: self._status_label.setText(""))
