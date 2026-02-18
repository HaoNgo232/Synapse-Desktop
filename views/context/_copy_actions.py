"""
Copy Actions Mixin cho ContextViewQt.

Chua CopyTaskWorker va tat ca cac copy-related methods.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Optional, List, Set, Callable
from PySide6.QtCore import QObject, QRunnable, Signal, Slot, QThreadPool, Qt

from core.token_counter import count_tokens
from core.prompt_generator import (
    generate_file_map,
    generate_file_contents_xml,
    generate_file_contents_json,
    generate_file_contents_plain,
    generate_prompt,
    generate_smart_context,
    build_smart_prompt,
)
from core.tree_map_generator import generate_tree_map_only
from core.utils.git_utils import get_git_diffs, get_git_logs
from core.utils.file_utils import scan_directory, TreeItem
from core.security_check import scan_secrets_in_files_cached
from services.clipboard_utils import copy_to_clipboard
from services.settings_manager import get_setting
from services.workspace_config import (
    get_excluded_patterns,
    get_use_gitignore,
    get_use_relative_paths,
)
from config.output_format import OutputStyle

if TYPE_CHECKING:
    from views.context_view_qt import ContextViewQt


# ============================================================
# Signal classes at MODULE LEVEL — not nested inside QRunnable.
#
# WHY: QRunnable with setAutoDelete(True) is destroyed by Qt's
# C++ thread pool right after run() returns. If the Signals
# QObject is a member of that QRunnable, it gets destroyed too.
# But the main-thread event loop may still be delivering the
# queued signal → reads freed memory → SEGFAULT.
#
# By defining Signals at module level and passing them separately,
# we control their lifetime explicitly via deleteLater().
# ============================================================


class CopyTaskSignals(QObject):
    """Signals for CopyTaskWorker — must outlive the QRunnable."""

    finished = Signal(str, int)  # (prompt_text, token_count)
    error = Signal(str)
    progress = Signal(str, int)  # (step_description, percentage)


class SecurityCheckSignals(QObject):
    """Signals for SecurityCheckWorker — must outlive the QRunnable."""

    finished = Signal(list)  # List[SecretMatch]
    error = Signal(str)


class CopyTaskWorker(QRunnable):
    """
    Background worker cho cac copy operations nang.

    SAFETY: setAutoDelete(False) to prevent Qt C++ from destroying
    this object while signals are still queued. Caller must call
    safe_cleanup() after handling signals.
    """

    def __init__(self, task_fn: Callable[[], str], signals: CopyTaskSignals):
        super().__init__()
        self.task_fn = task_fn
        self.signals = signals
        # CRITICAL: Do NOT auto-delete. Qt C++ deletes on the pool thread,
        # but our signals may still be queued for the main thread.
        self.setAutoDelete(False)

    @Slot()
    def run(self) -> None:
        """Chay task function va emit ket qua hoac error.

        IMPORTANT: Must ALWAYS emit either finished or error signal.
        If neither is emitted, copy buttons stay disabled forever.
        """
        try:
            prompt = self.task_fn()
            from core.token_counter import count_tokens as _count

            token_count = _count(prompt)
            self.signals.finished.emit(prompt, token_count)
        except Exception as e:
            self.signals.error.emit(str(e))


class SecurityCheckWorker(QRunnable):
    """Background worker for security scanning.

    SAFETY: Same pattern as CopyTaskWorker — no auto-delete.
    """

    def __init__(self, paths: set[str], signals: SecurityCheckSignals):
        super().__init__()
        self.paths = paths
        self.signals = signals
        self.setAutoDelete(False)

    @Slot()
    def run(self) -> None:
        try:
            from core.security_check import scan_secrets_in_files_cached

            matches = scan_secrets_in_files_cached(self.paths)
            self.signals.finished.emit(matches)
        except Exception as e:
            self.signals.error.emit(f"Security scan error: {e}")


class CopyActionsMixin:
    """Mixin chua tat ca copy-related methods cho ContextViewQt.

    Note: All instance attributes are initialized in ContextViewQt.__init__,
    not here. Class-level annotations are for documentation/type-checking only.
    """

    _current_copy_worker: Optional["CopyTaskWorker"]
    _current_copy_signals: Optional["CopyTaskSignals"]
    _current_security_worker: Optional["SecurityCheckWorker"]
    _current_security_signals: Optional["SecurityCheckSignals"]

    def _copy_context(self: "ContextViewQt", include_xml: bool = False) -> None:
        """Copy context with selected format."""
        workspace = self.get_workspace()
        if not workspace:
            self._show_status("No workspace selected", is_error=True)
            return

        selected_files = self.file_tree_widget.get_selected_paths()
        if not selected_files:
            self._show_status("No files selected", is_error=True)
            return

        file_paths = [Path(p) for p in selected_files if Path(p).is_file()]
        instructions = self._instructions_field.toPlainText()

        # Run security check in background to avoid UI freeze
        security_enabled = get_setting("enable_security_check", True)
        if security_enabled:
            # Disable buttons and show status BEFORE starting worker
            self._set_copy_buttons_enabled(False)
            self._show_status("Checking security...")
            self._run_security_check_then_copy(
                workspace, file_paths, instructions, include_xml
            )
        else:
            # No security check - proceed directly
            try:
                self._do_copy_context(workspace, file_paths, instructions, include_xml)
            except Exception as e:
                self._show_status(f"Error: {e}", is_error=True)
                self._set_copy_buttons_enabled(True)

    def _run_security_check_then_copy(
        self: "ContextViewQt",
        workspace: Path,
        file_paths: List[Path],
        instructions: str,
        include_xml: bool,
    ) -> None:
        """Run security check in background, then proceed with copy if safe.

        IMPORTANT: Must re-enable copy buttons in ALL code paths.
        """
        file_path_strs = {str(p) for p in file_paths}

        # Create signals first — we control their lifetime
        signals = SecurityCheckSignals()
        worker = SecurityCheckWorker(file_path_strs, signals)

        # Keep strong references to prevent GC
        self._current_security_signals = signals
        self._current_security_worker = worker

        def on_security_finished(matches: list) -> None:
            """Handle security scan results on main thread."""
            # Clean up worker refs
            self._current_security_worker = None
            self._current_security_signals = None

            if matches:
                # Found secrets - show dialog
                from components.dialogs_qt import SecurityDialogQt

                def _on_copy_anyway(_prompt: str) -> None:
                    """User chose to copy despite secrets."""
                    try:
                        self._do_copy_context(
                            workspace, file_paths, instructions, include_xml
                        )
                    except Exception as e:
                        self._show_status(f"Error: {e}", is_error=True)
                        self._set_copy_buttons_enabled(True)

                dialog = SecurityDialogQt(
                    parent=self,
                    matches=matches,
                    prompt="",
                    on_copy_anyway=_on_copy_anyway,
                )
                # Re-enable buttons when user cancels/closes dialog
                dialog.rejected.connect(
                    lambda: self._set_copy_buttons_enabled(True)
                )
                dialog.exec()
            else:
                # No secrets found - proceed with copy
                try:
                    self._do_copy_context(
                        workspace, file_paths, instructions, include_xml
                    )
                except Exception as e:
                    self._show_status(f"Error: {e}", is_error=True)
                    self._set_copy_buttons_enabled(True)

        def on_security_error(error_msg: str) -> None:
            """Handle security scan error."""
            self._current_security_worker = None
            self._current_security_signals = None
            self._show_status(f"Security check failed: {error_msg}", is_error=True)
            self._set_copy_buttons_enabled(True)

        # Use QueuedConnection explicitly — signal emitted on worker thread,
        # slot executed on main thread via event loop
        signals.finished.connect(
            on_security_finished, Qt.ConnectionType.QueuedConnection
        )
        signals.error.connect(
            on_security_error, Qt.ConnectionType.QueuedConnection
        )
        QThreadPool.globalInstance().start(worker)

    def _set_copy_buttons_enabled(self: "ContextViewQt", enabled: bool) -> None:
        """
        Enable/disable tat ca copy buttons.

        Goi khi bat dau/ket thuc copy operation de tranh user
        nhan nhieu lan khi dang xu ly.
        """
        for btn in (
            self._diff_btn,
            self._tree_map_btn,
            self._smart_btn,
            self._copy_btn,
            self._opx_btn,
        ):
            btn.setEnabled(enabled)

    def _run_copy_in_background(
        self: "ContextViewQt",
        task_fn: Callable[[], str],
        success_template: str = "Copied! ({token_count:,} tokens)",
        pre_snapshot: Optional[dict] = None,
    ) -> None:
        """
        Chay mot copy task tren background thread.

        Flow:
        1. Disable tat ca copy buttons
        2. Hien thi "Dang chuan bi..."
        3. Start CopyTaskWorker tren QThreadPool
        4. Khi xong: copy to clipboard, show breakdown (neu co snapshot), enable buttons

        IMPORTANT: Buttons MUST be re-enabled in ALL exit paths (finished + error).

        Args:
            task_fn: Callable tra ve prompt string (chay tren background thread)
            success_template: Template cho status message, co {token_count}
            pre_snapshot: Dict snapshot cac gia tri token truoc khi copy.
        """
        self._set_copy_buttons_enabled(False)
        self._show_status("Preparing context...")

        # Create signals object — we own its lifetime
        signals = CopyTaskSignals()
        worker = CopyTaskWorker(task_fn, signals)

        # Keep strong references to prevent GC
        self._current_copy_worker = worker
        self._current_copy_signals = signals

        def on_progress(step: str, progress: int) -> None:
            """Callback khi worker report progress."""
            self._show_status(f"{step} ({progress}%)")

        def on_finished(prompt: str, token_count: int) -> None:
            """Callback khi worker hoan thanh."""
            # Clean up worker refs
            self._current_copy_worker = None
            self._current_copy_signals = None

            success, msg = copy_to_clipboard(prompt)

            if not success:
                self._show_status(f"Copy failed: {msg}", is_error=True)
                self._set_copy_buttons_enabled(True)
                return

            if pre_snapshot:
                self._show_copy_breakdown(token_count, pre_snapshot)
            else:
                self._show_status(success_template.format(token_count=token_count))

            self._set_copy_buttons_enabled(True)

        def on_error(error_msg: str) -> None:
            """Callback khi worker gap loi."""
            self._current_copy_worker = None
            self._current_copy_signals = None
            self._show_status(f"Error: {error_msg}", is_error=True)
            self._set_copy_buttons_enabled(True)

        # Use QueuedConnection explicitly for cross-thread safety
        signals.progress.connect(on_progress, Qt.ConnectionType.QueuedConnection)
        signals.finished.connect(on_finished, Qt.ConnectionType.QueuedConnection)
        signals.error.connect(on_error, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(worker)

    def _do_copy_context(
        self: "ContextViewQt",
        workspace: Path,
        file_paths: List[Path],
        instructions: str,
        include_xml: bool,
    ) -> None:
        """
        Execute copy context tren background thread.

        Heavy work (scan tree, doc files, generate prompt, count tokens)
        chay background de UI khong bi freeze.
        """
        try:
            # Snapshot tat ca inputs truoc khi chuyen sang background thread
            selected_path_strs = {str(p) for p in file_paths}
            use_rel = get_use_relative_paths()
            output_style = self._selected_output_style
            include_git = get_setting("include_git_changes", True)

            def task() -> str:
                """Heavy work - chay tren background thread."""
                # Step 1: Scan tree
                tree_item = self._scan_full_tree(workspace)
                file_map = (
                    generate_file_map(
                        tree_item,
                        selected_path_strs,
                        workspace_root=workspace,
                        use_relative_paths=use_rel,
                    )
                    if tree_item
                    else ""
                )

                # Step 2: Read files
                if output_style == OutputStyle.XML:
                    file_contents = generate_file_contents_xml(
                        selected_path_strs,
                        workspace_root=workspace,
                        use_relative_paths=use_rel,
                    )
                elif output_style == OutputStyle.JSON:
                    file_contents = generate_file_contents_json(
                        selected_path_strs,
                        workspace_root=workspace,
                        use_relative_paths=use_rel,
                    )
                else:
                    file_contents = generate_file_contents_plain(
                        selected_path_strs,
                        workspace_root=workspace,
                        use_relative_paths=use_rel,
                    )

                # Step 3: Git operations
                git_diffs = None
                git_logs = None
                if include_git:
                    git_diffs = get_git_diffs(workspace)
                    git_logs = get_git_logs(workspace, max_commits=5)

                # Step 4: Generate prompt
                return generate_prompt(
                    file_map=file_map,
                    file_contents=file_contents,
                    user_instructions=instructions,
                    output_style=output_style,
                    include_xml_formatting=include_xml,
                    git_diffs=git_diffs,
                    git_logs=git_logs,
                )

            # Snapshot token values truoc khi background task chay
            pre_snapshot = {
                "file_tokens": self.file_tree_widget.get_total_tokens(),
                "instruction_tokens": count_tokens(instructions) if instructions else 0,
                "include_opx": include_xml,
                "copy_mode": "Copy + OPX" if include_xml else "Copy Context",
            }

            self._run_copy_in_background(
                task,
                "Copied! ({token_count:,} tokens)",
                pre_snapshot=pre_snapshot,
            )
        except Exception as e:
            self._show_status(f"Error preparing copy: {e}", is_error=True)
            self._set_copy_buttons_enabled(True)

    def _copy_smart_context(self: "ContextViewQt") -> None:
        """Copy smart context (code structure only) tren background thread."""
        workspace = self.get_workspace()
        if not workspace:
            self._show_status("No workspace selected", is_error=True)
            return

        selected_files = self.file_tree_widget.get_selected_paths()
        if not selected_files:
            self._show_status("No files selected", is_error=True)
            return

        # Snapshot inputs truoc khi chuyen sang background
        file_paths = [Path(p) for p in selected_files if Path(p).is_file()]
        selected_path_strs = {str(p) for p in file_paths}
        instructions = self._instructions_field.toPlainText()
        use_rel = get_use_relative_paths()
        include_git = get_setting("include_git_changes", True)

        def task() -> str:
            """Heavy work - chay tren background thread."""
            assert workspace is not None
            tree_item = self._scan_full_tree(workspace)
            file_map = (
                generate_file_map(
                    tree_item,
                    selected_path_strs,
                    workspace_root=workspace,
                    use_relative_paths=use_rel,
                )
                if tree_item
                else ""
            )
            smart_contents = generate_smart_context(
                selected_paths=selected_path_strs,
                include_relationships=True,
                workspace_root=workspace,
                use_relative_paths=use_rel,
            )
            git_diffs = None
            git_logs = None
            if include_git:
                git_diffs = get_git_diffs(workspace)
                git_logs = get_git_logs(workspace, max_commits=5)
            return build_smart_prompt(
                smart_contents=smart_contents,
                file_map=file_map,
                user_instructions=instructions,
                git_diffs=git_diffs,
                git_logs=git_logs,
            )

        pre_snapshot = {
            "file_tokens": self.file_tree_widget.get_total_tokens(),
            "instruction_tokens": count_tokens(instructions) if instructions else 0,
            "include_opx": False,
            "copy_mode": "Copy Smart",
        }

        self._run_copy_in_background(
            task,
            "Smart context copied! ({token_count:,} tokens)",
            pre_snapshot=pre_snapshot,
        )

    def _copy_tree_map_only(self: "ContextViewQt") -> None:
        """Copy tree map only tren background thread."""
        workspace = self.get_workspace()
        if not workspace:
            self._show_status("No workspace selected", is_error=True)
            return

        # Snapshot inputs
        selected_files = self.file_tree_widget.get_selected_paths()
        selected_strs = set(selected_files) if selected_files else set()
        instructions = (
            self._instructions_field.toPlainText()
            if hasattr(self, "_instructions_field")
            else ""
        )
        use_rel = get_use_relative_paths()

        def task() -> str:
            """Heavy work - chay tren background thread."""
            assert workspace is not None
            tree_item = self._scan_full_tree(workspace)
            if not tree_item:
                raise ValueError("No file tree loaded")

            valid_paths = self._collect_all_tree_paths(tree_item)
            paths = selected_strs & valid_paths if selected_strs else valid_paths

            return generate_tree_map_only(
                tree_item,
                paths,
                instructions,
                workspace_root=workspace,
                use_relative_paths=use_rel,
            )

        pre_snapshot = {
            "file_tokens": 0,
            "instruction_tokens": count_tokens(instructions) if instructions else 0,
            "include_opx": False,
            "copy_mode": "Copy Tree Map",
        }

        self._run_copy_in_background(
            task,
            "Tree map copied! ({token_count:,} tokens)",
            pre_snapshot=pre_snapshot,
        )

    def _collect_all_tree_paths(self: "ContextViewQt", root: TreeItem) -> Set[str]:
        """Collect all node paths from a TreeItem tree."""
        paths: Set[str] = set()

        def _walk(node: TreeItem) -> None:
            paths.add(node.path)
            for child in node.children:
                _walk(child)

        _walk(root)
        return paths

    def _scan_full_tree(self: "ContextViewQt", workspace: Path) -> TreeItem:
        """Scan full workspace tree with current exclude settings."""
        return scan_directory(
            workspace,
            excluded_patterns=get_excluded_patterns(),
            use_gitignore=get_use_gitignore(),
        )

    def _show_diff_only_dialog(self: "ContextViewQt") -> None:
        """Show diff only dialog."""
        workspace = self.get_workspace()
        if not workspace:
            self._show_status("No workspace selected", is_error=True)
            return

        try:
            from components.dialogs_qt import DiffOnlyDialogQt
            from core.utils.git_utils import build_diff_only_prompt

            def _build_diff_prompt(
                diff_result, instructions, include_content, include_tree
            ):
                return build_diff_only_prompt(
                    diff_result,
                    instructions,
                    include_content,
                    include_tree,
                    workspace_root=workspace,
                    use_relative_paths=get_use_relative_paths(),
                )

            dialog = DiffOnlyDialogQt(
                parent=self,
                workspace=workspace,
                build_prompt_callback=_build_diff_prompt,
                instructions=self._instructions_field.toPlainText(),
                on_success=lambda msg: self._show_status(msg),
            )
            dialog.exec()
        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)

    def _show_copy_breakdown(
        self: "ContextViewQt", total_tokens: int, pre_snapshot: dict
    ) -> None:
        """Hien thi token breakdown sau khi copy qua Global Toast System."""
        from components.toast_qt import toast_success

        # Extract snapshot values
        file_t = pre_snapshot.get("file_tokens", 0)
        instr_t = pre_snapshot.get("instruction_tokens", 0)
        include_opx = pre_snapshot.get("include_opx", False)

        # Uoc luong OPX tokens tu constant
        opx_t = 0
        if include_opx:
            try:
                from core.opx_instruction import XML_FORMATTING_INSTRUCTIONS

                opx_t = count_tokens(XML_FORMATTING_INSTRUCTIONS)
            except ImportError:
                opx_t = 0

        # Tinh overhead (structure tokens)
        sum_parts = file_t + instr_t + opx_t
        if sum_parts > total_tokens:
            ratio = total_tokens / sum_parts if sum_parts > 0 else 1.0
            file_t = int(file_t * ratio)
            instr_t = int(instr_t * ratio)
            opx_t = int(opx_t * ratio)
            structure_t = 0
        else:
            structure_t = max(0, total_tokens - file_t - instr_t - opx_t)

        # Build breakdown message
        parts = []
        if file_t > 0:
            parts.append(f"{file_t:,} content")
        if instr_t > 0:
            parts.append(f"{instr_t:,} instructions")
        if opx_t > 0:
            parts.append(f"{opx_t:,} OPX")
        if structure_t > 0:
            parts.append(f"{structure_t:,} system prompt")

        breakdown_text = " + ".join(parts) if parts else ""

        # Build tooltip chi tiet
        tooltip_lines = [
            f"Total: {total_tokens:,} tokens",
            "",
            f"File content: {file_t:,} tokens",
            f"Instructions: {instr_t:,} tokens",
        ]
        if opx_t > 0:
            tooltip_lines.append(f"OPX instructions: {opx_t:,} tokens")
        tooltip_lines.extend(
            [
                f"Prompt structure: {structure_t:,} tokens",
                "  (includes: tree map, git diff/log, XML tags)",
            ]
        )

        toast_success(
            message=breakdown_text or f"{total_tokens:,} tokens",
            title=f"Copied! {total_tokens:,} tokens",
            tooltip="\n".join(tooltip_lines),
            duration=8000,
        )