"""
Context View (PySide6) - Tab để chọn files và copy context.

Refactored to use Composition pattern (controllers thay vi Mixins) de tach biet
logic khoi UI va tuan thu Single Responsibility Principle.
"""

import threading
import logging
from pathlib import Path
from typing import Any, Optional, Set, List, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from domain.ports.ignore_engine_port import IIgnoreEngine
    from application.interfaces.tokenization_port import ITokenizationService
    from domain.tokenization.comparison_service import (
        TokenComparison,
        TokenComparisonService,
    )
    from domain.prompt.copy_mode import CopyConfig

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Slot, QTimer


from domain.smart_context.tree_item import TreeItem
from domain.ports.file_watcher_port import WatcherCallbacks
from domain.ports.registry import DomainRegistry
from domain.config.output_format import (
    OutputStyle,
    get_style_by_id,
    get_format_config,
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


def update_app_setting(**kwargs: Any) -> bool:
    svc = DomainRegistry.settings_service()
    for k, v in kwargs.items():
        svc.update_setting(k, v)
    return True


logger = logging.getLogger(__name__)


# Compatibility Alias for UI Tests
class FileWatcher:
    pass


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
        ignore_engine: Optional["IIgnoreEngine"] = None,
        tokenization_service: Optional["ITokenizationService"] = None,
        token_comparison_service: Optional["TokenComparisonService"] = None,
    ):
        super().__init__(parent)
        self.get_workspace = get_workspace
        self.get_workspace_path = get_workspace  # Alias for protocol compatibility

        # IgnoreEngine duoc inject tu ServiceContainer
        if ignore_engine is None:
            ignore_engine = DomainRegistry.ignore_engine()
        self._ignore_engine: "IIgnoreEngine" = ignore_engine

        if tokenization_service is None:
            tokenization_service = DomainRegistry.tokenization_service()
        self._tokenization_service: "ITokenizationService" = tokenization_service

        if token_comparison_service is None:
            from domain.tokenization.comparison_service import TokenComparisonService

            token_comparison_service = TokenComparisonService()
        self._token_comparison_service: "TokenComparisonService" = (
            token_comparison_service
        )

        # State
        self.tree: Optional[TreeItem] = None
        self._selected_output_style: OutputStyle = DEFAULT_OUTPUT_STYLE
        self._loading_lock = threading.Lock()
        self._is_loading = False
        self._pending_refresh = False
        self._token_generation = 0
        self._smart_comparison_generation = 0
        self._smart_comparison_key: tuple[str, ...] | None = None
        self._latest_token_comparison: Optional["TokenComparison"] = None
        self._smart_comparison_worker: Any = None
        # Improve Instructions state: worker reference
        self._improve_instructions_worker = None
        self._improve_instructions_generation: int = 0
        # AI Pick Files state: worker reference
        self._ai_pick_files_worker = None
        self._ai_pick_files_generation: int = 0

        # Services (with dependency injection support)
        self._file_watcher = DomainRegistry.file_watcher_service()

        if prompt_builder is None:
            from application.services.prompt_build_service import PromptBuildService

            # Fallback instance
            prompt_builder = PromptBuildService(
                tokenization_service=self._tokenization_service,
            )
        self._prompt_builder = prompt_builder

        if clipboard_service is None:
            clipboard_service = DomainRegistry.clipboard_service()
        self._clipboard_service = clipboard_service

        # RelatedFilesController: quan ly logic auto-select related files
        # TreeManagementController: quan ly refresh tree, ignore patterns, file watchers
        # NOTE: parent=None de tranh QObject init phuc tap khi QWidget.__init__ bi mock trong tests
        self._related_controller: RelatedFilesController = RelatedFilesController(
            self,
            # graph_provider removed
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

        # F5: Refresh file tree (khop voi tooltip cua nut Reload)
        refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        refresh_shortcut.activated.connect(
            lambda: (
                self._tree_controller.refresh_tree() if self._tree_controller else None
            )
        )

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
            pass  # intentionally silent — widget may be deleted or not initialized

    def on_workspace_changed(self, workspace_path: Optional[Path]) -> None:
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

        # Invalidate any in-flight Improve Instructions request
        self._improve_instructions_generation += 1
        self._cancel_improve_instructions_worker()
        if hasattr(self, "_improve_instructions_btn"):
            self._improve_instructions_btn.setEnabled(True)
            self._improve_instructions_btn.setText("Improve Instructions")

        # Invalidate any in-flight AI Pick Files request
        self._ai_pick_files_generation += 1
        self._cancel_ai_pick_files_worker()
        if hasattr(self, "_ai_pick_files_btn"):
            self._ai_pick_files_btn.setEnabled(True)
            self._ai_pick_files_btn.setText("AI Pick Files")

        # 1. Stop file watcher for old workspace
        if self._file_watcher:
            self._file_watcher.stop()

        # 2. Deactivate related mode to clean up state
        self._related_controller.set_mode(False, 0, silent=True)

        # 3. Clear all caches for old workspace via CacheRegistry
        DomainRegistry.cache_registry().invalidate_for_workspace()
        self._copy_controller._prompt_cache.invalidate_all()

        # 4. Reset preset controller BEFORE loading tree to avoid race condition
        if self._preset_controller:
            self._preset_controller.on_workspace_changed(workspace_path)

        # 5. Load new tree (this increments generation counter, cancels old workers)
        self.file_tree_widget.load_tree(workspace_path)
        self.tree = self.file_tree_widget.get_model()._root_node  # type: ignore

        # Toggle stacked widget between file tree and empty state
        if hasattr(self, "_left_stacked_widget"):
            if workspace_path is None:
                self._left_stacked_widget.setCurrentIndex(1)
            else:
                self._left_stacked_widget.setCurrentIndex(0)

        # 6. Reset token display
        if hasattr(self, "_token_usage_bar"):
            self._token_usage_bar.update_stats(tokens=0, limit=200000, files=0)

        if hasattr(self, "_context_info_label"):
            self._context_info_label.setText("")
        if hasattr(self, "_limit_warning"):
            self._limit_warning.hide()

        # 7. Start file watcher for new workspace
        if (
            self._file_watcher
            and workspace_path is not None
            and workspace_path.exists()
        ):
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

        # 9. Sync Templates Button Text
        if hasattr(self, "_template_btn"):
            self._template_btn.setText("Templates")

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
        """Kiểm tra xem Smart Mode có đang active không."""
        return (
            self._mode_smart_btn.isChecked()
            if hasattr(self, "_mode_smart_btn")
            else False
        )

    def parent_widget(self):
        return self

    def get_copy_config(self) -> "CopyConfig":
        from domain.prompt.copy_mode import CopyConfig, CopyMode

        mode = CopyMode.FULL
        if hasattr(self, "_mode_smart_btn") and self._mode_smart_btn.isChecked():
            mode = CopyMode.SMART
        elif hasattr(self, "_mode_apply_btn") and self._mode_apply_btn.isChecked():
            mode = CopyMode.APPLY

        include_git = (
            self._git_diff_cb.isChecked() if hasattr(self, "_git_diff_cb") else False
        )
        tree_map_only = (
            self._tree_map_only_cb.isChecked()
            if hasattr(self, "_tree_map_only_cb")
            else False
        )
        commit_depth = (
            self._commit_depth_spin.value()
            if hasattr(self, "_commit_depth_spin")
            else 0
        )

        return CopyConfig(
            mode=mode,
            include_git_diff=include_git,
            tree_map_only=tree_map_only,
            output_style=self.get_output_style(),
            git_commit_depth=commit_depth,
        )

    def _on_copy_clicked(self) -> None:
        if self._copy_controller:
            self._copy_controller.on_copy_requested()

    def _on_configure_diff_clicked(self) -> None:
        if self._copy_controller:
            self._copy_controller._show_diff_only_dialog()

    def set_copy_buttons_enabled(self, enabled: bool) -> None:
        # Hien/an loading bar va cap nhat text button chinh
        if hasattr(self, "_copy_loading_bar"):
            self._copy_loading_bar.setVisible(not enabled)
        if hasattr(self, "_copy_btn"):
            self._copy_btn.setText("Copy" if enabled else "Processing...")
            self._copy_btn.setEnabled(enabled)

        # Enable/disable 3 mode buttons
        tree_map_only = (
            self._tree_map_only_cb.isChecked()
            if hasattr(self, "_tree_map_only_cb")
            else False
        )
        for btn in (
            getattr(self, "_mode_full_btn", None),
            getattr(self, "_mode_smart_btn", None),
            getattr(self, "_mode_apply_btn", None),
        ):
            if btn is not None:
                btn.setEnabled(enabled and not tree_map_only)

        for cb in (
            getattr(self, "_git_diff_cb", None),
            getattr(self, "_tree_map_only_cb", None),
        ):
            if cb is not None:
                cb.setEnabled(enabled)

        # Enable/disable commit depth spinbox và advanced config button
        include_git = (
            self._git_diff_cb.isChecked() if hasattr(self, "_git_diff_cb") else False
        )
        if hasattr(self, "_commit_depth_spin") and self._commit_depth_spin is not None:
            self._commit_depth_spin.setEnabled(enabled and include_git)
        if (
            hasattr(self, "_mode_diff_config_btn")
            and self._mode_diff_config_btn is not None
        ):
            self._mode_diff_config_btn.setEnabled(enabled)

        # Cập nhật text của _opx_btn cũ cho test tương thích ngược
        if hasattr(self, "_opx_btn"):
            self._opx_btn.setText(
                "Copy + Search/Replace" if enabled else "Processing..."
            )

        for btn in (
            self._diff_btn,
            self._tree_map_btn,
            self._smart_btn,
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

        # Show success message on StatusBar
        sb = self._get_status_bar()
        if sb:
            sb.showMessage(f"✅ Context copied! Processed {token_count:,} tokens", 5000)

    def _get_status_bar(self):
        """Lay statusBar tu QMainWindow cha."""
        from PySide6.QtWidgets import QMainWindow

        window = self.window()
        if isinstance(window, QMainWindow):
            return window.statusBar()
        return None

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

        self._improve_instructions_generation += 1
        self._cancel_improve_instructions_worker()

        self._ai_pick_files_generation += 1
        self._cancel_ai_pick_files_worker()

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
                        pass  # intentionally silent — signal connection might not exist
            except (RuntimeError, TypeError, AttributeError):
                pass  # intentionally silent — widget or widget children already deleted
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
            logger.error("context_view: operation failed", exc_info=True)

        if self._file_watcher:
            self._file_watcher.stop()
            self._file_watcher = None

        self.file_tree_widget.cleanup()

    def _cancel_improve_instructions_worker(self) -> None:
        """
        Huy va ngat ket noi signals cua ImproveInstructionsWorker neu dang chay.

        Giu nguyen generation guard trong _on_improve_instructions_finished/_on_improve_instructions_error
        de bo qua ket qua stale, nhung van dam bao khong co signal nao
        duoc deliver vao QWidget da bi huy.
        """
        worker = self._improve_instructions_worker
        if worker is None:
            return

        try:
            cancel = getattr(worker, "cancel", None)
            if callable(cancel):
                cancel()
        except Exception:
            logger.error("context_view: operation failed", exc_info=True)

        try:
            signals = getattr(worker, "signals", None)
            if signals is not None:
                try:
                    signals.finished.disconnect()
                except (RuntimeError, TypeError):
                    pass  # intentionally silent — signal might not be connected
                try:
                    signals.error.disconnect()
                except (RuntimeError, TypeError):
                    pass  # intentionally silent — signal might not be connected
                try:
                    signals.progress.disconnect()
                except (RuntimeError, TypeError):
                    pass  # intentionally silent — signal might not be connected
        except RuntimeError:
            # signals co the da bi xoa boi Qt
            pass  # intentionally silent — worker or signals already deleted by Qt

        self._improve_instructions_worker = None

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
        QTimer.singleShot(150, self, self._update_token_display)

    @Slot(str)
    def _on_format_changed(self, format_id: str) -> None:
        """Handle format change via menu action."""
        if not format_id:
            return
        try:
            self._selected_output_style = get_style_by_id(format_id)
            update_app_setting(output_format=format_id)

            # Update button text to reflect selection
            # Update button text to reflect selection
            if hasattr(self, "_format_btn"):
                config = get_format_config(self._selected_output_style)
                self._format_btn.setText(config.name)

            if self._copy_controller:
                self._copy_controller._prompt_cache.invalidate_all()
        except ValueError:
            pass

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

            if action_type == "edit" and template_id:
                self._show_custom_template_dialog(template_id)
                return

            if action_type == "delete" and template_id:
                reply = QMessageBox.question(
                    self,
                    "Delete Custom Template",
                    "Are you sure you want to delete this template?",
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

    @Slot()
    def _on_save_instruction_as_template(self) -> None:
        """Slot: Save current instruction as a template (one-click)."""
        text = self._instructions_field.toPlainText().strip()
        if not text:
            self.show_status(
                "Instructions are empty. Write something first!", is_error=True
            )
            return

        self._show_custom_template_dialog(initial_content=text)

    def _show_custom_template_dialog(
        self, template_id: Optional[str] = None, initial_content: Optional[str] = None
    ) -> None:
        """Hien thi dialog cho phep tao/sua Custom Template."""
        from presentation.components.dialogs.custom_template_dialog import (
            CustomTemplateDialog,
        )

        dialog = CustomTemplateDialog(
            self, template_id=template_id, initial_content=initial_content
        )
        if dialog.exec():
            status = (
                "Custom template saved!" if not template_id else "Template updated!"
            )
            self._show_status(status)

    @Slot()
    def _populate_template_menu(self) -> None:
        """Đổ dữ liệu template vào menu (dynamic build)."""
        from domain.prompt.template_manager import list_templates

        menu = self._template_menu
        menu.clear()

        templates = list_templates()
        builtin_templates = [t for t in templates if not getattr(t, "is_custom", False)]
        custom_templates = [t for t in templates if getattr(t, "is_custom", False)]

        # 1. Đổ dữ liệu các builtin templates
        for tmpl in builtin_templates:
            action = menu.addAction(tmpl.display_name)
            if tmpl.description:
                action.setToolTip(tmpl.description)
            action.setData(tmpl.template_id)

        # Thêm separator nếu có cả builtin và custom templates
        if builtin_templates and custom_templates:
            menu.addSeparator()

        # 2. Đổ dữ liệu các custom templates
        for tmpl in custom_templates:
            sub = menu.addMenu(f"{tmpl.display_name} (Custom)")
            if tmpl.description:
                sub.setToolTip(tmpl.description)
                sub.menuAction().setToolTip(tmpl.description)

            ins = sub.addAction("Insert")
            ins.setData({"action": "insert", "id": tmpl.template_id})

            edt = sub.addAction("Edit")
            edt.setData({"action": "edit", "id": tmpl.template_id})

            sub.addSeparator()

            dlt = sub.addAction("Delete")
            dlt.setData({"action": "delete", "id": tmpl.template_id})

        menu.addSeparator()
        add_action = menu.addAction("Manage/Add Custom Template...")
        add_action.setData("__CREATE_CUSTOM__")

    @Slot()
    def _populate_history_menu(self) -> None:
        """Đổ dữ liệu recent instructions vào history menu khi được click."""
        menu = self._history_menu
        menu.clear()

        settings = DomainRegistry.settings()
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
            clear_all_action = menu.addAction("Clear All History")
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
                settings = DomainRegistry.settings()
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

        reply = QMessageBox.question(
            self,
            "Clear History",
            "Are you sure you want to delete the entire Prompt history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            update_app_setting(instruction_history=[])
            self._show_status("All prompt history cleared.")

    # ===== Token Counting =====

    def _update_token_display(self) -> None:
        """Update token count display tu cached values. Khong trigger counting.

        Hien thi file tokens + instruction tokens tren toolbar.
        Tooltip phan tach ro 'instruction tokens' khi chua chon file nao
        de tranh confusion '39 tokens khi 0 files'.
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

        # Update Usage Bar (Toolbar) — single source of truth cho token stats
        if hasattr(self, "_token_usage_bar"):
            from domain.config.model_config import (
                get_model_by_id,
                DEFAULT_MODEL_ID,
            )

            model_id = getattr(self, "_selected_model_id", DEFAULT_MODEL_ID)
            model_cfg = get_model_by_id(model_id)
            limit = model_cfg.context_length if model_cfg else 128000

            selected_paths = list(self.file_tree_widget.get_selected_paths())
            selected_key = tuple(sorted(selected_paths))
            current_comparison_key = getattr(self, "_smart_comparison_key", None)
            comparison = (
                getattr(self, "_latest_token_comparison", None)
                if selected_key and selected_key == current_comparison_key
                else None
            )
            if not selected_key:
                self._latest_token_comparison = None
                self._smart_comparison_key = None

            # Update Toolbar progress bar
            self._token_usage_bar.update_stats(
                tokens=total,
                limit=limit,
                files=file_count,
                smart_tokens=comparison.smart_tokens if comparison else None,
                savings_pct=comparison.savings_pct if comparison else None,
            )
            self._request_token_comparison(selected_paths, total, limit, file_count)

            # Tooltip chia ro nguon token: file vs instruction.
            # Dac biet quan trong khi file_count=0 ma instruction_tokens>0
            # de user khong bi confused 'tai sao co 39 tokens khi chua chon file'.
            if file_count == 0 and instruction_tokens > 0:
                tooltip_note = (
                    f"Tip: {instruction_tokens:,} tokens are from your instructions,\n"
                    f"not from files. Select files to see file token counts."
                )
            else:
                tooltip_note = (
                    "Actual copy may include overhead (XML tags, tree structure)."
                )

            self._token_usage_bar.setToolTip(
                f"Token breakdown:\n"
                f"  Files:        {total_file_tokens:,} tokens\n"
                f"  Instructions: {instruction_tokens:,} tokens\n"
                f"  Total:        {total:,} tokens\n\n"
                f"Model: {model_cfg.name if model_cfg else 'Unknown'}\n"
                f"{tooltip_note}"
            )

    def _request_token_comparison(
        self,
        selected_paths: list[str],
        total_tokens: int,
        limit: int,
        file_count: int,
    ) -> None:
        """Chạy Smart token comparison trên background thread theo update path hiện có."""
        key = tuple(sorted(selected_paths))
        if not key:
            self._latest_token_comparison = None
            self._smart_comparison_key = None
            return

        current_key = getattr(self, "_smart_comparison_key", None)
        if (
            key == current_key
            and getattr(self, "_latest_token_comparison", None) is not None
        ):
            return

        if key == current_key and getattr(self, "_smart_comparison_worker", None):
            return

        self._smart_comparison_generation = (
            getattr(self, "_smart_comparison_generation", 0) + 1
        )
        generation = self._smart_comparison_generation
        self._smart_comparison_key = key
        paths_snapshot = list(key)

        def _compare() -> "TokenComparison":
            return self._token_comparison_service.compare_paths(paths_snapshot)

        def _apply(result: "TokenComparison") -> None:
            if generation != self._smart_comparison_generation:
                return
            self._latest_token_comparison = result
            if hasattr(self, "_token_usage_bar"):
                self._token_usage_bar.update_stats(
                    tokens=total_tokens,
                    limit=limit,
                    files=file_count,
                    smart_tokens=result.smart_tokens,
                    savings_pct=result.savings_pct,
                )

        def _clear_worker() -> None:
            if generation == self._smart_comparison_generation:
                self._smart_comparison_worker = None

        from presentation.utils.qt_utils import schedule_background

        self._smart_comparison_worker = schedule_background(
            _compare,
            on_result=_apply,
            on_finished=_clear_worker,
        )

    @Slot(str)
    def _on_model_changed(self, model_id: str) -> None:
        """
        Handler when user changes model.

        Resets encoder and clears cache to trigger recount with the new tokenizer.
        """
        # Reset encoder va reinitialize voi model moi qua TokenizationService
        from domain.config.model_config import get_model_by_id

        settings = DomainRegistry.settings()
        model_config = get_model_by_id(settings.model_id)
        repo = model_config.tokenizer_repo if model_config else None
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

    # ===== Improve User Instructions (doc tu Instructions field) =====

    def _run_improve_instructions(self) -> None:
        """
        Doc noi dung tu Instructions field va chay ImproveInstructionsWorker de cai thien instructions.

        Luong xu ly:
        1. Doc text tu _instructions_field
        2. Validate settings (API key, model)
        3. Thu thap file tree va git diff (neu co workspace) de lam context
        4. Tao ImproveInstructionsWorker chay tren background thread
        5. Khi worker xong -> cap nhat ket qua vao _instructions_field
        """
        user_query = self._instructions_field.toPlainText().strip()
        if not user_query:
            from presentation.components.toast.toast_qt import toast_error

            toast_error("Please write your instruction first.")
            return

        from application.services.improve_instructions_worker import (
            ImproveInstructionsWorker,
        )
        from domain.prompt.generator import generate_file_map
        from domain.prompt.context_builder_prompts import build_full_tree_string
        from presentation.components.toast.toast_qt import toast_error

        settings = DomainRegistry.settings()
        if not settings.ai_api_key:
            toast_error("Please configure AI API Key in Settings first.")
            return
        if not settings.ai_model_id:
            toast_error("Please select an AI model in Settings first.")
            return

        workspace = self.get_workspace()
        file_tree_map = None
        git_diff_str = None

        if self.tree:
            all_paths = self._collect_all_tree_paths(self.tree)
            file_tree_map = generate_file_map(
                self.tree,
                all_paths,
                workspace_root=workspace,
                use_relative_paths=True,
            )

            # Optional: Git diff
            if workspace:
                try:
                    diff_result = DomainRegistry.git_service().get_diffs(workspace)
                    if diff_result is not None:
                        _, git_diff_str = build_full_tree_string(
                            file_tree_map, diff_result, include_git=True
                        )
                except Exception:
                    logger.error("context_view: operation failed", exc_info=True)

        # Disable button khi dang chay
        self._improve_instructions_btn.setEnabled(False)
        self._improve_instructions_btn.setText("Improving...")

        # Tao worker chay tren background thread
        worker = ImproveInstructionsWorker(
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            model_id=settings.ai_model_id,
            user_query=user_query,
            file_tree=file_tree_map,
            git_diff=git_diff_str,
        )

        self._improve_instructions_generation += 1
        current_gen = self._improve_instructions_generation

        worker.signals.finished.connect(
            lambda improved, explanation, usage, g=current_gen: (
                self._on_improve_instructions_finished(improved, explanation, usage, g)
            )
        )
        worker.signals.error.connect(
            lambda msg, g=current_gen: self._on_improve_instructions_error(msg, g)
        )
        worker.signals.progress.connect(self._on_improve_instructions_progress)

        # Giu reference tranh GC
        self._improve_instructions_worker = worker
        from PySide6.QtCore import QThreadPool

        QThreadPool.globalInstance().start(worker)

    def _on_improve_instructions_finished(
        self, improved_instructions: str, explanation: str, usage: dict, generation: int
    ) -> None:
        """Xu ly khi Improve instructions worker hoan thanh thanh cong."""
        if generation != self._improve_instructions_generation:
            return

        self._improve_instructions_worker = None
        self._improve_instructions_btn.setEnabled(True)
        self._improve_instructions_btn.setText("Improve Instructions")

        if improved_instructions:
            self._instructions_field.setPlainText(improved_instructions)

            from presentation.components.toast.toast_qt import toast_success

            toast_success("Instructions improved successfully!")
        else:
            from presentation.components.toast.toast_qt import toast_error

            toast_error("AI could not improve the instructions.")

    def _on_improve_instructions_error(self, error_msg: str, generation: int) -> None:
        """Xu ly khi Improve instructions worker gap loi."""
        if generation != self._improve_instructions_generation:
            return

        self._improve_instructions_worker = None
        self._improve_instructions_btn.setEnabled(True)
        self._improve_instructions_btn.setText("Improve Instructions")

        from presentation.components.toast.toast_qt import toast_error

        toast_error(error_msg)

    def _on_improve_instructions_progress(self, status: str) -> None:
        """Cap nhat text button khi worker dang chay."""
        self._improve_instructions_btn.setText(status)

    # ===== AI Pick Files =====

    def _cancel_ai_pick_files_worker(self) -> None:
        """Huỷ và ngắt kết nối signals của AIPickFilesWorker nếu đang chạy."""
        worker = self._ai_pick_files_worker
        if worker is None:
            return

        try:
            cancel = getattr(worker, "cancel", None)
            if callable(cancel):
                cancel()
        except Exception:
            logger.error(
                "context_view: cancel ai_pick_files_worker failed", exc_info=True
            )

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
            pass

        self._ai_pick_files_worker = None

        # Huỷ dialog nếu có
        dialog = getattr(self, "_ai_pick_files_dialog", None)
        if dialog:
            try:
                dialog.reject()
            except Exception:
                pass
            self._ai_pick_files_dialog = None

    def _run_ai_pick_files(self) -> None:
        """
        Đọc instruction hiện tại và chạy AIPickFilesWorker trong background thread.
        """
        # 1. Single-flight guard
        if self._ai_pick_files_worker is not None:
            self._show_status("AI file selection is already running.", is_error=True)
            return

        user_instruction = self.get_instructions_text().strip()
        if not user_instruction:
            self._show_status("Please write your instruction first.", is_error=True)
            return
        if len(user_instruction) > 8000:
            self._show_status(
                "Instruction is too long. Shorten it to under 8000 characters.",
                is_error=True,
            )
            return

        workspace = self.get_workspace()
        if not workspace:
            self._show_status(
                "No folder opened. Open a workspace first.", is_error=True
            )
            return

        # Validate workspace directory existence
        if not Path(workspace).is_dir():
            self._show_status(
                "Workspace path is invalid or does not exist.", is_error=True
            )
            return

        settings = DomainRegistry.settings()
        if not settings.ai_api_key:
            self._show_status(
                "Please configure AI API Key in Settings first.", is_error=True
            )
            return
        if not settings.ai_model_id:
            self._show_status(
                "Please select an AI model in Settings first.", is_error=True
            )
            return

        from application.services.ai_pick_files_worker import AIPickFilesWorker
        from presentation.components.dialogs.ai_pick_files_dialog import (
            AIPickFilesDialog,
        )
        from PySide6.QtCore import QThreadPool

        # Disable button khi đang chạy
        self._ai_pick_files_btn.setEnabled(False)
        self._ai_pick_files_btn.setText("AI Picking...")

        # Khởi tạo và hiển thị Dialog tiến độ (non-blocking)
        self._ai_pick_files_dialog = AIPickFilesDialog(self)
        self._ai_pick_files_dialog.rejected.connect(self._cancel_ai_pick_files_worker)
        self._ai_pick_files_dialog.show()

        # Tạo worker chạy trên background thread
        worker = AIPickFilesWorker(
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            model_id=settings.ai_model_id,
            workspace=str(workspace),
            user_instruction=user_instruction,
        )

        self._ai_pick_files_generation += 1
        current_gen = self._ai_pick_files_generation

        worker.signals.finished.connect(
            lambda paths, g=current_gen: self._on_ai_pick_files_finished(paths, g)
        )
        worker.signals.error.connect(
            lambda msg, g=current_gen: self._on_ai_pick_files_error(msg, g)
        )
        # Kết nối progress signal bảo vệ bằng generation counter
        worker.signals.progress.connect(
            lambda msg, g=current_gen: self._on_ai_pick_files_progress(msg, g)
        )

        # Giữ reference tránh GC
        self._ai_pick_files_worker = worker
        QThreadPool.globalInstance().start(worker)

    def _on_ai_pick_files_finished(self, paths: list, generation: int) -> None:
        if generation != self._ai_pick_files_generation:
            return

        self._ai_pick_files_worker = None
        self._ai_pick_files_btn.setEnabled(True)
        self._ai_pick_files_btn.setText("AI Pick Files")

        # Đóng dialog thành công
        dialog = getattr(self, "_ai_pick_files_dialog", None)
        if dialog:
            dialog.update_step(3, "success", f"Selected {len(paths)} files")
            dialog.finish_with_success()
            self._ai_pick_files_dialog = None

        if not paths:
            self._show_status(
                "AI found no relevant files in the workspace.", is_error=False
            )
            return

        settings = DomainRegistry.settings()
        auto_apply = getattr(settings, "ai_auto_apply", True)

        # Nếu số lượng file đề xuất > 50 hoặc auto_apply tắt, hiện Dialog xác nhận
        if len(paths) > 50 or not auto_apply:
            from PySide6.QtWidgets import QMessageBox

            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Apply Selection?")
            msg_box.setText(
                f"AI suggested {len(paths)} files.\nDo you want to apply this selection to your workspace?"
            )
            msg_box.setIcon(QMessageBox.Icon.Question)
            msg_box.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            msg_box.setStyleSheet(f"""
                QMessageBox {{
                    background-color: {ThemeColors.BG_SURFACE};
                    color: white;
                }}
                QLabel {{
                    color: white;
                    font-size: 12px;
                }}
                QPushButton {{
                    background-color: {ThemeColors.BG_ELEVATED};
                    color: white;
                    border: 1px solid {ThemeColors.BORDER_LIGHT};
                    border-radius: 4px;
                    padding: 4px 14px;
                    min-width: 60px;
                }}
                QPushButton:hover {{
                    background-color: {ThemeColors.PRIMARY}20;
                    border-color: {ThemeColors.PRIMARY};
                }}
            """)
            if msg_box.exec() != QMessageBox.StandardButton.Yes:
                self._show_status("AI file suggestions discarded.")
                return

        # Đồng bộ hóa qua public API sync_agent_selection của file_tree_widget
        if hasattr(self, "file_tree_widget") and self.file_tree_widget:
            self.file_tree_widget.sync_agent_selection(paths)

        self._show_status(f"AI suggested {len(paths)} files; applied successfully!")

    def _on_ai_pick_files_error(self, error_msg: str, generation: int) -> None:
        if generation != self._ai_pick_files_generation:
            return

        self._ai_pick_files_worker = None
        self._ai_pick_files_btn.setEnabled(True)
        self._ai_pick_files_btn.setText("AI Pick Files")

        # Actionable error mapping
        sanitized_msg = error_msg.lower()
        if (
            "401" in sanitized_msg
            or "invalid key" in sanitized_msg
            or "authentication" in sanitized_msg
        ):
            display_msg = "API key was rejected. Check AI Context Builder in Settings."
        elif "403" in sanitized_msg or "forbidden" in sanitized_msg:
            display_msg = "API key does not have access to the selected model."
        elif "404" in sanitized_msg or "not found" in sanitized_msg:
            display_msg = "Selected AI model was not found."
        elif "timeout" in sanitized_msg or "timed out" in sanitized_msg:
            display_msg = "AI provider did not respond in time."
        elif "connection refused" in sanitized_msg or "connect" in sanitized_msg:
            display_msg = "Could not connect to AI provider. Verify Base URL and network connection."
        else:
            display_msg = error_msg
            if (
                "authorization" in display_msg.lower()
                or "api_key" in display_msg.lower()
                or "bearer" in display_msg.lower()
            ):
                display_msg = "Invalid authorization or AI credentials."
            if len(display_msg) > 120:
                display_msg = display_msg[:120] + "..."

        # Đánh dấu bước lỗi và đóng Dialog sau 2s
        dialog = getattr(self, "_ai_pick_files_dialog", None)
        if dialog:
            dialog.update_step(2, "error", f"Error: {display_msg}")
            from PySide6.QtCore import QTimer

            QTimer.singleShot(2000, dialog, dialog.reject)
            self._ai_pick_files_dialog = None

        self._show_status(f"AI Pick Files failed: {display_msg}", is_error=True)

    def _on_ai_pick_files_progress(self, status: str, generation: int) -> None:
        if generation != self._ai_pick_files_generation:
            return

        if hasattr(self, "_ai_pick_files_btn") and self._ai_pick_files_btn:
            self._ai_pick_files_btn.setText("AI Picking...")

        dialog = getattr(self, "_ai_pick_files_dialog", None)
        if not dialog:
            return

        if status == "Initializing Codex...":
            dialog.update_step(0, "active")
        elif status == "Connecting to Agent...":
            dialog.update_step(0, "success")
            dialog.update_step(1, "active")
        elif status == "AI Selecting...":
            dialog.update_step(1, "success")
            dialog.update_step(2, "active", "AI is analyzing workspace...")
        elif status.startswith("tool_call:"):
            tool_name = status.split(":", 1)[1]
            dialog.update_step(2, "active", f"Agent is running '{tool_name}'...")
        elif status == "reasoning":
            dialog.update_step(2, "active", "Agent is thinking...")
        elif status == "file_change":
            dialog.update_step(2, "active", "Agent is applying file changes...")
        elif status == "Synchronizing...":
            dialog.update_step(2, "success")
            dialog.update_step(3, "active")

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
