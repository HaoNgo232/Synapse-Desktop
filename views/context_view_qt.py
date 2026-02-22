"""
Context View (PySide6) - Tab để chọn files và copy context.

Refactored using Mixin pattern for better organization.
"""

import threading
from pathlib import Path
from typing import Optional, Set, List, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from core.utils.repo_manager import RepoManager

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Slot, QTimer, QObject


from core.utils.file_utils import TreeItem
from services.file_watcher import FileWatcher, WatcherCallbacks
from services.settings_manager import update_app_setting
from config.output_format import (
    OutputStyle,
    get_style_by_id,
    DEFAULT_OUTPUT_STYLE,
)

# Import mixins
from views.context._ui_builder import UIBuilderMixin
from views.context._copy_actions import CopyActionsMixin
from views.context._related_files import RelatedFilesMixin
from views.context._tree_management import TreeManagementMixin


class ContextViewQt(
    UIBuilderMixin,
    CopyActionsMixin,
    RelatedFilesMixin,
    TreeManagementMixin,
    QWidget,
):
    """View cho Context tab - PySide6 version."""

    def __init__(
        self,
        get_workspace: Callable[[], Optional[Path]],
        parent: Optional[QWidget] = None,
        prompt_builder=None,
        clipboard_service=None,
    ):
        super().__init__(parent)
        self.get_workspace = get_workspace

        # State
        self.tree: Optional[TreeItem] = None
        self._selected_output_style: OutputStyle = DEFAULT_OUTPUT_STYLE
        self._last_ignored_patterns: List[str] = []
        self._related_mode_active: bool = False
        self._related_depth: int = 1
        self._last_added_related_files: Set[str] = set()
        self._resolving_related: bool = False  # Guard against recursive triggers
        self._loading_lock = threading.Lock()
        self._is_loading = False
        self._pending_refresh = False
        self._token_generation = 0
        # Note: These attributes are used by mixins but owned by ContextViewQt
        # CopyActionsMixin worker/signal references — must be kept alive
        # to prevent GC while background work is in progress
        self._current_copy_worker = None
        self._current_copy_signals = None
        self._current_security_worker = None
        self._current_security_signals = None
        # Generation counter — incremented each copy request to discard stale results
        self._copy_generation: int = 0
        self._copy_buttons_disabled: bool = False
        # Stale worker/signal refs — kept alive until their callback fires
        self._stale_workers: list = []
        # Prompt-level cache — skips heavy work when nothing changed
        from views.context._copy_actions import PromptCache

        self._prompt_cache: PromptCache = PromptCache()
        # TreeManagementMixin
        self._repo_manager: Optional[RepoManager] = None  # Lazy init as RepoManager

        # Services (with dependency injection support)
        self._file_watcher: Optional[FileWatcher] = FileWatcher()

        if prompt_builder is None:
            from services.prompt_build_service import PromptBuildService

            prompt_builder = PromptBuildService()
        self._prompt_builder = prompt_builder

        if clipboard_service is None:
            from services.prompt_build_service import QtClipboardService

            clipboard_service = QtClipboardService()
        self._clipboard_service = clipboard_service

        # Build UI (from UIBuilderMixin)
        self._build_ui()

    # ===== Public API =====

    def on_workspace_changed(self, workspace_path: Path) -> None:
        """Handle workspace change."""
        from core.logging_config import log_info

        log_info(f"[ContextView] Workspace changing to: {workspace_path}")

        # 0. Invalidate any pending copy operations by incrementing generation.
        # Old workers will still run but their results will be ignored.
        self._begin_copy_operation()
        self._set_copy_buttons_enabled(True)

        # 1. Stop file watcher for old workspace
        if self._file_watcher:
            self._file_watcher.stop()

        # 2. Deactivate related mode to clean up state
        if self._related_mode_active:
            self._related_mode_active = False
            self._last_added_related_files.clear()
            self._related_menu_btn.setText("Related: Off")

        # 3. Clear all caches for old workspace via CacheRegistry
        from services.cache_registry import cache_registry

        cache_registry.invalidate_for_workspace()
        self._prompt_cache.invalidate_all()

        # 4. Load new tree (this increments generation counter, cancels old workers)
        self.file_tree_widget.load_tree(workspace_path)
        self.tree = self.file_tree_widget.get_model()._root_node  # type: ignore

        # 5. Reset token display
        self._token_count_label.setText("0 tokens")
        self._token_stats.update_stats(
            file_count=0, file_tokens=0, instruction_tokens=0
        )

        # 6. Start file watcher for new workspace
        if self._file_watcher and workspace_path.exists():
            self._file_watcher.start(
                path=workspace_path,
                callbacks=WatcherCallbacks(
                    on_file_modified=self._on_file_modified,
                    on_file_created=self._on_file_created,
                    on_file_deleted=self._on_file_deleted,
                    on_batch_change=self._on_file_system_changed,
                ),
                debounce_seconds=0.5,
            )

    def restore_tree_state(
        self, selected_files: List[str], expanded_folders: List[str]
    ) -> None:
        """Restore tree state từ session."""
        if selected_files:
            valid = {f for f in selected_files if Path(f).exists()}
            self.file_tree_widget.set_selected_paths(valid)
        if expanded_folders:
            valid = {f for f in expanded_folders if Path(f).exists()}
            self.file_tree_widget.set_expanded_paths(valid)
        self._update_token_display()

    def set_instructions_text(self, text: str) -> None:
        """Set instructions text (session restore)."""
        self._instructions_field.setPlainText(text)

    def get_instructions_text(self) -> str:
        return self._instructions_field.toPlainText()

    def get_selected_paths(self) -> List[str]:
        return self.file_tree_widget.get_selected_paths()

    def get_expanded_paths(self) -> List[str]:
        return self.file_tree_widget.get_expanded_paths()

    def cleanup(self) -> None:
        """Cleanup resources."""
        # Invalidate all pending workers — their callbacks will be ignored
        self._copy_generation += 1

        # Force cleanup all stale refs
        for obj in self._stale_workers:
            if isinstance(obj, QObject):
                try:
                    obj.deleteLater()
                except RuntimeError:
                    pass
        self._stale_workers.clear()
        self._current_copy_worker = None
        self._current_copy_signals = None
        self._current_security_worker = None
        self._current_security_signals = None

        # Dismiss all toasts
        try:
            from components.toast_qt import ToastManager

            manager = ToastManager.instance()
            if manager is not None:
                manager.dismiss_all(force=True)
        except Exception:
            pass

        if self._file_watcher:
            self._file_watcher.stop()
            self._file_watcher = None

        self.file_tree_widget.cleanup()

    # ===== Slots =====

    @Slot(set)
    def _on_selection_changed(self, selected_paths: set) -> None:
        """Handle selection change — update display + trigger related resolution if active."""
        self._token_generation += 1
        self._prompt_cache.invalidate_all()
        self._update_token_display()

        # Auto-resolve related files when mode is active
        if self._related_mode_active and not self._resolving_related:
            self._resolve_related_files()

    @Slot()
    def _on_instructions_changed(self) -> None:
        """Handle instructions text change - cap nhat word count va token display."""
        text = self._instructions_field.toPlainText()
        word_count = len(text.split()) if text.strip() else 0
        self._word_count_label.setText(f"{word_count} words")
        QTimer.singleShot(150, self._update_token_display)

    @Slot(int)
    def _on_format_changed(self, index: int) -> None:
        """Handle format dropdown change."""
        format_id = self._format_combo.currentData()
        if format_id:
            try:
                self._selected_output_style = get_style_by_id(format_id)
                update_app_setting(output_format=format_id)
                self._prompt_cache.invalidate_all()
            except ValueError:
                pass

    @Slot(object)
    def _on_template_selected(self, action) -> None:
        """Xu ly khi chon mot prompt template hoac action xoa template."""
        from core.prompting.template_manager import load_template, delete_template
        from PySide6.QtWidgets import QMessageBox

        data = action.data()
        if not data:
            return

        if isinstance(data, dict):
            action_type = data.get("action")
            template_id = str(data.get("id", ""))

            if action_type == "delete" and template_id:
                reply = QMessageBox.question(
                    self,
                    "Xóa Custom Template",
                    "Bạn có chắc chắn muốn xóa template này không?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    if delete_template(template_id):
                        self._show_status("Template deleted.")
                    else:
                        self._show_status("Failed to delete template.", is_error=True)
                return
            # neu la insert thi fallthrough xuong ben duoi
        else:
            template_id = str(data)

        if not template_id:
            return

        if template_id == "__CREATE_CUSTOM__":
            self._show_custom_template_dialog()
            return

        try:
            content = load_template(template_id)
            cursor = self._instructions_field.textCursor()
            cursor.select(cursor.SelectionType.Document)
            cursor.insertText(content)
            self._show_status("Template inserted")
        except Exception as e:
            self._show_status(f"Failed to load template: {e}", is_error=True)

    def _show_custom_template_dialog(self) -> None:
        """Hien thi dialog cho phep tao Custom Template."""
        from components.custom_template_dialog import CustomTemplateDialog

        dialog = CustomTemplateDialog(self)
        if dialog.exec():
            self._show_status("Custom template saved! You can now use it.")

    @Slot()
    def _populate_template_menu(self) -> None:
        """Đổ dữ liệu template vào menu (dynamic build)."""
        from core.prompting.template_manager import list_templates

        menu = self._template_menu
        menu.clear()

        for tmpl in list_templates():
            if getattr(tmpl, "is_custom", False):
                sub = menu.addMenu(tmpl.display_name)
                if tmpl.description:
                    sub.setToolTip(tmpl.description)

                ins = sub.addAction("Insert")
                ins.setData({"action": "insert", "id": tmpl.template_id})

                sub.addSeparator()

                dlt = sub.addAction("❌ Delete")
                dlt.setData({"action": "delete", "id": tmpl.template_id})
            else:
                action = menu.addAction(tmpl.display_name)
                if tmpl.description:
                    action.setToolTip(tmpl.description)
                action.setData(tmpl.template_id)

        menu.addSeparator()
        add_action = menu.addAction("➕ Manage/Add Custom Template...")
        add_action.setData("__CREATE_CUSTOM__")

    @Slot()
    def _populate_history_menu(self) -> None:
        """Đổ dữ liệu recent instructions vào history menu khi được click."""
        from services.settings_manager import load_app_settings

        menu = self._history_menu
        menu.clear()

        settings = load_app_settings()
        history = settings.instruction_history

        if not history:
            action = menu.addAction("No history yet")
            action.setEnabled(False)
            return

        for text in history:
            label = text[:50] + "..." if len(text) > 50 else text
            label = label.replace("\n", " ").strip()

            sub = menu.addMenu(label)
            sub.setToolTip(text[:200] + ("..." if len(text) > 200 else ""))

            ins = sub.addAction("Apply")
            ins.setData({"action": "insert", "text": text})

            sub.addSeparator()

            dlt = sub.addAction("❌ Delete")
            dlt.setData({"action": "delete", "text": text})

    @Slot(object)
    def _on_history_selected(self, action) -> None:
        """Handle history selection from dropdown."""
        data = action.data()
        if not data:
            return

        if isinstance(data, dict):
            action_type = data.get("action")
            text = str(data.get("text", ""))

            if action_type == "delete" and text:
                from services.settings_manager import (
                    load_app_settings,
                    update_app_setting,
                )

                settings = load_app_settings()
                history_list = settings.instruction_history.copy()
                if text in history_list:
                    history_list.remove(text)
                    update_app_setting(instruction_history=history_list)
                    self._show_status("History item deleted.")
                return
            # neu la insert thi fallthrough
        else:
            text = str(data)

        if text:
            self._instructions_field.setPlainText(text)
            self._show_status("History loaded")

    @Slot()
    def _clear_prompt_history(self) -> None:
        """Xoa toan bo lich su cua prompt input."""
        from PySide6.QtWidgets import QMessageBox
        from services.settings_manager import update_app_setting

        reply = QMessageBox.question(
            self,
            "Clear History",
            "Bạn có chắc chắn muốn xóa toàn bộ lịch sử Prompt không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            update_app_setting(instruction_history=[])
            self._show_status("All prompt history cleared.")

    # ===== Token Counting =====

    def _update_token_display(self) -> None:
        """Update token count display tu cached values. Khong trigger counting.

        Hien thi file tokens + instruction tokens tren toolbar.
        Tooltip canh bao rang actual copy se co them overhead
        (tree map, git, OPX, XML structure).
        """
        model = self.file_tree_widget.get_model()
        file_count = model.get_selected_file_count()

        # Count instruction tokens
        instructions = self._instructions_field.toPlainText()
        instruction_tokens = (
            self._prompt_builder.count_tokens(instructions) if instructions else 0
        )

        # Get cached tokens
        total_file_tokens = self.file_tree_widget.get_total_tokens()
        total = total_file_tokens + instruction_tokens

        self._token_count_label.setText(f"{total:,} tokens")

        # Tooltip canh bao overhead khi copy
        self._token_count_label.setToolTip(
            f"{total_file_tokens:,} file tokens + {instruction_tokens:,} instruction tokens\n\n"
            "Note: Actual prompt size will be larger due to:\n"
            "- Tree map (project structure)\n"
            "- Git changes (diff + log)\n"
            "- OPX instructions (if using Copy + OPX)\n"
            "- XML/JSON tags wrapping\n\n"
            "Hover over the status message after copying to see detailed breakdown."
        )

        # Update stats panel
        self._token_stats.update_stats(
            file_count=file_count,
            file_tokens=total_file_tokens,
            instruction_tokens=instruction_tokens,
        )
        self._selection_meta_label.setText(f"{file_count:,} selected")

    @Slot(str)
    def _on_model_changed(self, model_id: str) -> None:
        """
        Handler when user changes model.

        Resets encoder and clears cache to trigger recount with the new tokenizer.
        """
        # Reset encoder va reinitialize voi model moi qua TokenizationService
        from services.encoder_registry import initialize_encoder

        initialize_encoder()  # Re-inject new config vao TokenizationService

        # Invalidate prompt cache (token counts will differ with new tokenizer)
        self._prompt_cache.invalidate_all()

        # Clear token cache (since tokenizer has changed)
        model = self.file_tree_widget.get_model()
        model._token_cache.clear()

        # Trigger recount for all selected files
        self.file_tree_widget._start_token_counting()

        self._show_status(f"Recounting tokens with {model_id}...")

    # ===== Helpers =====

    def _show_status(self, message: str, is_error: bool = False) -> None:
        """Hien thi thong bao qua Global Toast System."""
        if not message:
            return

        if is_error:
            from components.toast_qt import toast_error

            toast_error(message)
        else:
            from components.toast_qt import toast_success

            toast_success(message)
