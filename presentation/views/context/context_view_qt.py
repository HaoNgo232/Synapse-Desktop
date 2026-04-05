"""
Context View (PySide6) - Tab để chọn files và copy context.

Refactored to use Component Composition pattern instead of Mixins.
Logic is delegated to Controllers, and UI is composed of independent Components.

This version includes compatibility aliases and properties to support existing tests
and controllers that expect certain attributes.
"""

import logging
import gc
from pathlib import Path
from typing import Optional, Set, List, Callable, TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from domain.filesystem.ignore_engine import IgnoreEngine
    from application.interfaces.tokenization_port import ITokenizationService
    from domain.relationships.port import IRelationshipGraphProvider

from PySide6.QtWidgets import QWidget, QVBoxLayout, QSplitter
from PySide6.QtCore import Slot, QTimer, Qt

from infrastructure.filesystem.file_watcher_facade import FileWatcher, WatcherCallbacks
from infrastructure.persistence import settings_manager

from presentation.config.theme import ThemeColors
from presentation.config.output_format import (
    OutputStyle,
    get_style_by_id,
    DEFAULT_OUTPUT_STYLE,
)

# Components
from presentation.views.context.components.context_toolbar import ContextToolbar
from presentation.views.context.components.file_panel import FilePanel
from presentation.views.context.components.instructions_panel import InstructionsPanel
from presentation.views.context.components.actions_panel import ActionsPanel
from presentation.components.preset_widget import PresetWidget

# Controllers
from presentation.views.context.copy_action_controller import CopyActionController
from presentation.views.context.related_files_controller import RelatedFilesController
from presentation.views.context.tree_management_controller import (
    TreeManagementController,
)
from presentation.views.context.preset_controller import PresetController


logger = logging.getLogger(__name__)


class ContextViewQt(QWidget):
    """View cho Context tab - Refactored version using Composition."""

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
        self.get_workspace_path = get_workspace  # Alias

        # Services Injection
        if ignore_engine is None:
            from domain.filesystem.ignore_engine import IgnoreEngine as _IE

            ignore_engine = _IE()
        self._ignore_engine = ignore_engine

        if tokenization_service is None:
            from infrastructure.adapters.encoder_registry import (
                get_tokenization_service,
            )

            tokenization_service = get_tokenization_service()
        self._tokenization_service = tokenization_service
        self._graph_provider = graph_provider

        # Controllers
        self._related_controller = RelatedFilesController(
            self, graph_provider=self._graph_provider
        )
        self._tree_controller = TreeManagementController(self, parent=None)
        self._copy_controller = CopyActionController(self, parent=None)
        self._preset_controller = PresetController(self, parent=None)

        # External services for controllers
        if prompt_builder is None:
            from application.services.prompt_build_service import PromptBuildService

            prompt_builder = PromptBuildService(
                tokenization_service=self._tokenization_service,
                graph_service=cast(Any, self._graph_provider),
            )
        self._prompt_builder = prompt_builder

        if clipboard_service is None:
            from infrastructure.adapters.clipboard_service import QtClipboardService

            clipboard_service = QtClipboardService()
        self._clipboard_service = clipboard_service

        # State
        self.tree = None
        self._selected_output_style: OutputStyle = DEFAULT_OUTPUT_STYLE
        self._token_generation = 0
        self._ai_suggest_worker = None
        self._ai_suggest_previous_selection: Optional[List[str]] = None
        self._ai_suggest_generation: int = 0
        self._file_watcher = FileWatcher()
        self._is_loading = False  # Compatibility with tests

        # Build UI via Composition
        self._init_ui()

        # Initialize displays from settings
        settings = settings_manager.load_app_settings()
        self.instructions_panel.update_template_tier_display(
            getattr(settings, "template_tier", "lite")
        )

        # Connect signals
        self._setup_connections()
        self._setup_shortcuts()
        self._setup_graph_signals()

    def _init_ui(self) -> None:
        """Initialize and compose UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Toolbar
        self.toolbar = ContextToolbar(self)
        layout.addWidget(self.toolbar)

        # Add PresetWidget to toolbar dynamically
        self._preset_widget = PresetWidget(controller=self._preset_controller)
        if hasattr(self._preset_widget, "_label"):
            self._preset_widget._label.hide()
        self._preset_widget.setFixedHeight(30)
        self.toolbar.layout_for_presets.addWidget(self._preset_widget)

        # 2. Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(3)
        splitter.setStyleSheet(
            f"QSplitter::handle {{ background-color: {ThemeColors.BORDER}; margin: 4px 0; }}"
        )

        # Left Panel (Files)
        self.file_panel = FilePanel(
            self._ignore_engine, self._tokenization_service, self
        )
        splitter.addWidget(self.file_panel)

        # Center Panel (Instructions)
        self.instructions_panel = InstructionsPanel(self)
        splitter.addWidget(self.instructions_panel)

        # Right Panel (Actions)
        self.actions_panel = ActionsPanel(self)
        splitter.addWidget(self.actions_panel)

        splitter.setStretchFactor(0, 30)
        splitter.setStretchFactor(1, 40)
        splitter.setStretchFactor(2, 30)
        splitter.setSizes([400, 550, 450])

        layout.addWidget(splitter, 1)

    # --- Compatibility Accessors for Tests and Controllers ---
    @property
    def _instructions_field(self):
        return self.instructions_panel.instructions_field

    @property
    def _word_count_label(self):
        return self.instructions_panel._word_count_label

    @property
    def _token_usage_bar(self):
        return self.toolbar.token_usage_bar

    @property
    def _opx_btn(self):
        return self.actions_panel.opx_btn

    @property
    def _copy_btn(self):
        return self.actions_panel.copy_btn

    @property
    def _smart_btn(self):
        return self.actions_panel.compress_btn

    @property
    def _diff_btn(self):
        return self.actions_panel.diff_btn

    @property
    def _tree_map_btn(self):
        return self.actions_panel.tree_map_btn

    @property
    def _format_btn(self):
        return self.toolbar._format_btn

    @property
    def _history_menu(self):
        return self.instructions_panel._history_menu

    @property
    def _template_menu(self):
        return self.instructions_panel._template_menu

    @property
    def repo_manager(self):
        if not hasattr(self, "_repo_manager"):
            from infrastructure.git.repo_manager import RepoManager

            self._repo_manager = RepoManager()
        return self._repo_manager

    def _setup_connections(self) -> None:
        """Kết nối các signal từ components vào logic xử lý của view/controllers."""
        # Toolbar actions - Các thao tác trên thanh công cụ
        self.toolbar.refresh_requested.connect(self._tree_controller.refresh_tree)
        self.toolbar.clone_repo_requested.connect(
            lambda: self._tree_controller.open_remote_repo_dialog(self)
        )
        self.toolbar.manage_cache_requested.connect(
            lambda: self._tree_controller.open_cache_management_dialog(self)
        )
        self.toolbar.related_mode_changed.connect(self._related_controller.set_mode)
        self.toolbar.format_changed.connect(self._on_format_changed)
        self.toolbar.model_changed.connect(self._on_model_changed)

        # File Panel actions - Thao tác trên cây thư mục file
        self.file_panel.selection_changed.connect(self._on_selection_changed)
        self.file_panel.file_preview_requested.connect(self._preview_file)
        self.file_panel.token_counting_done.connect(self._update_token_display)
        self.file_panel.exclude_patterns_changed.connect(
            self._tree_controller.refresh_tree
        )

        # Instructions actions - Thao tác trên khung nhập chỉ dẫn (prompt)
        self.instructions_panel.text_changed.connect(self._on_instructions_changed)
        self.instructions_panel.ai_suggest_requested.connect(
            self._run_ai_suggest_from_instructions
        )
        self.instructions_panel.template_menu_about_to_show.connect(
            self._populate_template_menu
        )
        self.instructions_panel.history_menu_about_to_show.connect(
            self._populate_history_menu
        )
        self.instructions_panel.template_selected.connect(self._on_template_selected)
        self.instructions_panel.history_selected.connect(self._on_history_selected)

        # Actions Panel actions - Các nút copy và tùy chọn output
        self.actions_panel.copy_opx_requested.connect(
            lambda: self._copy_controller.on_copy_context_requested(include_xml=True)
        )
        self.actions_panel.copy_requested.connect(
            lambda: self._copy_controller.on_copy_context_requested(include_xml=False)
        )
        self.actions_panel.compress_requested.connect(
            self._copy_controller.on_copy_smart_requested
        )
        self.actions_panel.git_diff_requested.connect(
            self._copy_controller._show_diff_only_dialog
        )
        self.actions_panel.tree_map_requested.connect(
            self._copy_controller.on_copy_tree_map_requested
        )

        self.actions_panel.copy_as_file_toggled.connect(
            lambda: None
        )  # Managed via getter
        self.actions_panel.full_tree_toggled.connect(self._on_full_tree_toggled)
        self.actions_panel.semantic_index_toggled.connect(
            self._on_semantic_index_toggled
        )

        # Kết nối PresetWidget với sự thay đổi selection để highlight/dirty check
        self._preset_widget.connect_selection_changed(self.file_panel.selection_changed)

    # === Private Handlers ===

    def _on_full_tree_toggled(self, checked: bool) -> None:
        settings_manager.update_app_setting(include_full_tree=checked)
        if self._copy_controller:
            self._copy_controller._prompt_cache.invalidate_all()
        self._update_token_display()

    def _on_semantic_index_toggled(self, checked: bool) -> None:
        settings_manager.update_app_setting(enable_semantic_index=checked)
        if self._copy_controller:
            self._copy_controller._prompt_cache.invalidate_all()
        self._update_token_display()

    @Slot(set)
    def _on_selection_changed(self, selected_paths: set) -> None:
        if not self._copy_controller or not self._related_controller:
            return
        self._token_generation += 1
        self._copy_controller._prompt_cache.invalidate_all()
        self._update_token_display()
        self._related_controller.resolve_for_current_selection()

    @Slot()
    def _on_instructions_changed(self, text: str) -> None:
        # Word count is handled internally by InstructionsPanel
        QTimer.singleShot(150, self._update_token_display)

    @Slot(str)
    def _on_format_changed(self, format_id: str) -> None:
        try:
            self._selected_output_style = get_style_by_id(format_id)
            settings_manager.update_app_setting(output_format=format_id)
            self.toolbar.update_format_display(format_id)
            if self._copy_controller:
                self._copy_controller._prompt_cache.invalidate_all()
        except ValueError:
            pass

    @Slot(str)
    def _on_model_changed(self, model_id: str) -> None:
        from infrastructure.adapters.encoder_registry import get_tokenizer_repo

        repo = get_tokenizer_repo()
        self._tokenization_service.set_model_config(tokenizer_repo=repo)

        self.toolbar.update_model_display(model_id)
        settings_manager.update_app_setting(model_id=model_id)

        if self._copy_controller:
            self._copy_controller._prompt_cache.invalidate_all()

        model = self.file_panel.file_tree_widget.get_model()
        model._token_cache.clear()
        self.file_panel.file_tree_widget._start_token_counting()
        self._show_status(f"Recounting tokens with {model_id}...")

    # === Public API for Controllers / MainWindow ===

    def on_workspace_changed(self, workspace_path: Path) -> None:
        """Handle workspace change."""
        if (
            not self._copy_controller
            or not self._related_controller
            or not self._tree_controller
        ):
            return

        # 0. Invalidate operations
        self._copy_controller._begin_copy_operation()
        self.set_copy_buttons_enabled(True)
        self._ai_suggest_generation += 1
        self._cancel_ai_suggest_worker()
        self.instructions_panel.set_ai_suggest_busy(False)

        # 1. Watcher
        if self._file_watcher:
            self._file_watcher.stop()

        # 2. Reset state
        self._related_controller.set_mode(False, 0, silent=True)
        from infrastructure.adapters.cache_registry import cache_registry

        cache_registry.invalidate_for_workspace()
        self._copy_controller._prompt_cache.invalidate_all()

        if self._preset_controller:
            self._preset_controller.on_workspace_changed(workspace_path)

        # 3. Load tree
        self.file_panel.load_tree(workspace_path)
        self.tree = self.file_panel.file_tree_widget.get_model()._root_node

        # 4. Reset display
        self.toolbar.token_usage_bar.update_stats(tokens=0, limit=200000, files=0)
        self.actions_panel.show_limit_warning("")

        # 5. Start watcher
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

        if self._graph_provider:
            self._graph_provider.on_workspace_changed(workspace_path)

    def restore_tree_state(
        self, selected_files: List[str], expanded_folders: List[str]
    ) -> None:
        if selected_files:
            valid = {f for f in selected_files if Path(f).exists()}
            self.file_panel.set_selected_paths(valid)
        if expanded_folders:
            valid_list = [f for f in expanded_folders if Path(f).exists()]
            self.file_panel.set_expanded_paths(valid_list)  # Fix: list[str]
        self._update_token_display()

    def get_selected_paths(self) -> Set[str]:
        return self.file_panel.get_selected_paths()

    def get_all_selected_paths(self) -> Set[str]:
        return self.file_panel.get_all_selected_paths()

    def get_expanded_paths(self) -> List[str]:
        return self.file_panel.get_expanded_paths()

    def load_tree(self, workspace: Path) -> None:
        """Alias for TreeManagementController compatibility."""
        self.file_panel.load_tree(workspace)

    def add_paths_to_selection(self, paths: Set[str]) -> int:
        return self.file_panel.add_paths_to_selection(paths)

    def remove_paths_from_selection(self, paths: Set[str]) -> int:
        return self.file_panel.remove_paths_from_selection(paths)

    def set_selected_paths_from_preset(self, paths: Set[str]) -> None:
        self.file_panel.set_selected_paths(paths)

    def set_instructions_text(self, text: str) -> None:
        self.instructions_panel.set_text(text)

    def get_instructions_text(self) -> str:
        return self.instructions_panel.get_text()

    def get_output_style(self) -> OutputStyle:
        return self._selected_output_style

    def set_copy_buttons_enabled(self, enabled: bool) -> None:
        self.actions_panel.set_buttons_enabled(enabled)

    # === Logic methods (Ported from ContextViewQt / UIBuilderMixin) ===

    @Slot(object)
    def _populate_template_menu(self, menu=None) -> None:
        if menu is None:
            menu = self._template_menu
        from domain.prompt.template_manager import list_templates
        from PySide6.QtWidgets import QWidgetAction
        from presentation.components.tier_selector import TierSelector

        menu.clear()
        new_tier = getattr(
            settings_manager.load_app_settings(), "template_tier", "lite"
        )
        tier_selector = TierSelector(initial_tier=new_tier)
        tier_selector.tier_changed.connect(self._on_tier_changed)
        tier_selector.setContentsMargins(8, 4, 8, 4)

        action = QWidgetAction(menu)
        action.setDefaultWidget(tier_selector)
        menu.addAction(action)
        menu.addSeparator()

        for tmpl in list_templates():
            if getattr(tmpl, "is_custom", False):
                sub = menu.addMenu(tmpl.display_name)
                sub.addAction("Insert").setData(
                    {"action": "insert", "id": tmpl.template_id}
                )
                sub.addAction("Edit").setData(
                    {"action": "edit", "id": tmpl.template_id}
                )
                sub.addSeparator()
                sub.addAction("Delete").setData(
                    {"action": "delete", "id": tmpl.template_id}
                )
            else:
                action = menu.addAction(tmpl.display_name)
                action.setData(tmpl.template_id)

        menu.addSeparator()
        menu.addAction("Manage/Add Custom Template...").setData("__CREATE_CUSTOM__")

    @Slot(object)
    def _on_template_selected(self, action) -> None:
        from domain.prompt.template_manager import load_template, delete_template
        from PySide6.QtWidgets import QMessageBox

        data = action.data()
        if not data:
            return

        if isinstance(data, dict):
            action_type = data.get("action")
            template_id = str(data.get("id", ""))
            if action_type == "edit":
                self._show_custom_template_dialog(template_id)
                return
            if action_type == "delete":
                if (
                    QMessageBox.question(self, "Delete", "Are you sure?")
                    == QMessageBox.StandardButton.Yes
                ):
                    if delete_template(template_id):
                        self._show_status("Deleted")
                return
            template_id = template_id
        else:
            template_id = str(data)

        if template_id == "__CREATE_CUSTOM__":
            self._show_custom_template_dialog()
            return

        try:
            self._instructions_field.setPlainText(load_template(template_id))
            self._show_status("Template loaded")
        except Exception as e:
            self._show_status(f"Error: {e}", True)

    def _show_custom_template_dialog(self, template_id: Optional[str] = None) -> None:
        """
        Hiển thị dialog để tạo mới hoặc chỉnh sửa template tùy chỉnh.
        Fix Bug 2.
        """
        from presentation.components.dialogs.custom_template_dialog import (
            CustomTemplateDialog,
        )

        dialog = CustomTemplateDialog(self, template_id=template_id)
        if dialog.exec():
            status = (
                "Custom template saved!" if not template_id else "Template updated!"
            )
            self._show_status(status)

    @Slot(object)
    def _populate_history_menu(self, menu=None) -> None:
        if menu is None:
            menu = self._history_menu
        menu.clear()
        history = settings_manager.load_app_settings().instruction_history
        if not history:
            action = menu.addAction("No history yet")
            action.setEnabled(False)
            return
        for text in history:
            label = (text[:50] + "...") if len(text) > 50 else text
            sub = menu.addMenu(label.replace("\n", " "))
            sub.addAction("Apply").setData({"action": "insert", "text": text})
            sub.addSeparator()
            sub.addAction("Delete").setData({"action": "delete", "text": text})
        menu.addSeparator()
        menu.addAction("Clear All History").setData({"action": "clear_all"})

    @Slot(object)
    def _on_history_selected(self, action) -> None:
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
                settings = settings_manager.load_app_settings()
                h = settings.instruction_history.copy()
                if text in h:
                    h.remove(text)
                    settings_manager.update_app_setting(instruction_history=h)
                    self._show_status("History item deleted.")
                return
        else:
            text = str(data)

        if text:
            self._instructions_field.setPlainText(text)
            self._show_status("History loaded")

    def _clear_prompt_history(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        if (
            QMessageBox.question(self, "Clear", "Clear all history?")
            == QMessageBox.StandardButton.Yes
        ):
            settings_manager.update_app_setting(instruction_history=[])
            self._show_status("All prompt history cleared.")

    def _update_token_display(self) -> None:
        # Avoid crashes if internal components are missing during rapid transitions
        if not hasattr(self, "file_panel") or not self.file_panel:
            return

        selected_count = (
            self.file_panel.file_tree_widget.get_model().get_selected_file_count()
        )
        instructions = self.get_instructions_text()
        instruction_tokens = (
            self._prompt_builder.count_tokens(instructions) if instructions else 0
        )
        file_tokens = self.file_panel.get_total_tokens()
        total = file_tokens + instruction_tokens

        from presentation.config.model_config import get_model_by_id, DEFAULT_MODEL_ID

        m_id = getattr(self, "_selected_model_id", DEFAULT_MODEL_ID)
        m_cfg = get_model_by_id(m_id)
        limit = m_cfg.context_length if m_cfg else 128000

        self.toolbar.token_usage_bar.update_stats(
            tokens=total, limit=limit, files=selected_count
        )

    def scan_full_tree(self, workspace: Path) -> Any:
        from infrastructure.filesystem.file_scanner import (
            scan_directory,
        )  # FIX: đúng module cho scan_directory
        from application.services.workspace_config import (
            get_excluded_patterns,
            get_use_gitignore,
        )

        excluded = get_excluded_patterns()
        use_gitignore = get_use_gitignore()
        return scan_directory(
            workspace,
            ignore_engine=self._ignore_engine,
            excluded_patterns=excluded,
            use_gitignore=use_gitignore,
        )

    def parent_widget(self) -> QWidget:
        return self

    def is_smart_mode_active(self) -> bool:
        return False

    def update_related_button_text(self, active: bool, depth: int, count: int) -> None:
        self.toolbar.update_related_button_text(active, depth, count)

    def show_copy_breakdown(self, token_count: int, breakdown: dict) -> None:
        from presentation.components.toast.toast_qt import toast_success

        mode = breakdown.get("copy_mode", "Copy")
        toast_success(
            message=f"Processed {token_count:,} tokens", title=f"{mode} successful!"
        )
        sb = self._get_status_bar()
        if sb:
            sb.showMessage(f"✅ Context copied! {token_count:,} tokens", 5000)

    def _get_status_bar(self):
        from PySide6.QtWidgets import QMainWindow

        w = self.window()
        return w.statusBar() if isinstance(w, QMainWindow) else None

    def _show_status(self, message: str, is_error: bool = False) -> None:
        from presentation.components.toast.toast_qt import toast_error, toast_success

        if not message:
            return
        if is_error:
            toast_error(message)
        else:
            toast_success(message)

    def show_status(self, message: str, is_error: bool = False) -> None:
        """Alias public cho _show_status de thoa man view protocols."""
        self._show_status(message, is_error)

    @Slot(str)
    def _preview_file(self, file_path: str) -> None:
        from presentation.components.dialogs.dialogs_qt import FilePreviewDialogQt

        FilePreviewDialogQt.show_preview(self, file_path)

    @Slot(str)
    def _on_tier_changed(self, tier: str) -> None:
        settings_manager.update_app_setting(template_tier=tier)
        if self._copy_controller:
            self._copy_controller._prompt_cache.invalidate_all()
        # Removed the call that resets Related Files: self.toolbar.update_related_button_text(False, 0, 0)
        self.instructions_panel.update_template_tier_display(
            tier
        )  # Cập nhật nhãn Templates
        self._show_status(f"Tier switched to {tier.capitalize()}")

    def _run_ai_suggest_from_instructions(self) -> None:
        user_query = self.get_instructions_text().strip()
        if not user_query:
            self._show_status("Please write instruction first", True)
            return
        settings = settings_manager.load_app_settings()
        if not settings.ai_api_key or not settings.ai_model_id:
            self._show_status("Configure AI settings first", True)
            return
        if self.tree is None:
            self._show_status("Open folder first", True)
            return
        self.instructions_panel.set_ai_suggest_busy(True)
        workspace = self.get_workspace()
        # ... rest ...
        all_paths = self._collect_all_tree_paths(self.tree)
        from domain.prompt.generator import generate_file_map

        file_tree_map = generate_file_map(
            self.tree, all_paths, workspace_root=workspace, use_relative_paths=True
        )
        from application.services.ai_context_worker import AIContextWorker

        worker = AIContextWorker(
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            model_id=settings.ai_model_id,
            file_tree=file_tree_map,
            user_query=user_query,
            all_file_paths=list(all_paths),
            workspace_root=workspace,
        )
        self._ai_suggest_generation += 1
        gen = self._ai_suggest_generation
        worker.signals.finished.connect(
            lambda p, r, u, g=gen: self._on_ai_suggest_finished(p, r, u, g)
        )
        worker.signals.error.connect(lambda m, g=gen: self._on_ai_suggest_error(m, g))
        self._ai_suggest_worker = worker
        from PySide6.QtCore import QThreadPool

        QThreadPool.globalInstance().start(worker)

    def _on_ai_suggest_finished(
        self, paths: list, reasoning: str, usage: dict, generation: int
    ) -> None:
        if generation != self._ai_suggest_generation:
            return
        self._ai_suggest_worker = None
        self.instructions_panel.set_ai_suggest_busy(False)
        if paths:
            self._on_ai_selection_applied(paths)
            self._show_status(f"AI selected {len(paths)} files")
        else:
            self._show_status(f"AI found nothing. {reasoning}", True)

    def _on_ai_suggest_error(self, error_msg: str, generation: int) -> None:
        if generation != self._ai_suggest_generation:
            return
        self._ai_suggest_worker = None
        self.instructions_panel.set_ai_suggest_busy(False)
        self._show_status(error_msg, True)

    def _on_ai_selection_applied(self, paths: list) -> None:
        workspace = self.get_workspace()
        resolved = set()
        for p in paths:
            full = workspace / p if workspace and not Path(p).is_absolute() else Path(p)
            if full.exists():
                resolved.add(str(full))
        self.file_panel.set_selected_paths(resolved)

    def _collect_all_tree_paths(self, root) -> Set[str]:
        paths = set()

        def _walk(node):
            paths.add(node.path)
            for c in node.children:
                _walk(c)

        _walk(root)
        return paths

    def _cancel_ai_suggest_worker(self) -> None:
        if self._ai_suggest_worker:
            try:
                self._ai_suggest_worker.cancel()
            except Exception:
                pass
            self._ai_suggest_worker = None

    def _setup_shortcuts(self) -> None:
        from PySide6.QtGui import QShortcut, QKeySequence

        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(
            lambda: self._preset_widget.trigger_save_action()
        )
        QShortcut(QKeySequence("Ctrl+Shift+L"), self).activated.connect(
            lambda: self._preset_widget.focus_selector()
        )

    def _setup_graph_signals(self) -> None:
        if not self._graph_provider or not hasattr(self._graph_provider, "signals"):
            return
        s = self._graph_provider.signals
        s.build_started.connect(lambda: self._show_status("Building graph..."))
        s.build_finished.connect(
            lambda d, t: self._show_status(f"Graph built in {d:.2f}s")
        )

    def cleanup(self) -> None:
        if self._copy_controller:
            self._copy_controller._begin_copy_operation()
        self._cancel_ai_suggest_worker()
        self.file_panel.cleanup()
        if self._file_watcher:
            self._file_watcher.stop()

        # Consistent cleanup for tests
        if self._tree_controller:
            self._tree_controller.cleanup()
        if self._related_controller:
            self._related_controller.cleanup()
        if self._preset_controller:
            self._preset_controller.cleanup()

        self._related_controller = None  # type: ignore
        self._tree_controller = None  # type: ignore
        self._copy_controller = None  # type: ignore
        self._preset_controller = None  # type: ignore
        self._file_watcher = None  # type: ignore
        gc.collect()

    def invalidate_prompt_cache(self):
        if self._copy_controller:
            self._copy_controller._prompt_cache.invalidate_all()

    @property
    def file_tree_widget(self):
        return self.file_panel.file_tree_widget

    def get_tokenization_service(self):
        return self._tokenization_service

    def get_ignore_engine(self):
        return self._ignore_engine

    def get_clipboard_service(self):
        return self._clipboard_service

    def get_prompt_builder(self):
        return self._prompt_builder

    def get_copy_as_file(self):
        return self.actions_panel.get_copy_as_file()

    def get_full_tree(self):
        return self.actions_panel.get_full_tree()

    def get_semantic_index(self):
        return self.actions_panel.get_semantic_index()

    def get_total_tokens(self) -> int:
        """Lay tong tokens tu file panel."""
        return self.file_panel.get_total_tokens()

    # --- Preset support ---
    def set_selected_paths(self, paths: Set[str]) -> None:
        self.file_panel.set_selected_paths(paths)
