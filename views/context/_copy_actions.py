"""
Copy Actions Mixin cho ContextViewQt.

Chua CopyTaskWorker va tat ca cac copy-related methods.

ARCHITECTURE — "Generation Guard" pattern:
- Moi lan user nhan bat ky copy button nao, _copy_generation tang len.
- Worker cu VAN CHAY BINH THUONG tren thread pool (khong cancel, khong disconnect).
- Khi worker cu emit signal, main thread SO SANH generation:
  + Match → xu ly ket qua (copy to clipboard, show toast).
  + Mismatch → IGNORE hoan toan (stale result).
- Signals object duoc cleanup CHI KHI worker DA EMIT finished/error.
  Viec nay dam bao KHONG BAO GIO co use-after-free.

WHY NOT CANCEL:
- QThreadPool khong co API cancel runnable dang chay.
- threading.Event chi la flag — task_fn() (scan tree, doc files) khong check flag.
- Goi deleteLater() tren signals khi worker thread van giu reference → SEGFAULT.
- Disconnect signals khi worker dang emit → RuntimeError hoac lost signal → buttons disabled forever.

=> Giai phap don gian nhat, an toan nhat: DE WORKER CU CHAY XONG, IGNORE KET QUA.
"""

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Optional, List, Set, Callable, Dict, Tuple
from PySide6.QtCore import QObject, QRunnable, Signal, Slot, QThreadPool, Qt


from core.tree_map_generator import generate_tree_map_only
from core.utils.file_utils import scan_directory, TreeItem
from services.settings_manager import load_app_settings
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
# we control their lifetime explicitly.
# ============================================================


# ============================================================
# Prompt-level cache — avoids re-scanning, re-reading, re-generating
# when user clicks the same copy button without changing anything.
#
# Fingerprint = hash of:
#   - sorted selected file paths + their mtimes
#   - instructions text
#   - output style
#   - copy mode (context/smart/treemap/opx)
#   - relevant settings (git, security, relative paths)
#
# Cache stores ONE entry per copy mode. If fingerprint matches,
# return cached (prompt, token_count) immediately.
# ============================================================


class PromptCache:
    """Single-entry-per-mode cache for generated prompts.

    Thread-safe for reads from main thread (all cache access is on main thread
    since it happens before/instead of dispatching to background).
    """

    def __init__(self) -> None:
        # mode_key -> (fingerprint, prompt, token_count)
        self._entries: Dict[str, Tuple[str, str, int]] = {}

    def get(self, mode: str, fingerprint: str) -> Optional[Tuple[str, int]]:
        """Return (prompt, token_count) if fingerprint matches, else None."""
        entry = self._entries.get(mode)
        if entry is not None and entry[0] == fingerprint:
            return (entry[1], entry[2])
        return None

    def put(self, mode: str, fingerprint: str, prompt: str, token_count: int) -> None:
        """Store result for a copy mode."""
        self._entries[mode] = (fingerprint, prompt, token_count)

    def invalidate(self, mode: Optional[str] = None) -> None:
        """Invalidate one mode or all modes."""
        if mode is None:
            self._entries.clear()
        else:
            self._entries.pop(mode, None)

    def invalidate_all(self) -> None:
        """Clear entire cache."""
        self._entries.clear()


def _build_fingerprint(
    selected_paths: Set[str],
    instructions: str,
    output_style_id: str,
    copy_mode: str,
    include_git: bool,
    use_relative_paths: bool,
    include_xml: bool = False,
) -> str:
    """Build a fingerprint string from all inputs that affect prompt output.

    Includes file mtimes so cache auto-invalidates when files change.
    Bao gom ca rule file configuration de cache invalidate khi user thay doi rules.
    """
    h = hashlib.sha256()

    # Copy mode + settings
    h.update(f"mode={copy_mode}\n".encode())
    h.update(f"style={output_style_id}\n".encode())
    h.update(f"git={include_git}\n".encode())
    h.update(f"rel={use_relative_paths}\n".encode())
    h.update(f"xml={include_xml}\n".encode())

    # Instructions
    h.update(f"instr={instructions}\n".encode())

    # Rule file configuration — cache bust khi user thay doi rule file names
    app_settings = load_app_settings()
    rule_names = sorted(app_settings.get_rule_filenames_set())
    h.update(f"rules={','.join(rule_names)}\n".encode())

    # Sorted file paths + mtimes
    for p in sorted(selected_paths):
        try:
            mtime = Path(p).stat().st_mtime
        except OSError:
            mtime = 0.0
        h.update(f"{p}:{mtime}\n".encode())

    return h.hexdigest()


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

    IMPORTANT: setAutoDelete(False) — caller phai giu strong reference.
    Worker KHONG co cancel mechanism. Task chay den khi xong.
    Caller dung generation counter de ignore stale results.
    """

    def __init__(
        self,
        task_fn: Callable[[], Tuple[str, int]],
        signals: CopyTaskSignals,
        generation: int,
    ):
        super().__init__()
        self.task_fn = task_fn
        self.signals = signals
        self.generation = generation
        self.setAutoDelete(False)

    @Slot()
    def run(self) -> None:
        """Chay task function va emit ket qua hoac error.

        GUARANTEE: Luon emit DUNG MOT trong finished hoac error.
        Caller dua vao guarantee nay de cleanup va re-enable buttons.
        """
        try:
            prompt, token_count = self.task_fn()
            try:
                self.signals.finished.emit(prompt, token_count)
            except RuntimeError:
                pass  # Signals da bi delete (app shutting down)
        except Exception as e:
            try:
                self.signals.error.emit(str(e))
            except RuntimeError:
                pass


class SecurityCheckWorker(QRunnable):
    """Background worker for security scanning.

    Same pattern as CopyTaskWorker — no cancel, no auto-delete.
    """

    def __init__(self, paths: set[str], signals: SecurityCheckSignals, generation: int):
        super().__init__()
        self.paths = paths
        self.signals = signals
        self.generation = generation
        self.setAutoDelete(False)

    @Slot()
    def run(self) -> None:
        try:
            from core.security_check import scan_secrets_in_files_cached

            matches = scan_secrets_in_files_cached(self.paths)
            try:
                self.signals.finished.emit(matches)
            except RuntimeError:
                pass
        except Exception as e:
            try:
                self.signals.error.emit(f"Security scan error: {e}")
            except RuntimeError:
                pass


class CopyActionsMixin:
    """Mixin chua tat ca copy-related methods cho ContextViewQt.

    CRASH FIX — "Generation Guard" pattern:
    - _copy_generation tang moi lan user nhan copy button.
    - Worker cu van chay, nhung ket qua bi ignore neu generation mismatch.
    - Signals chi duoc deleteLater() SAU KHI worker da emit (trong callback).
    - KHONG BAO GIO disconnect signals hoac deleteLater() khi worker dang chay.

    Note: All instance attributes are initialized in ContextViewQt.__init__,
    not here. Class-level annotations are for documentation/type-checking only.
    """

    # References to current workers/signals — kept alive to prevent GC
    # while background work is in progress. OLD workers are NOT cleaned up
    # until their callback fires (generation mismatch → ignore + cleanup).
    _current_copy_worker: Optional["CopyTaskWorker"]
    _current_copy_signals: Optional["CopyTaskSignals"]
    _current_security_worker: Optional["SecurityCheckWorker"]
    _current_security_signals: Optional["SecurityCheckSignals"]
    _copy_generation: int  # Incremented each copy request
    _copy_buttons_disabled: bool  # Track button state to avoid redundant calls

    # Stale worker refs — workers whose generation is outdated but may still
    # be running on thread pool. We keep strong refs to prevent GC/segfault
    # until their callback fires and we can safely deleteLater().
    _stale_workers: list

    # Prompt-level cache — one entry per copy mode
    _prompt_cache: PromptCache

    def _try_cache_hit(
        self: "ContextViewQt",
        copy_mode: str,
        selected_paths: Set[str],
        instructions: str,
        include_xml: bool = False,
    ) -> Optional[Tuple[str, int]]:
        """Check prompt cache for a hit. Returns (prompt, token_count) or None.

        This is called on the main thread BEFORE starting any background work.
        If cache hits, we skip all heavy work entirely.
        """
        output_style_id = self._selected_output_style.value
        include_git = load_app_settings().include_git_changes
        use_rel = get_use_relative_paths()

        fingerprint = _build_fingerprint(
            selected_paths=selected_paths,
            instructions=instructions,
            output_style_id=output_style_id,
            copy_mode=copy_mode,
            include_git=include_git,
            use_relative_paths=use_rel,
            include_xml=include_xml,
        )

        cached = self._prompt_cache.get(copy_mode, fingerprint)
        if cached is not None:
            return cached
        return None

    def _store_in_cache(
        self: "ContextViewQt",
        copy_mode: str,
        selected_paths: Set[str],
        instructions: str,
        prompt: str,
        token_count: int,
        include_xml: bool = False,
    ) -> None:
        """Store generated prompt in cache for future hits."""
        output_style_id = self._selected_output_style.value
        include_git = load_app_settings().include_git_changes
        use_rel = get_use_relative_paths()

        fingerprint = _build_fingerprint(
            selected_paths=selected_paths,
            instructions=instructions,
            output_style_id=output_style_id,
            copy_mode=copy_mode,
            include_git=include_git,
            use_relative_paths=use_rel,
            include_xml=include_xml,
        )
        self._prompt_cache.put(copy_mode, fingerprint, prompt, token_count)

    def _begin_copy_operation(self: "ContextViewQt") -> int:
        """Prepare for a new copy operation.

        - Increment generation counter.
        - Dismiss all active toasts to prevent UI accumulation.
        - Forcefully cleanup ALL stale refs (schedule deleteLater).
        - Move current worker/signals to stale list.
        - Disable all copy buttons.

        Returns:
            The new generation number for this operation.
        """
        self._copy_generation += 1
        gen = self._copy_generation

        # 1. Dismiss all active toasts IMMEDIATELY to prevent accumulation.
        #    Use force=True to skip animation and remove synchronously.
        #    This is critical when user clicks rapidly — old toasts must go
        #    before new ones are created to avoid animation conflicts.
        try:
            from components.toast_qt import ToastManager

            manager = ToastManager.instance()
            if manager is not None:
                manager.dismiss_all(force=True)
        except Exception:
            pass

        # 2. Force cleanup ALL stale refs now — don't wait for callbacks.
        #    Workers that are still running will finish on thread pool but
        #    their signals are disconnected from meaningful work because
        #    generation mismatch will cause early return in all callbacks.
        for obj in self._stale_workers:
            if isinstance(obj, QObject):
                try:
                    obj.deleteLater()
                except RuntimeError:
                    pass
        self._stale_workers.clear()

        # 3. Move current refs to stale list for next cleanup cycle.
        if self._current_copy_worker is not None:
            self._stale_workers.append(self._current_copy_worker)
            self._current_copy_worker = None
        if self._current_copy_signals is not None:
            self._stale_workers.append(self._current_copy_signals)
            self._current_copy_signals = None
        if self._current_security_worker is not None:
            self._stale_workers.append(self._current_security_worker)
            self._current_security_worker = None
        if self._current_security_signals is not None:
            self._stale_workers.append(self._current_security_signals)
            self._current_security_signals = None

        self._set_copy_buttons_enabled(False)
        return gen

    def _cleanup_stale_refs(self: "ContextViewQt", gen: int) -> None:
        """Thread-safe cleanup of stale worker/signal objects.

        Called from EVERY callback (finished/error) for EVERY generation.
        Always cleans up immediately — no threshold waiting.

        Su dung snapshot pattern trong lock de hoan toan thread-safe:
        - Double deleteLater() tren cung QObject khi nhieu callbacks chay dong thoi
        - List modification during iteration
        """
        if not hasattr(self, "_cleanup_lock"):
            import threading

            self._cleanup_lock = threading.Lock()

        with self._cleanup_lock:
            if not self._stale_workers:
                return

            # Tao snapshot de tranh modification during iteration
            # va double deleteLater() khi nhieu callbacks goi dong thoi
            to_cleanup = self._stale_workers[:]
            self._stale_workers.clear()

        # Execute deleteLater outside of the lock
        for obj in to_cleanup:
            if isinstance(obj, QObject):
                try:
                    obj.deleteLater()
                except RuntimeError:
                    pass  # Object da bi delete roi

    def _is_current_generation(self: "ContextViewQt", gen: int) -> bool:
        """Check if gen matches current _copy_generation."""
        return gen == self._copy_generation

    def _set_copy_buttons_enabled(self: "ContextViewQt", enabled: bool) -> None:
        """Enable/disable tat ca copy buttons."""
        self._copy_buttons_disabled = not enabled
        for btn in (
            self._diff_btn,
            self._tree_map_btn,
            self._smart_btn,
            self._copy_btn,
            self._opx_btn,
        ):
            btn.setEnabled(enabled)

    def _save_instruction_to_history(self: "ContextViewQt", text: str) -> None:
        """Luu instruction vao history (thread-safe, atomic, deduplicate, max 30).

        Su dung add_instruction_history() de dam bao toan bo
        read-modify-write duoc bao ve boi lock, tranh mat du lieu
        khi user click copy nhanh lien tiep.
        """
        from services.settings_manager import add_instruction_history

        add_instruction_history(text)

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
        self._save_instruction_to_history(instructions)
        copy_mode = "copy_opx" if include_xml else "copy_context"
        selected_path_strs = {str(p) for p in file_paths}

        # === Cache fast path ===
        cached = self._try_cache_hit(
            copy_mode, selected_path_strs, instructions, include_xml
        )
        if cached is not None:
            prompt, token_count = cached
            success, err_msg = self._clipboard_service.copy_to_clipboard(prompt)
            if success:
                pre_snapshot = {
                    "file_tokens": self.file_tree_widget.get_total_tokens(),
                    "instruction_tokens": self._prompt_builder.count_tokens(
                        instructions
                    )
                    if instructions
                    else 0,
                    "include_opx": include_xml,
                    "copy_mode": "Copy + OPX" if include_xml else "Copy Context",
                }
                self._show_copy_breakdown(token_count, pre_snapshot)
            else:
                self._show_status(f"Copy failed: {err_msg}", is_error=True)
            return

        gen = self._begin_copy_operation()

        # Run security check in background to avoid UI freeze
        security_enabled = load_app_settings().enable_security_check
        if security_enabled:
            self._show_status("Checking security...")
            self._run_security_check_then_copy(
                gen, workspace, file_paths, instructions, include_xml
            )
        else:
            try:
                self._do_copy_context(
                    gen, workspace, file_paths, instructions, include_xml
                )
            except Exception as e:
                self._show_status(f"Error: {e}", is_error=True)
                if self._is_current_generation(gen):
                    self._set_copy_buttons_enabled(True)

    def _run_security_check_then_copy(
        self: "ContextViewQt",
        gen: int,
        workspace: Path,
        file_paths: List[Path],
        instructions: str,
        include_xml: bool,
    ) -> None:
        """Run security check in background, then proceed with copy if safe."""
        # Early exit if generation already stale (user clicked again before we got here)
        if not self._is_current_generation(gen):
            return

        file_path_strs = {str(p) for p in file_paths}

        signals = SecurityCheckSignals()
        worker = SecurityCheckWorker(file_path_strs, signals, generation=gen)

        self._current_security_signals = signals
        self._current_security_worker = worker

        def on_security_finished(matches: list) -> None:
            """Handle security scan results on main thread."""
            self._cleanup_stale_refs(gen)

            if not self._is_current_generation(gen):
                # Stale result — ignore completely
                return

            # Clear current refs (this worker is done)
            self._current_security_worker = None
            self._current_security_signals = None

            if matches:
                from components.dialogs_qt import SecurityDialogQt

                def _on_copy_anyway(_prompt: str) -> None:
                    if not self._is_current_generation(gen):
                        self._set_copy_buttons_enabled(True)
                        return
                    try:
                        self._do_copy_context(
                            gen, workspace, file_paths, instructions, include_xml
                        )
                    except Exception as e:
                        self._show_status(f"Error: {e}", is_error=True)
                        if self._is_current_generation(gen):
                            self._set_copy_buttons_enabled(True)

                def _on_dialog_rejected() -> None:
                    if self._is_current_generation(gen):
                        self._set_copy_buttons_enabled(True)

                dialog = SecurityDialogQt(
                    parent=self,
                    matches=matches,
                    prompt="",
                    on_copy_anyway=_on_copy_anyway,
                )
                dialog.rejected.connect(_on_dialog_rejected)
                dialog.exec()
            else:
                try:
                    self._do_copy_context(
                        gen, workspace, file_paths, instructions, include_xml
                    )
                except Exception as e:
                    self._show_status(f"Error: {e}", is_error=True)
                    if self._is_current_generation(gen):
                        self._set_copy_buttons_enabled(True)

        def on_security_error(error_msg: str) -> None:
            """Handle security scan error."""
            self._cleanup_stale_refs(gen)

            if not self._is_current_generation(gen):
                return

            self._current_security_worker = None
            self._current_security_signals = None
            self._show_status(f"Security check failed: {error_msg}", is_error=True)
            self._set_copy_buttons_enabled(True)

        signals.finished.connect(
            on_security_finished, Qt.ConnectionType.QueuedConnection
        )
        signals.error.connect(on_security_error, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(worker)

    def _run_copy_in_background(
        self: "ContextViewQt",
        gen: int,
        task_fn: Callable[[], Tuple[str, int]],
        success_template: str = "Copied! ({token_count:,} tokens)",
        pre_snapshot: Optional[dict] = None,
        cache_key: Optional[tuple] = None,
    ) -> None:
        """
        Chay mot copy task tren background thread.

        Flow:
        1. Tao CopyTaskWorker + CopyTaskSignals.
        2. Start worker tren QThreadPool.
        3. Khi worker emit finished/error:
           a. Check generation — ignore neu mismatch.
           b. Copy to clipboard + show toast neu match.
           c. Store in prompt cache neu cache_key provided.
           d. Re-enable buttons neu day la generation hien tai.

        Args:
            gen: Generation number cho operation nay.
            task_fn: Callable tra ve prompt string (chay tren background thread).
            success_template: Template cho status message, co {token_count}.
            pre_snapshot: Dict snapshot cac gia tri token truoc khi copy.
            cache_key: Optional (mode, selected_paths, instructions, include_xml)
                       for storing result in prompt cache.
        """
        # Early exit if generation already stale
        if not self._is_current_generation(gen):
            return

        self._show_status("Preparing context...")

        signals = CopyTaskSignals()
        worker = CopyTaskWorker(task_fn, signals, generation=gen)

        self._current_copy_worker = worker
        self._current_copy_signals = signals

        def on_progress(step: str, progress: int) -> None:
            if not self._is_current_generation(gen):
                return
            self._show_status(f"{step} ({progress}%)")

        def on_finished(prompt: str, token_count: int) -> None:
            """Callback khi worker hoan thanh."""
            self._cleanup_stale_refs(gen)

            if not self._is_current_generation(gen):
                # Stale — ignore result, do NOT re-enable buttons
                # (current generation's worker will handle that)
                return

            # Clear refs — this worker is done
            self._current_copy_worker = None
            self._current_copy_signals = None

            # Store in prompt cache for future fast-path hits
            if cache_key is not None:
                try:
                    mode, paths, instr, incl_xml = cache_key
                    self._store_in_cache(
                        mode, paths, instr, prompt, token_count, incl_xml
                    )
                except Exception:
                    pass  # Cache storage failure is non-critical

            success, err_msg = self._clipboard_service.copy_to_clipboard(prompt)

            if not success:
                self._show_status(f"Copy failed: {err_msg}", is_error=True)
                self._set_copy_buttons_enabled(True)
                return

            if pre_snapshot:
                self._show_copy_breakdown(token_count, pre_snapshot)
            else:
                self._show_status(success_template.format(token_count=token_count))

            self._set_copy_buttons_enabled(True)

        def on_error(error_msg: str) -> None:
            """Callback khi worker gap loi."""
            self._cleanup_stale_refs(gen)

            if not self._is_current_generation(gen):
                return

            self._current_copy_worker = None
            self._current_copy_signals = None
            self._show_status(f"Error: {error_msg}", is_error=True)
            self._set_copy_buttons_enabled(True)

        signals.progress.connect(on_progress, Qt.ConnectionType.QueuedConnection)
        signals.finished.connect(on_finished, Qt.ConnectionType.QueuedConnection)
        signals.error.connect(on_error, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(worker)

    def _do_copy_context(
        self: "ContextViewQt",
        gen: int,
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
            selected_path_strs = {str(p) for p in file_paths}
            use_rel = get_use_relative_paths()
            output_style = self._selected_output_style
            include_git = load_app_settings().include_git_changes

            copy_mode = "copy_opx" if include_xml else "copy_context"
            # Capture for cache storage in on_finished callback
            _cache_selected = set(selected_path_strs)
            _cache_instructions = instructions
            _cache_include_xml = include_xml
            _cache_mode = copy_mode

            def task() -> Tuple[str, int]:
                """Heavy work - chay tren background thread."""
                tree_item = self._scan_full_tree(workspace)
                format_str = "xml"
                if output_style == OutputStyle.JSON:
                    format_str = "json"
                elif output_style == OutputStyle.PLAIN:
                    format_str = "plain"

                return self._prompt_builder.build_prompt(
                    file_paths=[Path(p) for p in selected_path_strs],
                    workspace=workspace,
                    instructions=instructions,
                    output_format=format_str,
                    include_git_changes=include_git,
                    use_relative_paths=use_rel,
                    tree_item=tree_item,
                    selected_paths=selected_path_strs,
                )

            pre_snapshot = {
                "file_tokens": self.file_tree_widget.get_total_tokens(),
                "instruction_tokens": self._prompt_builder.count_tokens(instructions)
                if instructions
                else 0,
                "include_opx": include_xml,
                "copy_mode": "Copy + OPX" if include_xml else "Copy Context",
            }

            self._run_copy_in_background(
                gen,
                task,
                "Copied! ({token_count:,} tokens)",
                pre_snapshot=pre_snapshot,
                cache_key=(
                    _cache_mode,
                    _cache_selected,
                    _cache_instructions,
                    _cache_include_xml,
                ),
            )
        except Exception as e:
            self._show_status(f"Error preparing copy: {e}", is_error=True)
            if self._is_current_generation(gen):
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

        file_paths = [Path(p) for p in selected_files if Path(p).is_file()]
        selected_path_strs = {str(p) for p in file_paths}
        instructions = self._instructions_field.toPlainText()
        self._save_instruction_to_history(instructions)

        # === Cache fast path ===
        cached = self._try_cache_hit("copy_smart", selected_path_strs, instructions)
        if cached is not None:
            prompt, token_count = cached
            success, err_msg = self._clipboard_service.copy_to_clipboard(prompt)
            if success:
                pre_snapshot = {
                    "file_tokens": self.file_tree_widget.get_total_tokens(),
                    "instruction_tokens": self._prompt_builder.count_tokens(
                        instructions
                    )
                    if instructions
                    else 0,
                    "include_opx": False,
                    "copy_mode": "Copy Smart",
                }
                self._show_copy_breakdown(token_count, pre_snapshot)
            else:
                self._show_status(f"Copy failed: {err_msg}", is_error=True)
            return

        gen = self._begin_copy_operation()
        use_rel = get_use_relative_paths()
        include_git = load_app_settings().include_git_changes

        def task() -> Tuple[str, int]:
            """Heavy work - chay tren background thread."""
            assert workspace is not None
            tree_item = self._scan_full_tree(workspace)
            return self._prompt_builder.build_prompt(
                file_paths=[Path(p) for p in selected_path_strs],
                workspace=workspace,
                instructions=instructions,
                output_format="smart",
                include_git_changes=include_git,
                use_relative_paths=use_rel,
                tree_item=tree_item,
                selected_paths=selected_path_strs,
            )

        pre_snapshot = {
            "file_tokens": self.file_tree_widget.get_total_tokens(),
            "instruction_tokens": self._prompt_builder.count_tokens(instructions)
            if instructions
            else 0,
            "include_opx": False,
            "copy_mode": "Copy Smart",
        }

        self._run_copy_in_background(
            gen,
            task,
            "Smart context copied! ({token_count:,} tokens)",
            pre_snapshot=pre_snapshot,
            cache_key=("copy_smart", selected_path_strs, instructions, False),
        )

    def _copy_tree_map_only(self: "ContextViewQt") -> None:
        """Copy tree map only tren background thread."""
        workspace = self.get_workspace()
        if not workspace:
            self._show_status("No workspace selected", is_error=True)
            return

        selected_files = self.file_tree_widget.get_selected_paths()
        selected_strs = set(selected_files) if selected_files else set()
        instructions = (
            self._instructions_field.toPlainText()
            if hasattr(self, "_instructions_field")
            else ""
        )
        self._save_instruction_to_history(instructions)

        # === Cache fast path ===
        cached = self._try_cache_hit("copy_treemap", selected_strs, instructions)
        if cached is not None:
            prompt, token_count = cached
            success, err_msg = self._clipboard_service.copy_to_clipboard(prompt)
            if success:
                pre_snapshot = {
                    "file_tokens": 0,
                    "instruction_tokens": self._prompt_builder.count_tokens(
                        instructions
                    )
                    if instructions
                    else 0,
                    "include_opx": False,
                    "copy_mode": "Copy Tree Map",
                }
                self._show_copy_breakdown(token_count, pre_snapshot)
            else:
                self._show_status(f"Copy failed: {err_msg}", is_error=True)
            return

        gen = self._begin_copy_operation()
        use_rel = get_use_relative_paths()

        def task() -> Tuple[str, int]:
            """Heavy work - chay tren background thread."""
            assert workspace is not None
            tree_item = self._scan_full_tree(workspace)
            if not tree_item:
                raise ValueError("No file tree loaded")

            valid_paths = self._collect_all_tree_paths(tree_item)
            paths = selected_strs & valid_paths if selected_strs else valid_paths

            prompt = generate_tree_map_only(
                tree_item,
                paths,
                instructions,
                workspace_root=workspace,
                use_relative_paths=use_rel,
            )
            # Thong nhat token counting path qua PromptBuildService
            # de dam bao cung tokenizer instance nhu cac copy operations khac
            count = self._prompt_builder.count_tokens(prompt)
            return prompt, count

        pre_snapshot = {
            "file_tokens": 0,
            "instruction_tokens": self._prompt_builder.count_tokens(instructions)
            if instructions
            else 0,
            "include_opx": False,
            "copy_mode": "Copy Tree Map",
        }

        self._run_copy_in_background(
            gen,
            task,
            "Tree map copied! ({token_count:,} tokens)",
            pre_snapshot=pre_snapshot,
            cache_key=("copy_treemap", selected_strs, instructions, False),
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

        # Diff dialog manages its own copy — just increment generation
        # to invalidate any pending workers from other modes.
        self._begin_copy_operation()
        # Re-enable buttons immediately since dialog handles its own flow
        self._set_copy_buttons_enabled(True)

        try:
            from components.dialogs_qt import DiffOnlyDialogQt
            from core.utils.git_utils import build_diff_only_prompt

            instructions = self._instructions_field.toPlainText()
            self._save_instruction_to_history(instructions)

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
                instructions=instructions,
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

        file_t = pre_snapshot.get("file_tokens", 0)
        instr_t = pre_snapshot.get("instruction_tokens", 0)
        include_opx = pre_snapshot.get("include_opx", False)

        opx_t = 0
        if include_opx:
            try:
                from core.opx_instruction import XML_FORMATTING_INSTRUCTIONS

                opx_t = self._prompt_builder.count_tokens(XML_FORMATTING_INSTRUCTIONS)
            except ImportError:
                opx_t = 0

        sum_parts = file_t + instr_t + opx_t
        if sum_parts > total_tokens:
            ratio = total_tokens / sum_parts if sum_parts > 0 else 1.0
            file_t = int(file_t * ratio)
            instr_t = int(instr_t * ratio)
            opx_t = int(opx_t * ratio)
            structure_t = 0
        else:
            structure_t = max(0, total_tokens - file_t - instr_t - opx_t)

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
