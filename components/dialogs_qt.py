"""
Dialogs Qt - PySide6 versions of all dialogs.

Port từ components/dialogs/ (Flet) sang QDialog-based.
"""

import json
import threading
from pathlib import Path
from typing import Optional, List, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from core.utils.repo_manager import RepoManager

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QPlainTextEdit, QScrollArea, QFrame, QWidget,
    QLineEdit, QCheckBox, QGroupBox, QMessageBox, QProgressBar,
    QGridLayout, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QFont

from core.theme import ThemeColors
from core.utils.qt_utils import schedule_background, run_on_main_thread
from services.clipboard_utils import copy_to_clipboard


# ============================================================
# Base Dialog
# ============================================================

class BaseDialogQt(QDialog):
    """Base class cho tất cả dialogs — cung cấp styling chung."""

    def __init__(self, parent: Optional[QWidget] = None, title: str = ""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(450)
        self.setStyleSheet(
            f"QDialog {{ background-color: {ThemeColors.BG_SURFACE}; }}"
        )

    def _make_primary_btn(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("class", "primary")
        return btn

    def _make_danger_btn(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("class", "danger")
        return btn

    def _make_outlined_btn(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("class", "outlined")
        return btn

    def _make_label(self, text: str, muted: bool = False) -> QLabel:
        label = QLabel(text)
        color = ThemeColors.TEXT_MUTED if muted else ThemeColors.TEXT_PRIMARY
        label.setStyleSheet(f"color: {color};")
        label.setWordWrap(True)
        return label

    def _make_status_label(self) -> QLabel:
        label = QLabel("")
        label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY};")
        return label


# ============================================================
# Security Dialog
# ============================================================

class SecurityDialogQt(BaseDialogQt):
    """Dialog khi phát hiện secrets trong content."""

    def __init__(
        self,
        parent: QWidget,
        prompt: str,
        matches: list,
        on_copy_anyway: Callable[[str], None],
    ):
        super().__init__(parent, "Security Warning")
        self.prompt = prompt
        self.matches = matches
        self.on_copy_anyway = on_copy_anyway
        self.setMinimumWidth(550)
        self._build_ui()

    def _build_ui(self) -> None:
        from core.security_check import format_security_warning
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Warning header
        header = QHBoxLayout()
        icon = QLabel("⚠️")
        icon.setStyleSheet("font-size: 20px;")
        header.addWidget(icon)
        title = QLabel("Security Warning")
        title.setStyleSheet(
            f"font-weight: bold; font-size: 16px; color: {ThemeColors.WARNING};"
        )
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Warning message
        warning_msg = format_security_warning(self.matches)
        msg_label = self._make_label(warning_msg)
        layout.addWidget(msg_label)

        # Details scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(200)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(4, 4, 4, 4)
        details_layout.setSpacing(4)

        for match in self.matches:
            display_name = Path(match.file_path).name if match.file_path else ""
            file_info = f" in {display_name}" if display_name else ""

            item = QFrame()
            item.setStyleSheet(
                f"background-color: {ThemeColors.BG_SURFACE}; "
                f"border-radius: 4px; padding: 6px;"
            )
            item_layout = QVBoxLayout(item)
            item_layout.setContentsMargins(6, 4, 6, 4)
            item_layout.setSpacing(2)

            type_label = QLabel(
                f"🔒 {match.secret_type}{file_info} (Line {match.line_number})"
            )
            type_label.setStyleSheet(
                f"font-size: 12px; font-weight: 600; color: {ThemeColors.TEXT_PRIMARY};"
            )
            item_layout.addWidget(type_label)

            val_label = QLabel(f"Value: {match.redacted_preview}")
            val_label.setStyleSheet(
                f"font-size: 11px; color: {ThemeColors.TEXT_SECONDARY}; "
                f"font-family: monospace; font-style: italic;"
            )
            item_layout.addWidget(val_label)
            details_layout.addWidget(item)

        details_layout.addStretch()
        scroll.setWidget(details_widget)
        layout.addWidget(scroll)

        # Info text
        info = QLabel("Please review your content before sharing with AI tools.")
        info.setStyleSheet(
            f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY}; font-style: italic;"
        )
        layout.addWidget(info)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = self._make_outlined_btn("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        copy_results_btn = self._make_outlined_btn("Copy Results")
        copy_results_btn.clicked.connect(self._copy_results)
        btn_row.addWidget(copy_results_btn)

        copy_anyway_btn = QPushButton("Copy Anyway")
        copy_anyway_btn.setStyleSheet(
            f"background-color: {ThemeColors.WARNING}; color: #FFFFFF; "
            f"font-weight: bold; padding: 8px 16px; border-radius: 6px;"
        )
        copy_anyway_btn.clicked.connect(self._do_copy_anyway)
        btn_row.addWidget(copy_anyway_btn)

        layout.addLayout(btn_row)

    @Slot()
    def _copy_results(self) -> None:
        results_data = [
            {
                "type": m.secret_type,
                "file": m.file_path or "N/A",
                "line": m.line_number,
                "preview": m.redacted_preview,
            }
            for m in self.matches
        ]
        copy_to_clipboard(json.dumps(results_data, indent=2, ensure_ascii=False))

    @Slot()
    def _do_copy_anyway(self) -> None:
        self.accept()
        self.on_copy_anyway(self.prompt)


# ============================================================
# Diff Only Dialog
# ============================================================

class DiffOnlyDialogQt(BaseDialogQt):
    """Dialog cho Copy Diff Only."""

    def __init__(
        self,
        parent: QWidget,
        workspace: Path,
        build_prompt_callback: Callable,
        instructions: str = "",
        on_success: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent, "Copy Diff Only")
        self.workspace = workspace
        self.build_prompt_callback = build_prompt_callback
        self.instructions = instructions
        self.on_success = on_success
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(self._make_label(
            "Copy only git changes instead of full source code."
        ))
        layout.addWidget(self._make_label(
            "Ideal for: code review, bug fixing, feature validation.", muted=True
        ))

        # Options
        form = QGridLayout()
        form.setSpacing(8)

        form.addWidget(QLabel("Recent commits:"), 0, 0)
        self._num_commits = QLineEdit("0")
        self._num_commits.setFixedWidth(100)
        self._num_commits.setPlaceholderText("0 = uncommitted only")
        form.addWidget(self._num_commits, 0, 1)

        form.addWidget(QLabel("Filter files:"), 0, 2)
        self._file_pattern = QLineEdit()
        self._file_pattern.setPlaceholderText("e.g., *.py, src/*.ts")
        form.addWidget(self._file_pattern, 0, 3)
        layout.addLayout(form)

        self._include_staged = QCheckBox("Include staged changes")
        self._include_staged.setChecked(True)
        layout.addWidget(self._include_staged)

        self._include_unstaged = QCheckBox("Include unstaged changes")
        self._include_unstaged.setChecked(True)
        layout.addWidget(self._include_unstaged)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {ThemeColors.BORDER};")
        layout.addWidget(sep)

        layout.addWidget(self._make_label("Enhanced context (larger output):"))

        self._include_file_content = QCheckBox("Include changed file content")
        layout.addWidget(self._include_file_content)

        self._include_tree = QCheckBox("Include project tree structure")
        layout.addWidget(self._include_tree)

        self._status = self._make_status_label()
        layout.addWidget(self._status)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = self._make_outlined_btn("Cancel")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        copy_btn = self._make_primary_btn("Copy Diff")
        copy_btn.clicked.connect(self._do_copy)
        btn_row.addWidget(copy_btn)
        layout.addLayout(btn_row)

    @Slot()
    def _do_copy(self) -> None:
        from core.utils.git_utils import get_diff_only
        from core.token_counter import count_tokens

        try:
            commits = max(0, int(self._num_commits.text() or "0"))
        except ValueError:
            commits = 0

        self._status.setText("Getting diff...")
        self._status.setStyleSheet(f"color: {ThemeColors.TEXT_SECONDARY};")

        result = get_diff_only(
            self.workspace,
            num_commits=commits,
            include_staged=self._include_staged.isChecked(),
            include_unstaged=self._include_unstaged.isChecked(),
        )

        if result.error:
            self._status.setText(f"Error: {result.error}")
            self._status.setStyleSheet(f"color: {ThemeColors.ERROR};")
            return

        if not result.diff_content.strip():
            self._status.setText("No changes found")
            self._status.setStyleSheet(f"color: {ThemeColors.WARNING};")
            return

        prompt = self.build_prompt_callback(
            result,
            self.instructions,
            self._include_file_content.isChecked(),
            self._include_tree.isChecked(),
        )

        success, message = copy_to_clipboard(prompt)
        if success:
            self.accept()
            token_count = count_tokens(prompt)
            if self.on_success:
                self.on_success(
                    f"Diff copied! ({token_count:,} tokens, "
                    f"+{result.insertions}/-{result.deletions} lines, "
                    f"{result.files_changed} files)"
                )
        else:
            self._status.setText(f"Copy failed: {message}")
            self._status.setStyleSheet(f"color: {ThemeColors.ERROR};")


# ============================================================
# Remote Repo Dialog
# ============================================================

class RemoteRepoDialogQt(BaseDialogQt):
    """Dialog clone remote GitHub repositories."""

    clone_finished = Signal(object)  # Path or Exception

    def __init__(
        self,
        parent: QWidget,
        repo_manager: "RepoManager",
        on_clone_success: Callable[[Path], None],
    ):
        super().__init__(parent, "Open Remote Repository")
        self.repo_manager = repo_manager
        self.on_clone_success = on_clone_success
        self.clone_finished.connect(self._handle_clone_result)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(self._make_label(
            "Enter GitHub URL or shorthand (owner/repo) to clone repository."
        ))

        self._url_field = QLineEdit()
        self._url_field.setPlaceholderText("owner/repo or https://github.com/owner/repo")
        layout.addWidget(self._url_field)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.hide()
        layout.addWidget(self._progress)

        self._status = self._make_status_label()
        layout.addWidget(self._status)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = self._make_outlined_btn("Cancel")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        self._clone_btn = self._make_primary_btn("Clone")
        self._clone_btn.clicked.connect(self._start_clone)
        btn_row.addWidget(self._clone_btn)
        layout.addLayout(btn_row)

    @Slot()
    def _start_clone(self) -> None:
        url = self._url_field.text().strip()
        if not url:
            self._status.setText("Please enter a GitHub URL")
            self._status.setStyleSheet(f"color: {ThemeColors.ERROR};")
            return

        self._progress.show()
        self._clone_btn.setEnabled(False)
        self._status.setText("Cloning...")

        def do_clone():
            try:
                repo_path = self.repo_manager.clone_repo(url)
                self.clone_finished.emit(repo_path)
            except Exception as ex:
                self.clone_finished.emit(ex)

        threading.Thread(target=do_clone, daemon=True).start()

    @Slot(object)
    def _handle_clone_result(self, result: object) -> None:
        self._progress.hide()
        self._clone_btn.setEnabled(True)
        if isinstance(result, Path):
            self.accept()
            self.on_clone_success(result)
        elif isinstance(result, Exception):
            self._status.setText(str(result))
            self._status.setStyleSheet(f"color: {ThemeColors.ERROR};")


# ============================================================
# Cache Management Dialog
# ============================================================

class CacheManagementDialogQt(BaseDialogQt):
    """Dialog quản lý cached repositories."""

    def __init__(
        self,
        parent: QWidget,
        repo_manager: "RepoManager",
        on_open_repo: Callable[[Path], None],
    ):
        super().__init__(parent, "Cached Repositories")
        self.repo_manager = repo_manager
        self.on_open_repo = on_open_repo
        self.setMinimumWidth(600)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        cached_repos = self.repo_manager.get_cached_repos()
        total_size = self.repo_manager.get_cache_size()
        total_size_str = self.repo_manager.format_size(total_size)

        # Header
        header = QHBoxLayout()
        header.addWidget(self._make_label(f"Cached repositories: {len(cached_repos)}"))
        header.addStretch()
        header.addWidget(self._make_label(f"Total: {total_size_str}", muted=True))
        layout.addLayout(header)

        # Repo list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(400)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(4, 4, 4, 4)
        self._list_layout.setSpacing(8)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._list_widget)
        layout.addWidget(scroll)

        self._status = self._make_status_label()
        layout.addWidget(self._status)

        # Buttons
        btn_row = QHBoxLayout()
        clear_btn = self._make_danger_btn("Clear All")
        clear_btn.clicked.connect(self._clear_all)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        close_btn = self._make_outlined_btn("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._refresh_list()

    def _refresh_list(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item and (widget := item.widget()):
                widget.deleteLater()

        cached_repos = self.repo_manager.get_cached_repos()
        if not cached_repos:
            self._list_layout.addWidget(self._make_label("No repositories cloned yet.", muted=True))
            return

        for repo in cached_repos:
            card = self._build_repo_card(repo)
            self._list_layout.addWidget(card)

    def _build_repo_card(self, repo) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"background-color: {ThemeColors.BG_SURFACE}; "
            f"border: 1px solid {ThemeColors.BORDER}; border-radius: 8px; padding: 12px;"
        )
        card_layout = QHBoxLayout(card)

        info_layout = QVBoxLayout()
        name_label = QLabel(repo.name)
        name_label.setStyleSheet(
            f"font-weight: 600; color: {ThemeColors.TEXT_PRIMARY};"
        )
        info_layout.addWidget(name_label)

        size_str = self.repo_manager.format_size(repo.size_bytes)
        time_str = repo.last_modified.strftime("%Y-%m-%d %H:%M") if repo.last_modified else ""
        meta = QLabel(f"📁 {size_str}  🕐 {time_str}")
        meta.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY};")
        info_layout.addWidget(meta)
        card_layout.addLayout(info_layout, stretch=1)

        open_btn = self._make_outlined_btn("Open")
        open_btn.clicked.connect(lambda checked=False, p=repo.path: self._open_repo(p))
        card_layout.addWidget(open_btn)

        del_btn = QPushButton("🗑")
        del_btn.setFixedWidth(32)
        del_btn.setStyleSheet(f"color: {ThemeColors.ERROR}; border: none;")
        del_btn.clicked.connect(lambda checked=False, n=repo.name: self._delete_repo(n))
        card_layout.addWidget(del_btn)

        return card

    def _open_repo(self, path: Path) -> None:
        self.accept()
        self.on_open_repo(path)

    def _delete_repo(self, name: str) -> None:
        if self.repo_manager.delete_repo(name):
            self._status.setText(f"Deleted: {name}")
            self._status.setStyleSheet(f"color: {ThemeColors.SUCCESS};")
            self._refresh_list()
        else:
            self._status.setText(f"Failed to delete: {name}")
            self._status.setStyleSheet(f"color: {ThemeColors.ERROR};")

    @Slot()
    def _clear_all(self) -> None:
        reply = QMessageBox.question(
            self, "Clear All",
            "Delete all cached repositories?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.repo_manager.clear_cache()
            self._refresh_list()
            self._status.setText("Cache cleared")


# ============================================================
# Dirty Repo Dialog
# ============================================================

class DirtyRepoDialogQt(BaseDialogQt):
    """Dialog khi repo có uncommitted changes."""

    def __init__(
        self,
        parent: QWidget,
        repo_manager: "RepoManager",
        repo_path: Path,
        repo_name: str,
        on_done: Callable[[str], None],
    ):
        super().__init__(parent, "Uncommitted Changes")
        self.repo_manager = repo_manager
        self.repo_path = repo_path
        self.repo_name = repo_name
        self.on_done = on_done
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("⚠️ Uncommitted Changes")
        title.setStyleSheet(
            f"font-weight: bold; font-size: 14px; color: {ThemeColors.WARNING};"
        )
        layout.addWidget(title)
        layout.addWidget(self._make_label(
            f"Repository '{self.repo_name}' has uncommitted local changes.\n"
            "What would you like to do?"
        ))

        btn_row = QHBoxLayout()
        cancel = self._make_outlined_btn("Cancel")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        btn_row.addStretch()

        discard = self._make_danger_btn("Discard & Pull")
        discard.clicked.connect(self._discard_and_pull)
        btn_row.addWidget(discard)

        stash = self._make_primary_btn("Stash & Pull")
        stash.clicked.connect(self._stash_and_pull)
        btn_row.addWidget(stash)
        layout.addLayout(btn_row)

    @Slot()
    def _stash_and_pull(self) -> None:
        self.accept()

        def work():
            try:
                self.repo_manager.stash_changes(self.repo_path)
                self.repo_manager._update_repo(self.repo_path, None, None)
                run_on_main_thread(
                    lambda: self.on_done(f"Updated {self.repo_name} (stashed)")
                )
            except Exception as e:
                run_on_main_thread(lambda: self.on_done(f"Error: {e}"))

        threading.Thread(target=work, daemon=True).start()

    @Slot()
    def _discard_and_pull(self) -> None:
        reply = QMessageBox.warning(
            self, "Confirm Discard",
            f"PERMANENTLY DELETE all local changes in '{self.repo_name}'?\n"
            "This cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.accept()

        def work():
            try:
                self.repo_manager.discard_changes(self.repo_path)
                self.repo_manager._update_repo(self.repo_path, None, None)
                run_on_main_thread(
                    lambda: self.on_done(f"Updated {self.repo_name} (discarded)")
                )
            except Exception as e:
                run_on_main_thread(lambda: self.on_done(f"Error: {e}"))

        threading.Thread(target=work, daemon=True).start()


# ============================================================
# File Preview Dialog
# ============================================================

class FilePreviewDialogQt(BaseDialogQt):
    """Dialog preview nội dung file với line numbers."""

    MAX_PREVIEW_SIZE = 1024 * 1024  # 1MB
    MAX_LINES = 5000

    def __init__(
        self,
        parent: QWidget,
        file_path: str,
        content: Optional[str] = None,
        highlight_line: Optional[int] = None,
    ):
        super().__init__(parent, "File Preview")
        self.file_path = file_path
        self._content = content
        self._highlight_line = highlight_line
        self.setMinimumSize(900, 650)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        path_obj = Path(self.file_path)
        file_name = path_obj.name

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel(f"📄 {file_name}"))
        header.addStretch()

        from core.utils.language_utils import get_language_from_path
        language = get_language_from_path(self.file_path)

        # Read content
        if self._content is None:
            from core.utils.file_utils import is_binary_by_extension
            if is_binary_by_extension(path_obj):
                self._show_error_content(layout, "Cannot preview binary file.")
                return
            if not path_obj.exists():
                self._show_error_content(layout, "File not found.")
                return
            try:
                size = path_obj.stat().st_size
                if size > self.MAX_PREVIEW_SIZE:
                    self._show_error_content(layout, f"File too large ({size / 1048576:.1f} MB)")
                    return
                self._content = path_obj.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                self._show_error_content(layout, f"Error: {e}")
                return

        lines = self._content.split("\n")
        truncated = len(lines) > self.MAX_LINES
        if truncated:
            lines = lines[:self.MAX_LINES]
            self._content = "\n".join(lines)

        info = QLabel(f"{language} • {len(lines)} lines")
        info.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY};")
        header.addWidget(info)
        layout.addLayout(header)

        # Highlight warning
        if self._highlight_line and 1 <= self._highlight_line <= len(lines):
            warn = QLabel(f"⚠️ Security issue found at line {self._highlight_line}")
            warn.setStyleSheet(
                f"background-color: #422006; color: {ThemeColors.WARNING}; "
                f"padding: 8px; border-radius: 4px; font-weight: bold;"
            )
            layout.addWidget(warn)

        # Code editor (read only) with syntax highlighting
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setFont(QFont("JetBrains Mono, Fira Code, Consolas", 12))
        self._text_edit.setStyleSheet(
            f"QTextEdit {{ "
            f"  background-color: #282a36; color: #f8f8f2; "
            f"  border: 1px solid {ThemeColors.BORDER}; border-radius: 4px; padding: 8px; "
            f"}} "
            f"QScrollBar:vertical {{ "
            f"  background: #1e1f29; width: 14px; margin: 0; border-radius: 7px; "
            f"}} "
            f"QScrollBar::handle:vertical {{ "
            f"  background: #6272a4; border-radius: 7px; min-height: 30px; "
            f"}} "
            f"QScrollBar::handle:vertical:hover {{ "
            f"  background: #8be9fd; "
            f"}} "
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ "
            f"  height: 0; "
            f"}} "
            f"QScrollBar:horizontal {{ "
            f"  background: #1e1f29; height: 14px; margin: 0; border-radius: 7px; "
            f"}} "
            f"QScrollBar::handle:horizontal {{ "
            f"  background: #6272a4; border-radius: 7px; min-width: 30px; "
            f"}} "
            f"QScrollBar::handle:horizontal:hover {{ "
            f"  background: #8be9fd; "
            f"}} "
            f"QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ "
            f"  width: 0; "
            f"}}"
        )
        self._text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        
        # Apply syntax highlighting via Pygments + Dracula
        highlighted_html = self._highlight_code(self._content, language)
        if highlighted_html:
            self._text_edit.setHtml(highlighted_html)
        else:
            self._text_edit.setPlainText(self._content)
        
        layout.addWidget(self._text_edit, stretch=1)

        if truncated:
            warn_label = QLabel(f"⚠️ Showing first {self.MAX_LINES} lines only")
            warn_label.setStyleSheet(f"color: {ThemeColors.WARNING}; font-size: 12px;")
            layout.addWidget(warn_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        copy_btn = self._make_outlined_btn("Copy")
        copy_btn.clicked.connect(self._copy_content)
        btn_row.addWidget(copy_btn)

        close_btn = self._make_outlined_btn("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _show_error_content(self, layout: QVBoxLayout, message: str) -> None:
        error_label = QLabel(f"❌ {message}")
        error_label.setStyleSheet(
            f"color: {ThemeColors.ERROR}; padding: 40px; font-size: 14px;"
        )
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(error_label, stretch=1)

        close_btn = self._make_outlined_btn("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    @Slot()
    def _copy_content(self) -> None:
        if self._content:
            copy_to_clipboard(self._content)

    @staticmethod
    def _highlight_code(content: str, language: str) -> Optional[str]:
        """Apply Pygments syntax highlighting with Dracula theme."""
        try:
            from pygments import highlight
            from pygments.lexers import get_lexer_by_name, TextLexer
            from pygments.formatters import HtmlFormatter

            try:
                lexer = get_lexer_by_name(language, stripall=True)
            except Exception:
                lexer = TextLexer()

            # Dracula-inspired inline styles
            formatter = HtmlFormatter(
                style="dracula",
                noclasses=True,  # Use inline styles
                nowrap=False,
                linenos=True,
                linenostart=1,
                lineanchors="line",
                prestyles=(
                    "background-color: #282a36; color: #f8f8f2; "
                    "font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace; "
                    "font-size: 12px; padding: 12px; border-radius: 4px; "
                    "line-height: 1.5;"
                ),
            )
            return highlight(content, lexer, formatter)
        except ImportError:
            return None
        except Exception:
            return None

    @staticmethod
    def show_preview(
        parent: QWidget,
        file_path: str,
        content: Optional[str] = None,
        highlight_line: Optional[int] = None,
    ) -> None:
        """Convenience static method to show the dialog."""
        dialog = FilePreviewDialogQt(parent, file_path, content, highlight_line)
        dialog.exec()
