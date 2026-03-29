"""
Context View (PySide6) - Tab để chọn files và copy context.

Refactored to use Composition pattern (controllers thay vi Mixins) de tach biet
logic khoi UI va tuan thu Single Responsibility Principle.
"""

import threading
import logging
from pathlib import Path
from typing import Optional, Set, List, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.filesystem.ignore_engine import IgnoreEngine
    from application.interfaces.tokenization_port import ITokenizationService
    from domain.relationships.port import IRelationshipGraphProvider

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Slot, QTimer


from infrastructure.filesystem.file_utils import TreeItem
from infrastructure.filesystem.file_watcher_facade import FileWatcher, WatcherCallbacks
from infrastructure.persistence.settings_manager import update_app_setting
from presentation.config.output_format import (
    OutputStyle,
    get_style_by_id,
    DEFAULT_OUTPUT_STYLE,
)

# Import mixins
from presentation.views.context.ui_builder import UIBuilderMixin
from presentation.views.context.copy_action_controller import CopyActionController

# Import controllers (composition-based replacements)
from presentation.views.context.related_files_controller import RelatedFilesController
from presentation.views.context.tree_management_controller import (
    TreeManagementController,
)


logger = logging.getLogger(__name__)


class ContextViewQt(
    QWidget,
    UIBuilderMixin,
):
    """View cho Context tab - PySide6 version."""

    def __init__(
        self,
        get_workspace: Callable[[], Optional[Path]],
        parent: Optional[QWidget] = None,
        prompt_builder=None,
        clipboard_service=None,
        ignore_engine: Optional["IgnoreEngine"] = None,
        tokenization_service: Optional["ITokenizationService"] = None,
        graph_provider: Optional["IRelationshipGraphProvider"] = None,
    ):
        super().__init__(parent)
        self.get_workspace = get_workspace
        self.get_workspace_path = get_workspace  # Alias for protocol compatibility

        # IgnoreEngine duoc inject tu ServiceContainer
        if ignore_engine is None:
            from infrastructure.filesystem.ignore_engine import IgnoreEngine as _IE

            ignore_engine = _IE()
        self._ignore_engine: "IgnoreEngine" = ignore_engine

        if tokenization_service is None:
            from infrastructure.adapters.encoder_registry import (
                get_tokenization_service,
            )

            tokenization_service = get_tokenization_service()
        self._tokenization_service: "ITokenizationService" = tokenization_service
        self._graph_provider: Optional["IRelationshipGraphProvider"] = graph_provider

        # State
        self.tree: Optional[TreeItem] = None
        self._selected_output_style: OutputStyle = DEFAULT_OUTPUT_STYLE
        self._loading_lock = threading.Lock()
        self._is_loading = False
        self._pending_refresh = False
        self._token_generation = 0
        # AI Suggest Select state: worker reference + snapshot cho Undo
        self._ai_suggest_worker = None
        self._ai_suggest_previous_selection: Optional[List[str]] = None
        self._ai_suggest_generation: int = 0

        # Services (with dependency injection support)
        self._file_watcher: Optional[FileWatcher] = FileWatcher()

        if prompt_builder is None:
            from application.services.prompt_build_service import PromptBuildService

            # Bug #1 Fix: Đảm bảo fallback instance cũng được inject graph_service (nếu có)
            # để project structure metadata có thể được tính toán.
            from typing import Any, cast

            prompt_builder = PromptBuildService(
                tokenization_service=self._tokenization_service,
                graph_service=cast(Any, self._graph_provider),
            )
        self._prompt_builder = prompt_builder

        if clipboard_service is None:
            from application.services.prompt_build_service import QtClipboardService

            clipboard_service = QtClipboardService()
        self._clipboard_service = clipboard_service

        # RelatedFilesController: quan ly logic auto-select related files
        # TreeManagementController: quan ly refresh tree, ignore patterns, file watchers
        # NOTE: parent=None de tranh QObject init phuc tap khi QWidget.__init__ bi mock trong tests
        self._related_controller: RelatedFilesController = RelatedFilesController(
            self,
            graph_provider=self._graph_provider,
        )
        self._tree_controller: TreeManagementController = TreeManagementController(
            self, parent=None
        )
        self._copy_controller: CopyActionController = CopyActionController(
            self, parent=None
        )

        # PresetController: quan ly context presets
        from presentation.views.context.preset_controller import PresetController

        self._preset_controller: PresetController = PresetController(self, parent=None)

        # Build UI (from UIBuilderMixin)
        self._build_ui()

        # Setup keyboard shortcuts
        self._setup_shortcuts()

    # ===== Public API =====

    def _setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts."""
        from PySide6.QtGui import QShortcut, QKeySequence

        # Ctrl+Shift+S: Quick save preset
        save_shortcut = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        save_shortcut.activated.connect(self._quick_save_preset)

        # Ctrl+Shift+L: Focus preset combo
        focus_shortcut = QShortcut(QKeySequence("Ctrl+Shift+L"), self)
        focus_shortcut.activated.connect(self._focus_preset_combo)

    def _quick_save_preset(self) -> None:
        """Quick save with proper confirmation dialogs."""
        if not hasattr(self, "_preset_controller") or self._preset_controller is None:
            return

        if not self.get_selected_paths():
            from presentation.components.toast.toast_qt import ToastManager, ToastType

            manager = ToastManager.instance()
            if manager:
                manager.show(
                    ToastType.ERROR,
                    "No files selected. Select files before saving preset.",
                )
            return

        try:
            # Always delegate to widget to ensure consistent UI behavior
            if hasattr(self, "_preset_widget") and self._preset_widget:
                self._preset_widget.trigger_save_action()
            else:
                # Fallback: create new preset if widget unavailable
                from PySide6.QtWidgets import QInputDialog

                name, ok = QInputDialog.getText(self, "New Preset", "Preset name:")
                if ok and name.strip():
                    self._preset_controller.create_preset(name.strip())
        except (RuntimeError, AttributeError) as e:
            logger.error(f"Failed to save preset: {e}")

    def _focus_preset_combo(self) -> None:
        """Focus preset combo box."""
        if not hasattr(self, "_preset_widget") or self._preset_widget is None:
            return
        try:
            if self._preset_widget.isVisible():
                self._preset_widget.focus_selector()
        except (RuntimeError, AttributeError):
            pass

    def on_workspace_changed(self, workspace_path: Path) -> None:
        """Handle workspace change."""
        if (
            not self._copy_controller
            or not self._related_controller
            or not self._tree_controller
        ):
            return

        from shared.logging_config import log_info

        log_info(f"[ContextView] Workspace changing to: {workspace_path}")

        # 0. Invalidate any pending copy operations by incrementing generation.
        self._copy_controller._begin_copy_operation()
        self.set_copy_buttons_enabled(True)

        # Invalidate any in-flight AI suggest request
        self._ai_suggest_generation += 1
        self._cancel_ai_suggest_worker()
        if hasattr(self, "_ai_suggest_btn"):
            self._ai_suggest_btn.setEnabled(True)
            self._ai_suggest_btn.setText("AI Suggest Select")

        # 1. Stop file watcher for old workspace
        if self._file_watcher:
            self._file_watcher.stop()

        # 2. Deactivate related mode to clean up state
        self._related_controller.set_mode(False, 0, silent=True)

        # 3. Clear all caches for old workspace via CacheRegistry
        from infrastructure.adapters.cache_registry import cache_registry

        cache_registry.invalidate_for_workspace()
        self._copy_controller._prompt_cache.invalidate_all()

        # 4. Reset preset controller BEFORE loading tree to avoid race condition
        if self._preset_controller:
            self._preset_controller.on_workspace_changed(workspace_path)

        # 5. Load new tree (this increments generation counter, cancels old workers)
        self.file_tree_widget.load_tree(workspace_path)
        self.tree = self.file_tree_widget.get_model()._root_node  # type: ignore

        # 6. Reset token display
        if hasattr(self, "_token_usage_bar"):
            self._token_usage_bar.update_stats(tokens=0, limit=200000, files=0)

        if hasattr(self, "_context_info_label"):
            self._context_info_label.setText("0 files · 0 tokens")
        if hasattr(self, "_limit_warning"):
            self._limit_warning.hide()

        # 7. Start file watcher for new workspace
        if self._file_watcher and workspace_path.exists():
            self._file_watcher.start(
                path=workspace_path,
                callbacks=WatcherCallbacks(
                    on_file_modified=self._tree_controller.on_file_modified,
                    on_file_created=self._tree_controller.on_file_created,
                    on_file_deleted=self._tree_controller.on_file_deleted,
                    on_batch_change=self._tree_controller.on_file_system_changed,
                ),
                debounce_seconds=0.5,
            )

        # 8. Trigger RelationshipGraph build cho workspace moi (background)
        if hasattr(self, "_graph_provider") and self._graph_provider is not None:
            self._graph_provider.on_workspace_changed(workspace_path)

        # 9. Sync Templates Button Text (Tier)
        from infrastructure.persistence.settings_manager import load_app_settings

        new_tier = getattr(load_app_settings(), "template_tier", "lite")
        if hasattr(self, "_template_btn"):
            tier_label = "Lite" if new_tier == "lite" else "Pro"
            self._template_btn.setText(f"Templates ({tier_label})")

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

    def get_selected_paths(self) -> Set[str]:
        return set(self.file_tree_widget.get_selected_paths())

    def get_expanded_paths(self) -> List[str]:
        return self.file_tree_widget.get_expanded_paths()

    def set_selected_paths_from_preset(self, paths: Set[str]) -> None:
        """Adapter: Apply preset selection (replace toàn bộ)."""
        self.file_tree_widget.set_selected_paths(paths)

    def get_output_style(self) -> OutputStyle:
        """Adapter: Get current output style."""
        return self._selected_output_style

    def show_status(self, message: str, is_error: bool = False) -> None:
        """Adapter: Show status message via toast."""
        from presentation.components.toast.toast_qt import ToastManager, ToastType

        manager = ToastManager.instance()
        if manager and message:
            toast_type = ToastType.ERROR if is_error else ToastType.SUCCESS
            manager.show(toast_type, message)

    # ===== Protocol Adapter Methods (cho Controllers) =====
    # Cac methods nay implement Protocol interfaces can thiet boi controllers
    # Ma khong expose chi tiet noi tai cua ContextViewQt.

    def get_all_selected_paths(self) -> Set[str]:
        """
        Tra ve tat ca selected paths (ca files va folders).

        Adapter method cho RelatedFilesViewProtocol va TreeManagementViewProtocol.
        """
        return self.file_tree_widget.get_all_selected_paths()

    def add_paths_to_selection(self, paths: Set[str]) -> int:
        """Adapter: them paths vao file tree selection."""
        return self.file_tree_widget.add_paths_to_selection(paths)

    def remove_paths_from_selection(self, paths: Set[str]) -> int:
        """Adapter: xoa paths khoi file tree selection."""
        return self.file_tree_widget.remove_paths_from_selection(paths)

    def load_tree(self, workspace: Path) -> None:
        """Adapter: reload file tree widget."""
        self.file_tree_widget.load_tree(workspace)

    def scan_full_tree(self, workspace: Path):
        """
        Adapter: Scan full workspace tree de build file index day du.

        Su dung cho RelatedFilesController khi resolve dependencies.
        """
        if not self._copy_controller:
            return None
        return self._copy_controller._scan_full_tree(workspace)

    def get_total_tokens(self) -> int:
        return self.file_tree_widget.get_total_tokens()

    def get_clipboard_service(self):
        return self._clipboard_service

    def get_prompt_builder(self):
        return self._prompt_builder

    def get_tokenization_service(self):
        return self._tokenization_service

    def get_ignore_engine(self):
        return self._ignore_engine

    def get_copy_as_file(self) -> bool:
        """Adapter: Read copy-as-file toggle state from actions panel."""
        toggle = getattr(self, "_copy_as_file_toggle", None)
        return toggle.isChecked() if toggle is not None else False

    def get_full_tree(self) -> bool:
        """Adapter: Read full-tree toggle state from actions panel."""
        toggle = getattr(self, "_full_tree_toggle", None)
        return toggle.isChecked() if toggle is not None else False

    def is_smart_mode_active(self) -> bool:
        """Kiểm tra xem Smart Mode có đang active không.
        (Hiện tại check dựa trên _selected_output_style == OutputStyle.SMART)
        """
        return self._selected_output_style == OutputStyle.SMART

    def parent_widget(self):
        return self

    def set_copy_buttons_enabled(self, enabled: bool) -> None:
        # Hien/an loading bar va cap nhat text button chinh
        if hasattr(self, "_copy_loading_bar"):
            self._copy_loading_bar.setVisible(not enabled)
        if hasattr(self, "_opx_btn"):
            self._opx_btn.setText("Copy + OPX" if enabled else "Processing...")
        for btn in (
            self._diff_btn,
            self._tree_map_btn,
            self._smart_btn,
            self._copy_btn,
            self._opx_btn,
        ):
            if btn is not None:
                btn.setEnabled(enabled)

    def show_copy_breakdown(self, token_count: int, breakdown: dict) -> None:
        """
        Hiển thị chi tiết token consumption sau khi copy thành công.
        breakdown chứa các keys: content_tokens, instruction_tokens, opx_tokens,
        tree_tokens, diff_tokens, rule_tokens, structure_tokens (overhead).
        """
        from presentation.components.toast.toast_qt import toast_success

        file_t = breakdown.get("content_tokens", 0)
        instr_t = breakdown.get("instruction_tokens", 0)
        opx_t = breakdown.get("opx_tokens", 0)
        tree_t = breakdown.get("tree_tokens", 0)
        diff_t = breakdown.get("diff_tokens", 0)
        rule_t = breakdown.get("rule_tokens", 0)
        structure_t = breakdown.get("structure_tokens", 0)
        mode = breakdown.get("copy_mode", "Copy")

        # Fallback logic cho cac mode cu hoac neu sum_parts tiep tuc lon hon token_count
        # (thuong do overhead XML tags neu PromptBuildService chua tinh het)
        sum_parts = file_t + instr_t + opx_t + tree_t + diff_t + rule_t
        if sum_parts > token_count:
            # Re-scale de khong bi am structure_tokens
            ratio = token_count / sum_parts if sum_parts > 0 else 1.0
            file_t = int(file_t * ratio)
            instr_t = int(instr_t * ratio)
            opx_t = int(opx_t * ratio)
            tree_t = int(tree_t * ratio)
            diff_t = int(diff_t * ratio)
            rule_t = int(rule_t * ratio)
            structure_t = 0
        elif structure_t == 0 and token_count > sum_parts:
            # Neu structure_t chua duoc tinh nhung con du, gan cho no
            structure_t = token_count - sum_parts

        parts = []
        if file_t > 0:
            parts.append(f"{file_t:,} content")
        if instr_t > 0:
            parts.append(f"{instr_t:,} instructions")
        if tree_t > 0:
            parts.append(f"{tree_t:,} tree map")
        if diff_t > 0:
            parts.append(f"{diff_t:,} diffs")
        if rule_t > 0:
            parts.append(f"{rule_t:,} rules")
        if opx_t > 0:
            parts.append(f"{opx_t:,} OPX")
        if structure_t > 0:
            parts.append(f"{structure_t:,} system prompt")

        breakdown_text = " + ".join(parts) if parts else ""

        tooltip_lines = [
            f"Total: {token_count:,} tokens",
            "",
            f"File content: {file_t:,} tokens",
            f"Instructions: {instr_t:,} tokens",
        ]
        if opx_t > 0:
            tooltip_lines.append(f"OPX instructions: {opx_t:,} tokens")
        if tree_t > 0:
            tooltip_lines.append(f"Tree map: {tree_t:,} tokens")
        if diff_t > 0:
            tooltip_lines.append(f"Git diffs/logs: {diff_t:,} tokens")
        if rule_t > 0:
            tooltip_lines.append(f"Project rules: {rule_t:,} tokens")

        tooltip_lines.extend(
            [
                f"Prompt structure: {structure_t:,} tokens",
                "  (includes: XML tags, assembly overhead)",
            ]
        )

        if len(parts) > 0:
            # Format breakdown with line breaks for readability
            breakdown_lines = []
            if file_t > 0:
                breakdown_lines.append(f"• {file_t:,} content")
            if instr_t > 0:
                breakdown_lines.append(f"• {instr_t:,} instructions")
            if tree_t > 0:
                breakdown_lines.append(f"• {tree_t:,} tree map")
            if diff_t > 0:
                breakdown_lines.append(f"• {diff_t:,} diffs")
            if rule_t > 0:
                breakdown_lines.append(f"• {rule_t:,} rules")
            if opx_t > 0:
                breakdown_lines.append(f"• {opx_t:,} OPX")
            if structure_t > 0:
                breakdown_lines.append(f"• {structure_t:,} system prompt")

            breakdown_text = "\n".join(breakdown_lines)

            toast_success(
                message=f"{token_count:,} tokens\n{breakdown_text}",
                title=f"{mode} successful!",
                tooltip="\n".join(tooltip_lines),
                duration=8000,
            )
        else:
            toast_success(
                message=f"{token_count:,} tokens",
                title=f"{mode} successful!",
                tooltip="\n".join(tooltip_lines),
                duration=8000,
            )

    def _collect_all_tree_paths(self, root: TreeItem) -> Set[str]:
        paths = set()

        def _walk(node):
            paths.add(node.path)
            for child in node.children:
                _walk(child)

        _walk(root)
        return paths

    def update_related_button_text(self, active: bool, depth: int, count: int) -> None:
        """
        Adapter: Cap nhat text cua related mode button.

        Duoc goi boi RelatedFilesController khi trang thai thay doi.
        """
        if not hasattr(self, "_related_menu_btn"):
            return

        if not active:
            self._related_menu_btn.setText("Related: Off")
            return

        depth_names = {1: "Direct", 2: "Nearby", 3: "Deep", 4: "Deeper", 5: "Deepest"}
        depth_name = depth_names.get(depth, f"Depth {depth}")

        if count > 0:
            self._related_menu_btn.setText(f"Related: {depth_name} ({count})")
        else:
            self._related_menu_btn.setText(f"Related: {depth_name}")

    @Slot(str)
    def _preview_file(self, file_path: str) -> None:
        """Preview file in dialog."""
        from presentation.components.dialogs.dialogs_qt import FilePreviewDialogQt

        FilePreviewDialogQt.show_preview(self, file_path)

    def invalidate_prompt_cache(self) -> None:
        """Adapter: Invalidate prompt-level cache (duoc goi boi TreeManagementController)."""
        if self._copy_controller:
            self._copy_controller._prompt_cache.invalidate_all()

    def cleanup(self) -> None:
        """Cleanup resources."""
        # Invalidate all pending workers — their callbacks will be ignored
        if self._copy_controller:
            self._copy_controller._begin_copy_operation()

        self._ai_suggest_generation += 1
        self._cancel_ai_suggest_worker()

        # Cleanup preset widget connections to prevent leaks
        if hasattr(self, "_preset_widget") and self._preset_widget:
            try:
                # Disconnect khoi signal cua file tree (dung _refresh_menu thay the)
                if hasattr(self, "file_tree_widget") and self.file_tree_widget:
                    try:
                        self.file_tree_widget.selection_changed.disconnect(
                            self._preset_widget._refresh_menu
                        )
                    except (RuntimeError, TypeError):
                        pass
            except (RuntimeError, TypeError, AttributeError):
                pass
            self._preset_widget.deleteLater()
            self._preset_widget = None  # type: ignore

        # Detach and destroy controllers manually since they use parent=None
        if self._related_controller:
            self._related_controller.deleteLater()
            self._related_controller = None  # type: ignore
        if self._tree_controller:
            self._tree_controller.deleteLater()
            self._tree_controller = None  # type: ignore
        if self._copy_controller:
            self._copy_controller.deleteLater()
            self._copy_controller = None  # type: ignore
        if self._preset_controller:
            self._preset_controller.cleanup()
            self._preset_controller.deleteLater()
            self._preset_controller = None  # type: ignore

        # Dismiss all toasts
        try:
            from presentation.components.toast.toast_qt import ToastManager

            manager = ToastManager.instance()
            if manager is not None:
                manager.dismiss_all(force=True)
        except Exception:
            pass

        if self._file_watcher:
            self._file_watcher.stop()
            self._file_watcher = None

        self.file_tree_widget.cleanup()

    def _cancel_ai_suggest_worker(self) -> None:
        """
        Huy va ngat ket noi signals cua AIContextWorker neu dang chay.

        Giu nguyen generation guard trong _on_ai_suggest_finished/_on_ai_suggest_error
        de bo qua ket qua stale, nhung van dam bao khong co signal nao
        duoc deliver vao QWidget da bi huy.
        """
        worker = self._ai_suggest_worker
        if worker is None:
            return

        try:
            cancel = getattr(worker, "cancel", None)
            if callable(cancel):
                cancel()
        except Exception:
            # Khong de viec huy worker lam vo UI
            logger.debug("Failed to cancel AIContextWorker", exc_info=True)

        try:
            signals = getattr(worker, "signals", None)
            if signals is not None:
                try:
                    signals.finished.disconnect()
                except (RuntimeError, TypeError):
                    pass
                try:
                    signals.error.disconnect()
                except (RuntimeError, TypeError):
                    pass
                try:
                    signals.progress.disconnect()
                except (RuntimeError, TypeError):
                    pass
        except RuntimeError:
            # signals co the da bi xoa boi Qt
            pass

        self._ai_suggest_worker = None

    # ===== Slots =====

    @Slot(set)
    def _on_selection_changed(self, selected_paths: set) -> None:
        """Handle selection change — update display + trigger related resolution if active."""
        if not self._copy_controller or not self._related_controller:
            return

        self._token_generation += 1
        self._copy_controller._prompt_cache.invalidate_all()
        self._update_token_display()

        # Update empty state hint visibility
        has_files = bool(selected_paths)
        if hasattr(self, "_no_files_hint"):
            self._no_files_hint.setVisible(not has_files)

        # Auto-resolve related files when mode is active
        self._related_controller.resolve_for_current_selection()

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
                if self._copy_controller:
                    self._copy_controller._prompt_cache.invalidate_all()
            except ValueError:
                pass

    @Slot(str)
    def _on_tier_changed(self, tier: str) -> None:
        """Xu ly khi nguoi dung thay doi template tier ngay tren toolbar."""
        from infrastructure.persistence.settings_manager import update_app_setting

        try:
            # Luu setting moi vao persistent storage
            update_app_setting(template_tier=tier)

            # Invalidate cache de dam bao template moi duoc fetch khi copy
            if self._copy_controller:
                self._copy_controller._prompt_cache.invalidate_all()

            # Cap nhat text trên button Templates de nguoi dung luon biet tier hien tai
            if hasattr(self, "_template_btn"):
                tier_label = "Lite" if tier == "lite" else "Pro"
                self._template_btn.setText(f"Templates ({tier_label})")

            # Thong bao cho nguoi dung via toast
            tier_display = "Lite (Concise)" if tier == "lite" else "Pro (Detailed)"
            self.show_status(f"Template Tier switched to {tier_display}")

        except Exception as e:
            logger.error(f"Failed to change template tier: {e}")
            self.show_status("Failed to change tier.", is_error=True)

    @Slot(object)
    def _on_template_selected(self, action) -> None:
        """Xu ly khi chon mot prompt template hoac action xoa template."""
        from domain.prompt.template_manager import load_template, delete_template
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
            self._instructions_field.setPlainText(content)
            self._show_status("Template loaded")
        except Exception as e:
            self._show_status(f"Failed to load template: {e}", is_error=True)

    def _show_custom_template_dialog(self) -> None:
        """Hien thi dialog cho phep tao Custom Template."""
        from presentation.components.dialogs.custom_template_dialog import (
            CustomTemplateDialog,
        )

        dialog = CustomTemplateDialog(self)
        if dialog.exec():
            self._show_status("Custom template saved! You can now use it.")

    @Slot()
    def _populate_template_menu(self) -> None:
        """Đổ dữ liệu template vào menu (dynamic build)."""
        from domain.prompt.template_manager import list_templates

        menu = self._template_menu
        menu.clear()

        # 1. Chèn Tier Selector (Lite/Pro) lên đầu menu dùng QWidgetAction (động)
        from PySide6.QtWidgets import QWidgetAction
        from infrastructure.persistence.settings_manager import load_app_settings
        from presentation.components.tier_selector import TierSelector

        # Luôn tạo mới menu item để tránh lỗi ownership của Qt
        new_tier = getattr(load_app_settings(), "template_tier", "lite")
        tier_selector = TierSelector(initial_tier=new_tier)
        tier_selector.tier_changed.connect(self._on_tier_changed)
        # Style gọn hơn khi nằm trong menu
        tier_selector.setContentsMargins(8, 4, 8, 4)

        action = QWidgetAction(menu)
        action.setDefaultWidget(tier_selector)
        menu.addAction(action)
        menu.addSeparator()

        # 2. Đổ dữ liệu các templates
        for tmpl in list_templates():
            if getattr(tmpl, "is_custom", False):
                sub = menu.addMenu(tmpl.display_name)
                if tmpl.description:
                    sub.setToolTip(tmpl.description)
                    sub.menuAction().setToolTip(tmpl.description)

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
        from infrastructure.persistence.settings_manager import load_app_settings

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

        # Clear All — relocated from standalone button for safety
        if history:
            menu.addSeparator()
            clear_all_action = menu.addAction("🗑 Clear All History")
            clear_all_action.setData({"action": "clear_all"})

    @Slot(object)
    def _on_history_selected(self, action) -> None:
        """Handle history selection from dropdown."""
        data = action.data()
        if not data:
            return

        if isinstance(data, dict):
            action_type = data.get("action")
            text = str(data.get("text", ""))

            if action_type == "clear_all":
                self._clear_prompt_history()
                return

            if action_type == "delete" and text:
                from infrastructure.persistence.settings_manager import (
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
        from infrastructure.persistence.settings_manager import update_app_setting

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

        # Update Usage Bar (Toolbar) & Actions Panel Labels
        if hasattr(self, "_token_usage_bar"):
            # Lay limit tu model_id da duoc luu tru khi chon tren toolbar
            from presentation.config.model_config import (
                get_model_by_id,
                DEFAULT_MODEL_ID,
            )

            model_id = getattr(self, "_selected_model_id", DEFAULT_MODEL_ID)
            model_cfg = get_model_by_id(model_id)
            limit = model_cfg.context_length if model_cfg else 128000

            # Update Toolbar progress bar
            self._token_usage_bar.update_stats(
                tokens=total, limit=limit, files=file_count
            )
            self._token_usage_bar.setToolTip(
                f"Breakdown:\n"
                f"- {total_file_tokens:,} from files\n"
                f"- {instruction_tokens:,} from instructions\n\n"
                f"Model: {model_cfg.name if model_cfg else 'Unknown'}\n"
                "Max limit based on selected model."
            )

            # Update compact labels in actions panel
            if hasattr(self, "_context_info_label"):
                self._context_info_label.setText(
                    f"{file_count} files · {total:,} tokens"
                )

            # Update Warning (Fixed height)
            if hasattr(self, "_limit_warning"):
                if total > limit:
                    over = total - limit
                    self._limit_warning.setText(f"⚠ Over limit by {over:,} tokens!")
                    self._limit_warning.show()
                else:
                    self._limit_warning.hide()

    @Slot(str)
    def _on_model_changed(self, model_id: str) -> None:
        """
        Handler when user changes model.

        Resets encoder and clears cache to trigger recount with the new tokenizer.
        """
        # Reset encoder va reinitialize voi model moi qua TokenizationService
        from infrastructure.adapters.encoder_registry import get_tokenizer_repo

        repo = get_tokenizer_repo()
        self._tokenization_service.set_model_config(tokenizer_repo=repo)

        # Invalidate prompt cache (token counts will differ with new tokenizer)
        if self._copy_controller:
            self._copy_controller._prompt_cache.invalidate_all()

        # Clear token cache (since tokenizer has changed)
        model = self.file_tree_widget.get_model()
        model._token_cache.clear()

        # Trigger recount for all selected files
        self.file_tree_widget._start_token_counting()

        self._show_status(f"Recounting tokens with {model_id}...")

    # ===== AI Context Builder =====

    def _on_ai_selection_applied(self, paths: list) -> None:
        """
        Callback khi nguoi dung nhan Apply tren AI Context Builder Dialog.

        Replace toan bo selection hien tai bang danh sach files do AI goi y.

        Args:
            paths: Danh sach absolute hoac relative file paths tu LLM
        """
        workspace = self.get_workspace()

        # Convert relative paths sang absolute paths neu can
        resolved_paths: set[str] = set()
        unresolved: list[str] = []

        for p in paths:
            if workspace and not Path(p).is_absolute():
                full_path = workspace / p
                if full_path.exists():
                    resolved_paths.add(str(full_path))
                else:
                    unresolved.append(p)
            else:
                resolved_paths.add(p)

        # Undo case: user ro rang muon clear selection
        if not paths:
            self.file_tree_widget.set_selected_paths(set())
            return

        # Neu khong resolve duoc bat ky path nao -> thong bao loi ro rang
        if not resolved_paths:
            from presentation.components.toast.toast_qt import toast_error

            toast_error(
                "AI suggested paths could not be resolved. "
                "Please check that the files exist in the current workspace."
            )
            if unresolved:
                logger.warning(
                    "AI suggested %d unresolved paths (sample): %s",
                    len(unresolved),
                    unresolved[:5],
                )
            return

        if unresolved:
            logger.warning(
                "AI suggested %d paths that do not exist on disk (sample): %s",
                len(unresolved),
                unresolved[:5],
            )

        self.file_tree_widget.set_selected_paths(resolved_paths)

    # ===== AI Suggest Select (doc tu Instructions field) =====

    def _run_ai_suggest_from_instructions(self) -> None:
        """
        Doc noi dung tu Instructions field va chay AI worker de tu dong chon files.

        Luong xu ly:
        1. Doc text tu _instructions_field
        2. Validate settings (API key, model, tree)
        3. Luu snapshot selection hien tai cho Undo
        4. Tao AIContextWorker chay tren background thread
        5. Khi worker xong -> auto-apply ket qua vao file tree
        """
        user_query = self._instructions_field.toPlainText().strip()
        if not user_query:
            from presentation.components.toast.toast_qt import toast_error

            toast_error("Please write your instruction first.")
            return

        from infrastructure.persistence.settings_manager import load_app_settings
        from application.services.ai_context_worker import AIContextWorker
        from domain.prompt.generator import generate_file_map
        from infrastructure.git.git_utils import get_git_diffs
        from domain.prompt.context_builder_prompts import build_full_tree_string
        from presentation.components.toast.toast_qt import toast_error

        settings = load_app_settings()
        if not settings.ai_api_key:
            toast_error("Please configure AI API Key in Settings first.")
            return
        if not settings.ai_model_id:
            toast_error("Please select an AI model in Settings first.")
            return
        if self.tree is None:
            toast_error("No project loaded. Open a folder first.")
            return

        workspace = self.get_workspace()
        all_paths = self._collect_all_tree_paths(self.tree)

        file_tree_map = generate_file_map(
            self.tree,
            all_paths,
            workspace_root=workspace,
            use_relative_paths=True,
        )

        # Optional: Git diff
        git_diff_str = None
        if workspace:
            try:
                diff_result = get_git_diffs(workspace)
                if diff_result is not None:
                    _, git_diff_str = build_full_tree_string(
                        file_tree_map, diff_result, include_git=True
                    )
            except Exception:
                pass

        # Luu snapshot selection hien tai de phuc vu Undo
        self._ai_suggest_previous_selection = list(
            self.file_tree_widget.get_selected_paths()
        )

        # Disable button khi dang chay
        self._ai_suggest_btn.setEnabled(False)
        self._ai_suggest_btn.setText("Analyzing...")

        # Tao worker chay tren background thread
        worker = AIContextWorker(
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            model_id=settings.ai_model_id,
            file_tree=file_tree_map,
            user_query=user_query,
            git_diff=git_diff_str,
            all_file_paths=list(all_paths),
            workspace_root=workspace,
        )

        self._ai_suggest_generation += 1
        current_gen = self._ai_suggest_generation

        worker.signals.finished.connect(
            lambda paths, reasoning, usage, g=current_gen: self._on_ai_suggest_finished(
                paths, reasoning, usage, g
            )
        )
        worker.signals.error.connect(
            lambda msg, g=current_gen: self._on_ai_suggest_error(msg, g)
        )
        worker.signals.progress.connect(self._on_ai_suggest_progress)

        # Giu reference tranh GC
        self._ai_suggest_worker = worker
        from PySide6.QtCore import QThreadPool

        QThreadPool.globalInstance().start(worker)

    def _on_ai_suggest_finished(
        self, paths: list, reasoning: str, usage: dict, generation: int
    ) -> None:
        """Xu ly khi AI suggest worker hoan thanh thanh cong."""
        if generation != self._ai_suggest_generation:
            return

        self._ai_suggest_worker = None
        self._ai_suggest_btn.setEnabled(True)
        self._ai_suggest_btn.setText("AI Suggest Select")

        if paths:
            self._on_ai_selection_applied(paths)

            from presentation.components.toast.toast_qt import toast_success

            toast_success(f"AI selected {len(paths)} files.")
        else:
            from presentation.components.toast.toast_qt import toast_error

            toast_error(f"AI could not find relevant files. {reasoning}")

    def _on_ai_suggest_error(self, error_msg: str, generation: int) -> None:
        """Xu ly khi AI suggest worker gap loi."""
        if generation != self._ai_suggest_generation:
            return

        self._ai_suggest_worker = None
        self._ai_suggest_btn.setEnabled(True)
        self._ai_suggest_btn.setText("AI Suggest Select")

        from presentation.components.toast.toast_qt import toast_error

        toast_error(error_msg)

    def _on_ai_suggest_progress(self, status: str) -> None:
        """Cap nhat text button khi worker dang chay."""
        self._ai_suggest_btn.setText(status)

    # ===== Helpers =====

    def _show_status(self, message: str, is_error: bool = False) -> None:
        """Hien thi thong bao qua Global Toast System."""
        if not message:
            return

        if is_error:
            from presentation.components.toast.toast_qt import toast_error

            toast_error(message)
        else:
            from presentation.components.toast.toast_qt import toast_success

            toast_success(message)
