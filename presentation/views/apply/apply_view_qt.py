"""
Apply View (PySide6) - Tab để paste OPX và apply changes.
"""

import logging
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
from PySide6.QtCore import Qt, Slot, QTimer
from domain.prompt.patch_detection_service import PatchDetectionService

from presentation.config.theme import ThemeColors
from domain.prompt.opx_parser import parse_any_response
from domain.ports.action_result import ActionResult
from domain.ports.registry import DomainRegistry
from presentation.utils.clipboard import (
    copy_to_clipboard,
    get_clipboard_text,
)
from application.services.preview_analyzer import (
    analyze_file_actions,
    PreviewRow,
    PreviewData,
    generate_preview_diff_lines,
)
from application.services.error_context import (
    build_error_context_for_ai,
    build_general_error_context,
    ApplyRowResult,
)
from application.services.apply_service import convert_to_row_results, save_memory_block
from presentation.components.diff_viewer_qt import DiffViewerWidget
from presentation.components.toast.toast_qt import toast_success, toast_error


def apply_file_actions(*args, **kwargs):
    return DomainRegistry.file_actions_service().apply_file_actions(*args, **kwargs)


def add_history_entry(*args, **kwargs):
    return DomainRegistry.history_service().add_history_entry(*args, **kwargs)


logger = logging.getLogger(__name__)


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

        # Xác định thư mục assets (hỗ trợ cả môi trường chạy mã nguồn và đóng gói)
        import sys

        if hasattr(sys, "_MEIPASS"):
            self.assets_dir = Path(sys._MEIPASS) / "assets"
        else:
            self.assets_dir = Path(__file__).parent.parent.parent.parent / "assets"

        # State
        self.last_preview_data: Optional[PreviewData] = None
        self.last_apply_results: List[ApplyRowResult] = []
        self.last_opx_text: str = ""
        self._cached_file_actions: List = []
        self._cached_memory_block: Optional[str] = None

        self.expanded_diffs: set = set()

        # Nâng cấp Auto-detection
        self._apply_btn = None
        self._summary_label = None
        self._detection_result = None

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._on_debounce_timeout)

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

        title_label = QLabel("Search/Replace Input")
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

        # Search/Replace input textarea
        self._opx_input = QPlainTextEdit()
        self._opx_input.setPlaceholderText(
            "Paste Search/Replace response (Aider-style) from AI chat...\n\n"
            "Example:\n"
            "<<<<<<< SEARCH path/to/file.ext\n"
            "original code block to replace\n"
            "=======\n"
            "replacement code block\n"
            ">>>>>>> REPLACE"
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

        # Summary label
        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        self._summary_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        self._summary_label.setOpenExternalLinks(False)
        self._summary_label.linkActivated.connect(self._show_affected_files_menu)
        self._summary_label.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.TEXT_MUTED}; font-weight: 500; margin-top: 4px; padding-left: 2px;"
        )
        self._summary_label.hide()
        layout.addWidget(self._summary_label)

        # Kết nối sự kiện textChanged
        self._opx_input.textChanged.connect(self._on_text_changed)

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
        # Primary CTA: Apply Changes
        self._apply_btn = QPushButton("Apply Changes")
        self._apply_btn.setStyleSheet(
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
            QPushButton:disabled {{
                background-color: {ThemeColors.BORDER};
                color: {ThemeColors.TEXT_MUTED};
            }}
        """
        )
        self._apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_btn.setEnabled(False)  # Mặc định disabled
        self._apply_btn.clicked.connect(self._apply_changes)
        btn_row.addWidget(self._apply_btn)

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
        self._copy_error_btn = QPushButton("⚠  Copy Error Context for AI Fix")
        self._copy_error_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: rgba(248, 113, 113, 0.1);"
            f"  color: {ThemeColors.ERROR};"
            f"  border: 1px solid {ThemeColors.ERROR};"
            f"  border-radius: 6px;"
            f"  padding: 5px 12px;"
            f"  font-weight: 700;"
            f"  font-size: 11px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {ThemeColors.ERROR};"
            f"  color: white;"
            f"}}"
        )
        self._copy_error_btn.setToolTip(
            "Copy full error context including file content, OPX instruction, "
            "and error messages so the AI can automatically fix it."
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

        # Render initial empty state
        self._render_empty_state()

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
        self._render_empty_state()
        self._cached_file_actions.clear()
        self._cached_memory_block = None
        self._detection_result = None
        if self._summary_label:
            self._summary_label.hide()
        if self._apply_btn:
            self._apply_btn.setEnabled(False)

    @Slot()
    def _preview_changes(self) -> None:
        """Parse edits (OPX/Search-Replace) and show preview."""
        opx_text = self._opx_input.toPlainText().strip()
        if not opx_text:
            self._show_status("No changes to preview", is_error=True)
            return

        workspace = self.get_workspace()
        if not workspace:
            self._show_status("No workspace selected", is_error=True)
            return

        try:
            parse_result = parse_any_response(opx_text)
            file_actions = parse_result.file_actions
            if not file_actions:
                self._show_status("No valid changes found", is_error=True)
                return

            self._cached_file_actions = file_actions
            self._cached_memory_block = parse_result.memory_block
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
            if self._apply_btn:
                self._apply_btn.setEnabled(True)
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
            self._show_status("No changes to apply", is_error=True)
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
                memory_block = self._cached_memory_block
            else:
                parse_result = parse_any_response(opx_text)
                file_actions = parse_result.file_actions
                memory_block = parse_result.memory_block
            if not file_actions:
                self._show_status("No valid changes found", is_error=True)
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
            self.last_apply_results = convert_to_row_results(results, file_actions)

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

            # Nếu apply thành công ít nhất một thay đổi, dọn dẹp textarea và hiện summary
            if success_count > 0:
                self._opx_input.blockSignals(True)
                self._opx_input.clear()
                self._opx_input.blockSignals(False)

                if self._summary_label:
                    self._summary_label.setText(
                        f"Successfully applied {success_count} changes"
                    )
                    self._summary_label.setToolTip("")
                    self._summary_label.setStyleSheet(
                        "font-size: 11px; color: #4ADE80; font-weight: 600; "
                        "background-color: rgba(74, 222, 128, 0.08); border: 1px solid rgba(74, 222, 128, 0.2); "
                        "border-radius: 6px; padding: 6px 10px; margin-top: 4px;"
                    )
                    self._summary_label.show()
                if self._apply_btn:
                    self._apply_btn.setEnabled(False)

            # Save continuous memory if apply was at least partially successful
            if success_count > 0 and memory_block:
                try:
                    from presentation.utils.qt_utils import schedule_background

                    schedule_background(
                        lambda: save_memory_block(workspace, memory_block)
                    )
                except ImportError:
                    save_memory_block(workspace, memory_block)

        except Exception as e:
            self._show_status(f"Apply error: {e}", is_error=True)

    @Slot(int, object, object)
    def _apply_single_change(
        self, action_idx: int, btn: QPushButton, card: QFrame
    ) -> None:
        """Apply single patch/file action."""
        workspace = self.get_workspace()
        if not workspace:
            self._show_status("No workspace selected", is_error=True)
            return

        if not self._cached_file_actions or action_idx >= len(
            self._cached_file_actions
        ):
            self._show_status("Action not found", is_error=True)
            return

        file_action = self._cached_file_actions[action_idx]

        # Confirm
        reply = QMessageBox.question(
            self,
            "Confirm Apply",
            f"Apply this change to {file_action.path}? A backup will be created.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            results = apply_file_actions([file_action], [workspace])
            if not results:
                self._show_status("No results returned", is_error=True)
                return
            result = results[0]

            # Convert to row results to keep error context updated
            row_results = convert_to_row_results(results, [file_action])

            if not self.last_apply_results and self.last_preview_data:
                # Initialize placeholder list
                self.last_apply_results = [
                    ApplyRowResult(
                        row_index=idx,
                        path=row.path,
                        action=row.action,
                        success=True,
                        message="",
                    )
                    for idx, row in enumerate(self.last_preview_data.rows)
                ]

            if self.last_apply_results and action_idx < len(self.last_apply_results):
                row_results[0].row_index = action_idx
                self.last_apply_results[action_idx] = row_results[0]

            if result.success:
                # Update UI to success state
                card.setStyleSheet(
                    f"QFrame {{"
                    f"  background-color: #052E16;"
                    f"  border: 1px solid #166534;"
                    f"  border-left: 4px solid {ApplyViewColors.SUCCESS_TEXT};"
                    f"  border-radius: 8px;"
                    f"  padding: 14px 16px;"
                    f"}}"
                    f"QFrame:hover {{"
                    f"  background-color: #052E16;"
                    f"  border-color: #166534;"
                    f"}}"
                )
                btn.setVisible(False)

                # Show success label
                success_label = QLabel("OK")
                success_label.setStyleSheet(
                    f"color: {ApplyViewColors.SUCCESS_TEXT}; font-size: 11px; font-weight: 700; border: none;"
                )
                btn.parentWidget().layout().addWidget(success_label)

                # Hide error label if previously shown
                error_label = card.findChild(QLabel, "single_error_label")
                if error_label and isinstance(error_label, QLabel):
                    error_label.setVisible(False)

                self._show_status(f"Applied change to {file_action.path} successfully")
            else:
                # Update UI to failure state
                card.setStyleSheet(
                    f"QFrame {{"
                    f"  background-color: #450A0A;"
                    f"  border: 1px solid #991B1B;"
                    f"  border-left: 4px solid {ApplyViewColors.ERROR_TEXT};"
                    f"  border-radius: 8px;"
                    f"  padding: 14px 16px;"
                    f"}}"
                    f"QFrame:hover {{"
                    f"  background-color: #450A0A;"
                    f"  border-color: #991B1B;"
                    f"}}"
                )

                # Show error message label
                error_label = card.findChild(QLabel, "single_error_label")
                if not isinstance(error_label, QLabel):
                    error_label = QLabel()
                    error_label.setObjectName("single_error_label")
                    error_label.setWordWrap(True)
                    card.layout().addWidget(error_label)

                error_label.setText(f"Error: {result.message}")
                error_label.setStyleSheet(
                    f"color: {ApplyViewColors.ERROR_TEXT}; font-size: 12px; padding-left: 4px; border: none;"
                )
                error_label.setVisible(True)

                self._show_status(
                    f"Failed to apply change to {file_action.path}", is_error=True
                )
                self._copy_error_btn.show()

            # Save to history
            action_results_dicts = [
                {
                    "action": result.action,
                    "path": result.path,
                    "success": result.success,
                    "message": result.message,
                }
            ]
            add_history_entry(
                workspace_path=str(workspace),
                opx_content=self.last_opx_text,
                action_results=action_results_dicts,
            )

            # Save continuous memory if apply was successful
            if result.success and self._cached_memory_block:
                try:
                    from presentation.utils.qt_utils import schedule_background

                    schedule_background(
                        lambda: save_memory_block(workspace, self._cached_memory_block)
                    )
                except ImportError:
                    save_memory_block(workspace, self._cached_memory_block)

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

    def _render_empty_state(self) -> None:
        """
        Hiển thị trạng thái chờ với hướng dẫn sử dụng.
        Hàm này sửa lỗi UI bị 'bóp lại' (squeezed) bằng cách điều chỉnh layout alignment
        và giới hạn chiều rộng của text một cách hợp lý.
        """
        self._clear_results()
        # Chuyển layout về chế độ căn giữa khi ở trạng thái empty
        self._results_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_widget = QWidget()
        empty_layout = QVBoxLayout(empty_widget)
        # Giữ spacing và padding rộng rãi để UI thoáng đãng (Premium feel)
        empty_layout.setSpacing(16)
        empty_layout.setContentsMargins(40, 80, 40, 80)

        # Biểu tượng tia sét đặc trưng của Synapse (loại bỏ emoji và dùng SVG icon được tô màu)
        empty_icon = QLabel()
        from presentation.components.qt_utils import create_colored_icon
        from PySide6.QtCore import QSize

        icon_zap = create_colored_icon(
            str(self.assets_dir / "zap.svg"), ThemeColors.PRIMARY
        )
        empty_icon.setPixmap(icon_zap.pixmap(QSize(52, 52)))
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)

        # Tiêu đề chính
        empty_title = QLabel("Ready to Apply Changes")
        empty_title.setStyleSheet(
            f"font-size: 20px; font-weight: 800; color: {ThemeColors.TEXT_PRIMARY}; "
            "background: transparent; margin-top: 10px;"
        )
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_title)

        # Hướng dẫn chi tiết 3 bước
        empty_steps = QLabel(
            "1.  Paste the OPX response from AI chat into the left panel\n"
            "2.  Click Preview to review changes with visual side-by-side diffs\n"
            "3.  Click Apply Changes to write to disk safely (with backups)"
        )
        empty_steps.setStyleSheet(
            f"color: {ThemeColors.TEXT_SECONDARY}; font-size: 14px; "
            "line-height: 1.8; background: transparent; "
            "padding: 10px 0;"
        )
        empty_steps.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_steps.setWordWrap(True)
        # Fix lỗi 'bóp': Đặt chiều rộng tối thiểu và tối đa để text wrap đẹp hơn
        empty_steps.setMinimumWidth(400)
        empty_steps.setMaximumWidth(600)
        empty_layout.addWidget(empty_steps)

        self._results_layout.addWidget(empty_widget)

    def _render_preview(self, preview_data: PreviewData) -> None:
        """Render preview cards."""
        self._clear_results()
        # Khi có kết quả, chuyển layout về AlignTop để danh sách bắt đầu từ trên xuống
        self._results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        for i, row in enumerate(preview_data.rows):
            card = self._create_preview_card(row, i)
            self._results_layout.addWidget(card)

        self._results_layout.addStretch()

    def _render_results(self, results: List[ActionResult]) -> None:
        """Render apply results."""
        self._clear_results()
        # Khi có kết quả, chuyển layout về AlignTop
        self._results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        has_errors = False

        for result in results:
            card = self._create_result_card(result)
            self._results_layout.addWidget(card)
            if not result.success:
                has_errors = True

        if has_errors:
            self._copy_error_btn.show()

        self._results_layout.addStretch()

    def _create_preview_card(self, row: PreviewRow, action_idx: int = 0) -> QFrame:
        """Tao preview card voi left accent border theo action type va expandable diff viewer."""
        card = QFrame()

        action = row.action.lower() if hasattr(row, "action") else "modify"
        fg, bg = ACTION_COLORS.get(
            action, (ThemeColors.PRIMARY, ThemeColors.BG_ELEVATED)
        )

        # Card style: left accent border theo action color
        card.setStyleSheet(
            f"QFrame {{"
            f"  background-color: {ThemeColors.BG_SURFACE};"
            f"  border: 1px solid {ThemeColors.BORDER};"
            f"  border-left: 4px solid {fg};"
            f"  border-radius: 8px;"
            f"  padding: 14px 16px;"
            f"}}"
            f"QFrame:hover {{"
            f"  border-color: {ThemeColors.BORDER_LIGHT};"
            f"  background-color: {ThemeColors.BG_ELEVATED};"
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

        diff_container = None
        if has_diff:
            # Container cho diff viewer - ban dau an
            diff_container = QFrame()
            diff_container.setVisible(False)
            diff_container.setStyleSheet("border: none;")
            diff_layout = QVBoxLayout(diff_container)
            diff_layout.setContentsMargins(0, 4, 0, 0)

            diff_viewer = DiffViewerWidget(row.diff_lines)
            diff_viewer.setMinimumHeight(550)
            diff_viewer.setMaximumHeight(800)
            diff_layout.addWidget(diff_viewer)

        # Hien thi hint neu khong co diff (va khong phai rename)
        if not has_diff and action != "rename":
            no_diff = QLabel("No diff available (file may not exist yet)")
            no_diff.setStyleSheet(
                f"color: {ThemeColors.TEXT_SECONDARY}; font-size: 11px; "
                f"font-style: italic; padding-left: 4px; border: none;"
            )
            layout.addWidget(no_diff)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        if has_diff:
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
                if container:
                    is_visible = container.isVisible()
                    container.setVisible(not is_visible)
                    btn.setText("Hide Diff" if not is_visible else "View Diff")

            diff_btn.clicked.connect(_toggle_diff)
            btn_row.addWidget(diff_btn)

        # Apply button cho tung card
        apply_this_btn = QPushButton("Apply")
        apply_this_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_this_btn.setStyleSheet(
            f"QPushButton {{"
            f"  color: white;"
            f"  background-color: {ThemeColors.PRIMARY};"
            f"  border: none;"
            f"  border-radius: 4px;"
            f"  padding: 3px 12px;"
            f"  font-size: 11px;"
            f"  font-weight: 600;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {ThemeColors.PRIMARY_HOVER};"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background-color: {ThemeColors.PRIMARY_PRESSED};"
            f"}}"
        )
        apply_this_btn.setFixedHeight(24)
        apply_this_btn.clicked.connect(
            lambda checked=False, idx=action_idx, btn=apply_this_btn, c=card: (
                self._apply_single_change(idx, btn, c)
            )
        )
        btn_row.addWidget(apply_this_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        if has_diff and diff_container:
            layout.addWidget(diff_container)

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

    # ===== Auto-Detection Slots =====

    @Slot()
    def _on_text_changed(self) -> None:
        """Kích hoạt timer debounce 800ms khi văn bản thay đổi."""
        self._debounce_timer.start(800)

    @Slot()
    def _on_debounce_timeout(self) -> None:
        """Hết thời gian debounce, tiến hành phân tích patch."""
        text = self._opx_input.toPlainText()
        workspace = self.get_workspace()
        ws_root = str(workspace) if workspace else None

        detector = PatchDetectionService(workspace_root=ws_root)
        self._detection_result = detector.detect(text)

        self._update_detection_ui()

        # Tự động trigger preview nếu phát hiện có patch hợp lệ và nội dung mới
        if self._detection_result and self._detection_result.has_patches:
            if text.strip() != (self.last_opx_text or "").strip():
                self._preview_changes()

    @Slot(str)
    def _show_affected_files_menu(self, link_text: str) -> None:
        """Hiển thị Popup Menu chứa các file bị ảnh hưởng."""
        if (
            not self._summary_label
            or not self._detection_result
            or not self._detection_result.affected_files
        ):
            return

        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{"
            f"  background-color: {ThemeColors.BG_ELEVATED};"
            f"  border: 1px solid {ThemeColors.BORDER};"
            f"  border-radius: 6px;"
            f"  padding: 4px 0px;"
            f"}}"
            f"QMenu::item {{"
            f"  padding: 6px 16px;"
            f"  color: {ThemeColors.TEXT_PRIMARY};"
            f"  font-family: 'Cascadia Code', 'Fira Code', monospace;"
            f"  font-size: 11px;"
            f"}}"
            f"QMenu::item:selected {{"
            f"  background-color: {ThemeColors.PRIMARY};"
            f"  color: white;"
            f"}}"
        )

        for file_path in self._detection_result.affected_files:
            action = menu.addAction(f"📄  {file_path}")
            action.setToolTip("Click to copy file path")
            action.triggered.connect(
                lambda checked=False, p=file_path: (
                    copy_to_clipboard(p),
                    self._show_status(f"Copied: {p}"),
                )
            )

        pos = self._summary_label.mapToGlobal(self._summary_label.rect().bottomLeft())
        pos.setY(pos.y() + 4)
        menu.exec(pos)

    def _update_detection_ui(self) -> None:
        """Cập nhật trạng thái hiển thị của Summary Label và Apply Button."""
        text = self._opx_input.toPlainText().strip()

        if not text:
            if self._summary_label:
                self._summary_label.hide()
            if self._apply_btn:
                self._apply_btn.setEnabled(False)
            self._render_empty_state()
            self._cached_file_actions.clear()
            self._cached_memory_block = None
            self._detection_result = None
            self.last_opx_text = ""
            self.last_preview_data = None
            return

        if self._detection_result and self._detection_result.has_patches:
            # Tính tổng số lượng changes
            num_changes = sum(
                max(1, len(a.changes)) for a in self._detection_result.file_actions
            )
            num_files = len(self._detection_result.affected_files)

            if self._summary_label:
                self._summary_label.setText(
                    f"Found {num_changes} changes in {num_files} affected files. "
                    f"<a href='show_files' style='color: {ThemeColors.PRIMARY}; text-decoration: none; font-weight: bold;'>[Show Files]</a>"
                )
                self._summary_label.setToolTip("")
                self._summary_label.setStyleSheet(
                    f"font-size: 11px; color: {ThemeColors.PRIMARY}; font-weight: 600; "
                    f"background-color: rgba(59, 130, 246, 0.08); border: 1px solid rgba(59, 130, 246, 0.2); "
                    f"border-radius: 6px; padding: 6px 10px; margin-top: 4px;"
                )
                self._summary_label.show()
            if self._apply_btn:
                self._apply_btn.setEnabled(True)
        else:
            if self._summary_label:
                self._summary_label.setText("No valid patch found")
                self._summary_label.setToolTip("")
                self._summary_label.setStyleSheet(
                    f"font-size: 11px; color: {ThemeColors.ERROR}; font-weight: 600; "
                    f"background-color: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.2); "
                    f"border-radius: 6px; padding: 6px 10px; margin-top: 4px;"
                )
                self._summary_label.show()
            if self._apply_btn:
                self._apply_btn.setEnabled(False)
