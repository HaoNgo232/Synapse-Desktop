"""
AI Context Builder Dialog - Floating chat dialog cho AI-powered file discovery.

Giao dien cho phep nguoi dung:
1. Nhap mo ta cong viec (task description)
2. Tuy chon: include git diff, auto-apply ket qua
3. Nhan nut "Suggest Files" de LLM phan tich va goi y
4. Xem ket qua (danh sach files + reasoning)
5. Apply ket qua vao file tree (tu dong hoac thu cong)
6. Undo selection neu AI chon sai (khoi phuc selection cu)

Giao dien su dung card-based design nhat quan voi Settings view.
"""

import logging
from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QFrame,
    QScrollArea,
    QCheckBox,
    QApplication,
)
from PySide6.QtCore import Qt, QThreadPool

from core.theme import ThemeColors
from core.prompt_generator import generate_file_map
from core.utils.file_utils import TreeItem
from core.utils.git_utils import get_git_diffs
from core.prompting.context_builder_prompts import build_full_tree_string
from services.ai_context_worker import AIContextWorker
from services.settings_manager import load_app_settings, save_app_settings
from components.toast_qt import toast_success, toast_error

logger = logging.getLogger(__name__)


class AIContextBuilderDialog(QDialog):
    """
    Floating dialog cho AI Context Builder.

    Cho phep nguoi dung mo ta cong viec va nhan goi y files tu LLM.
    Ket qua co the duoc apply vao file tree tu dong hoac thu cong.
    """

    def __init__(
        self,
        tree: Optional[TreeItem],
        all_file_paths: set[str],
        workspace_root: Optional[Path],
        on_apply_selection: Optional[Callable[[List[str]], None]] = None,
        get_current_selection: Optional[Callable[[], List[str]]] = None,
        parent=None,
    ) -> None:
        """
        Khoi tao AI Context Builder Dialog.

        Args:
            tree: TreeItem root cua file tree hien tai
            all_file_paths: Set tat ca file paths trong workspace
            workspace_root: Duong dan goc cua workspace
            on_apply_selection: Callback khi apply selection moi
            get_current_selection: Callback lay selection hien tai tu parent view
            parent: Parent widget
        """
        super().__init__(parent)
        self._tree = tree
        self._all_file_paths = all_file_paths
        self._workspace_root = workspace_root
        self._on_apply_selection = on_apply_selection
        self._get_current_selection = get_current_selection
        self._last_suggested_paths: List[str] = []
        self._is_loading = False
        # Snapshot selection CUA PARENT VIEW truoc khi apply, phuc vu Undo
        self._snapshot_before_apply: Optional[List[str]] = None
        # Giu reference toi worker dang chay de tranh Python GC
        # xoa worker/signals truoc khi signal duoc deliver (PySide6 race condition)
        self._current_worker: Optional[AIContextWorker] = None

        self._setup_window()
        self._build_ui()

    def _setup_window(self) -> None:
        """Cau hinh cua so dialog."""
        self.setWindowTitle("AI Context Builder")
        self.setMinimumSize(560, 480)
        self.resize(620, 560)
        self.setModal(False)
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {ThemeColors.BG_PAGE};
            }}
        """
        )

    def _build_ui(self) -> None:
        """Xay dung giao dien dialog."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # === Header ===
        header = QLabel("AI Context Builder")
        header.setStyleSheet(
            f"font-size: 16px; font-weight: 600; color: {ThemeColors.TEXT_PRIMARY};"
        )
        layout.addWidget(header)

        desc = QLabel(
            "Describe your task and let AI suggest relevant files for your context."
        )
        desc.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY};")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # === Task Input ===
        input_label = QLabel("What do you want to do?")
        input_label.setStyleSheet(
            f"font-size: 13px; font-weight: 500; color: {ThemeColors.TEXT_PRIMARY};"
        )
        layout.addWidget(input_label)

        self._task_input = QTextEdit()
        self._task_input.setPlaceholderText(
            "e.g. Fix the login validation bug, "
            "Add dark mode toggle to settings page, "
            "Refactor the auth module to use JWT..."
        )
        self._task_input.setFixedHeight(80)
        self._task_input.setStyleSheet(
            f"""
            QTextEdit {{
                background: {ThemeColors.BG_SURFACE};
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QTextEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
        """
        )
        layout.addWidget(self._task_input)

        # === Context Options ===
        options_row = QHBoxLayout()
        options_row.setSpacing(16)

        # Style chung cho tat ca checkboxes trong options row
        checkbox_style = f"""
            QCheckBox {{
                color: {ThemeColors.TEXT_SECONDARY};
                font-size: 12px;
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 3px;
                background: {ThemeColors.BG_SURFACE};
            }}
            QCheckBox::indicator:checked {{
                background: {ThemeColors.PRIMARY};
                border-color: {ThemeColors.PRIMARY};
            }}
        """

        self._git_diff_checkbox = QCheckBox("Include Git Diff")
        self._git_diff_checkbox.setChecked(True)
        self._git_diff_checkbox.setStyleSheet(checkbox_style)
        options_row.addWidget(self._git_diff_checkbox)

        # Auto-apply checkbox: tu dong ap dung ket qua AI vao context tree
        settings = load_app_settings()
        self._auto_apply_checkbox = QCheckBox("Auto-apply")
        self._auto_apply_checkbox.setChecked(settings.ai_auto_apply)
        self._auto_apply_checkbox.setToolTip(
            "Automatically apply AI suggestions to the file tree"
        )
        self._auto_apply_checkbox.setStyleSheet(checkbox_style)
        self._auto_apply_checkbox.toggled.connect(self._on_auto_apply_toggled)
        options_row.addWidget(self._auto_apply_checkbox)

        options_row.addStretch()

        layout.addLayout(options_row)

        # === Action Buttons Row ===
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._suggest_btn = QPushButton("Suggest Files")
        self._suggest_btn.setFixedHeight(38)
        self._suggest_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._suggest_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {ThemeColors.PRIMARY};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 24px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background: {ThemeColors.PRIMARY_PRESSED};
            }}
            QPushButton:disabled {{
                background: {ThemeColors.BORDER};
                color: {ThemeColors.TEXT_MUTED};
            }}
        """
        )
        self._suggest_btn.clicked.connect(self._on_suggest_clicked)
        btn_row.addWidget(self._suggest_btn)

        btn_row.addStretch()

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.TEXT_MUTED};"
        )
        btn_row.addWidget(self._status_label)

        layout.addLayout(btn_row)

        # === Results Area ===
        self._results_frame = QFrame()
        self._results_frame.setStyleSheet(
            f"""
            QFrame {{
                background: {ThemeColors.BG_SURFACE};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
            }}
        """
        )
        results_layout = QVBoxLayout(self._results_frame)
        results_layout.setContentsMargins(16, 12, 16, 12)
        results_layout.setSpacing(8)

        results_header = QLabel("Suggested Files")
        results_header.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {ThemeColors.TEXT_PRIMARY}; border: none;"
        )
        results_layout.addWidget(results_header)

        # Scroll area cho danh sach files
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {ThemeColors.BORDER};
                border-radius: 3px;
                min-height: 20px;
            }}
        """
        )

        self._results_content = QLabel("No suggestions yet. Describe your task above.")
        self._results_content.setStyleSheet(
            f"font-size: 12px; color: {ThemeColors.TEXT_MUTED}; border: none;"
        )
        self._results_content.setWordWrap(True)
        self._results_content.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        scroll.setWidget(self._results_content)

        results_layout.addWidget(scroll, stretch=1)

        # Reasoning label
        self._reasoning_label = QLabel("")
        self._reasoning_label.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.TEXT_SECONDARY}; border: none;"
        )
        self._reasoning_label.setWordWrap(True)
        self._reasoning_label.setVisible(False)
        results_layout.addWidget(self._reasoning_label)

        layout.addWidget(self._results_frame, stretch=1)

        # === Bottom Action Bar ===
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        self._apply_btn = QPushButton("Apply to Tree")
        self._apply_btn.setFixedHeight(36)
        self._apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_btn.setEnabled(False)
        self._apply_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {ThemeColors.SUCCESS_BG};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 20px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {ThemeColors.SUCCESS_BG_HOVER};
            }}
            QPushButton:disabled {{
                background: {ThemeColors.BORDER};
                color: {ThemeColors.TEXT_MUTED};
            }}
        """
        )
        self._apply_btn.clicked.connect(self._on_apply_clicked)
        bottom_row.addWidget(self._apply_btn)

        # Nut Undo: khoi phuc lai selection TRUOC KHI apply
        self._undo_btn = QPushButton("Undo")
        self._undo_btn.setFixedHeight(36)
        self._undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._undo_btn.setVisible(False)  # An mac dinh, chi hien sau khi apply
        self._undo_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                color: {ThemeColors.WARNING};
                border: 1px solid {ThemeColors.WARNING};
                border-radius: 8px;
                padding: 0 16px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: rgba(255, 170, 0, 0.08);
            }}
        """
        )
        self._undo_btn.clicked.connect(self._on_undo_clicked)
        bottom_row.addWidget(self._undo_btn)

        bottom_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(36)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding: 0 20px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {ThemeColors.BG_ELEVATED};
            }}
        """
        )
        close_btn.clicked.connect(self.close)
        bottom_row.addWidget(close_btn)

        layout.addLayout(bottom_row)

    # === Slots ===

    def _on_auto_apply_toggled(self, checked: bool) -> None:
        """
        Luu trang thai auto-apply vao AppSettings khi user toggle checkbox.

        Args:
            checked: Trang thai moi cua checkbox
        """
        settings = load_app_settings()
        settings.ai_auto_apply = checked
        save_app_settings(settings)

    def _on_suggest_clicked(self) -> None:
        """
        Xu ly khi nguoi dung nhan nut Suggest Files.

        Doc settings, tao file tree, (optional) git diff,
        tao worker va quang vao thread pool.
        Repo Map duoc generate TRONG worker (background thread) de tranh UI freeze.
        """
        user_query = self._task_input.toPlainText().strip()
        if not user_query:
            toast_error("Please describe your task first.")
            return

        # Doc settings
        settings = load_app_settings()
        if not settings.ai_api_key:
            toast_error("Please configure AI API Key in Settings first.")
            return
        if not settings.ai_model_id:
            toast_error("Please select an AI model in Settings first.")
            return

        # Tao file tree
        if self._tree is None:
            toast_error("No project loaded. Open a folder first.")
            return

        file_tree_map = generate_file_map(
            self._tree,
            self._all_file_paths,
            workspace_root=self._workspace_root,
            use_relative_paths=True,
        )

        # Optional: Git diff
        git_diff_str: Optional[str] = None
        if self._git_diff_checkbox.isChecked() and self._workspace_root:
            try:
                diff_result = get_git_diffs(self._workspace_root)
                if diff_result is not None:
                    _, git_diff_str = build_full_tree_string(
                        file_tree_map, diff_result, include_git=True
                    )
            except Exception as e:
                logger.warning("Could not get git diffs: %s", e)

        # An nut Undo khi bat dau request moi
        self._undo_btn.setVisible(False)

        # Set loading TRUOC khi bat dau bat ky I/O nao (Bug #3 fix)
        self._set_loading(True)

        # Tao worker - truyen all_file_paths de worker tu generate Repo Map
        # tren background thread, KHONG block main thread
        worker = AIContextWorker(
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            model_id=settings.ai_model_id,
            file_tree=file_tree_map,
            user_query=user_query,
            git_diff=git_diff_str,
            all_file_paths=list(self._all_file_paths),
            workspace_root=self._workspace_root,
        )
        worker.signals.finished.connect(self._on_worker_finished)
        worker.signals.error.connect(self._on_worker_error)
        worker.signals.progress.connect(self._on_worker_progress)

        # GIU REFERENCE de tranh GC xoa worker truoc khi signal duoc deliver
        self._current_worker = worker

        QThreadPool.globalInstance().start(worker)

    def _on_worker_finished(self, paths: list, reasoning: str, usage: dict) -> None:
        """
        Xu ly khi worker hoan thanh thanh cong.

        Hien thi danh sach files va reasoning tren UI.
        Neu auto-apply dang bat, tu dong ap dung ket qua vao context tree.
        """
        self._current_worker = None  # Giai phong reference sau khi worker xong
        self._set_loading(False)
        self._last_suggested_paths = paths

        if not paths:
            self._results_content.setText("AI could not find relevant files.")
            self._results_content.setStyleSheet(
                f"font-size: 12px; color: {ThemeColors.WARNING}; border: none;"
            )
            self._apply_btn.setEnabled(False)
        else:
            # Hien thi danh sach files
            file_list = "\n".join(f"  {p}" for p in paths)
            self._results_content.setText(
                f"{len(paths)} files suggested:\n\n{file_list}"
            )
            self._results_content.setStyleSheet(
                f"font-size: 12px; color: {ThemeColors.TEXT_PRIMARY}; border: none;"
            )
            self._apply_btn.setEnabled(True)

        # Hien thi reasoning
        if reasoning:
            self._reasoning_label.setText(f"Reasoning: {reasoning}")
            self._reasoning_label.setVisible(True)
        else:
            self._reasoning_label.setVisible(False)

        # Hien thi token usage
        if usage:
            total = usage.get("total_tokens", 0)
            self._status_label.setText(f"Tokens used: {total:,}")
        else:
            self._status_label.setText("Done")

        # Auto-apply: Neu checkbox bat va co paths, tu dong apply vao tree
        if self._auto_apply_checkbox.isChecked() and paths:
            self._do_apply(show_toast=True)

    def _on_worker_error(self, error_msg: str) -> None:
        """Xu ly khi worker gap loi."""
        self._current_worker = None  # Giai phong reference sau khi worker xong
        self._set_loading(False)
        self._results_content.setText(f"Error: {error_msg}")
        self._results_content.setStyleSheet(
            f"font-size: 12px; color: {ThemeColors.ERROR}; border: none;"
        )
        toast_error(error_msg)

    def _on_worker_progress(self, status: str) -> None:
        """Cap nhat status text khi worker dang chay."""
        self._status_label.setText(status)

    def _on_apply_clicked(self) -> None:
        """
        Apply danh sach files duoc suggest vao file tree (nhan thu cong).

        Goi callback on_apply_selection voi danh sach paths.
        """
        if not self._last_suggested_paths:
            return
        self._do_apply(show_toast=True)
        self.close()

    def _do_apply(self, show_toast: bool = False) -> None:
        """
        Logic chung de apply suggested paths vao context tree.

        Duoc goi boi auto-apply (sau khi worker xong) hoac manual apply.
        Luu snapshot selection hien tai CUA PARENT VIEW de phuc vu Undo.

        Args:
            show_toast: Co hien thi toast notification hay khong
        """
        if not self._last_suggested_paths or not self._on_apply_selection:
            return

        # Chup snapshot selection hien tai CUA PARENT TREE truoc khi apply
        # De Undo co the khoi phuc lai dung trang thai
        if self._get_current_selection:
            try:
                self._snapshot_before_apply = list(self._get_current_selection())
            except Exception:
                self._snapshot_before_apply = None
        else:
            self._snapshot_before_apply = None

        self._on_apply_selection(self._last_suggested_paths)

        if show_toast:
            toast_success(
                f"Applied {len(self._last_suggested_paths)} files to context."
            )

        # Hien thi nut Undo de user co the khoi phuc
        self._undo_btn.setVisible(True)
        # Disable nut Apply sau khi da ap dung (tranh double-apply)
        self._apply_btn.setEnabled(False)

    def _on_undo_clicked(self) -> None:
        """
        Khoi phuc selection ve trang thai TRUOC KHI apply.

        Neu co snapshot -> apply lai snapshot cu.
        Neu khong co snapshot -> xoa selection (fallback an toan).
        """
        if self._on_apply_selection:
            # Khoi phuc selection cu thay vi xoa sach
            restore_paths = self._snapshot_before_apply or []
            self._on_apply_selection(restore_paths)
            toast_success("Selection restored to previous state.")

        self._undo_btn.setVisible(False)
        self._apply_btn.setEnabled(True)
        self._snapshot_before_apply = None

    def _set_loading(self, loading: bool) -> None:
        """Toggle trang thai loading tren UI."""
        self._is_loading = loading
        self._suggest_btn.setEnabled(not loading)
        self._task_input.setEnabled(not loading)
        self._apply_btn.setEnabled(False)

        if loading:
            self._suggest_btn.setText("Analyzing...")
            self._results_content.setText("AI is analyzing your project...")
            self._results_content.setStyleSheet(
                f"font-size: 12px; color: {ThemeColors.TEXT_MUTED}; border: none;"
            )
            self._reasoning_label.setVisible(False)
            self._status_label.setText("Connecting...")
            # Process events de UI update ngay
            QApplication.processEvents()
        else:
            self._suggest_btn.setText("Suggest Files")

    def closeEvent(self, event) -> None:
        """
        Cleanup khi dialog bi dong: disconnect signals tu worker dang chay.

        Tranh crash khi worker emit signal vao dialog da bi destroy (Bug #4 fix).
        """
        if self._current_worker is not None:
            self._current_worker.cancel()
            try:
                self._current_worker.signals.finished.disconnect(
                    self._on_worker_finished
                )
                self._current_worker.signals.error.disconnect(self._on_worker_error)
                self._current_worker.signals.progress.disconnect(
                    self._on_worker_progress
                )
            except RuntimeError:
                # Signal da bi disconnect hoac object da bi destroy
                pass
            self._current_worker = None
        super().closeEvent(event)
