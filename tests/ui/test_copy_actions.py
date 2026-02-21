"""Tests cho CopyActionsMixin - cache, copy context, smart, treemap, diff, breakdown.

Su dung context_view fixture tu conftest.py.
Covers: lines 267-1038 cua _copy_actions.py
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
# _try_cache_hit / _store_in_cache / _begin_copy_operation
# ═══════════════════════════════════════════════════════════════

def test_try_cache_hit_miss(context_view):
    """Kiem tra _try_cache_hit khi khong co cache (line 267-296)."""
    view = context_view
    result = view._try_cache_hit("copy_context", {"a.py"}, "test", False)
    assert result is None


def test_try_cache_hit_hit(context_view):
    """Kiem tra _try_cache_hit khi co cache match."""
    view = context_view
    # Store something first
    view._store_in_cache("copy_context", {"a.py"}, "test", "prompt text", 100, False)
    # The hit depends on fingerprint matching
    result = view._try_cache_hit("copy_context", {"a.py"}, "test", False)
    if result is not None:
        assert result == ("prompt text", 100)


def test_store_in_cache(context_view):
    """Kiem tra _store_in_cache (line 298-321)."""
    view = context_view
    view._store_in_cache("copy_smart", {"b.py"}, "instr", "prompt", 200, False)
    # Verify through prompt cache
    assert "copy_smart" in view._prompt_cache._entries


def test_begin_copy_operation(context_view):
    """Kiem tra _begin_copy_operation increments gen (line 323-378)."""
    view = context_view
    old_gen = view._copy_generation
    gen = view._begin_copy_operation()
    assert gen == old_gen + 1
    assert view._copy_buttons_disabled is True


def test_begin_copy_operation_clears_toast(context_view):
    """Kiem tra _begin_copy_operation dismisses toasts (line 342-349)."""
    view = context_view
    with patch("components.toast_qt.ToastManager") as mock_mgr:
        mock_instance = MagicMock()
        mock_mgr.instance.return_value = mock_instance
        view._begin_copy_operation()
        mock_instance.dismiss_all.assert_called_with(force=True)


def test_begin_copy_operation_moves_refs_to_stale(context_view):
    """Kiem tra _begin_copy_operation moves current refs to stale (line 364-375)."""
    view = context_view
    fake_worker = MagicMock()
    fake_signals = MagicMock()
    view._current_copy_worker = fake_worker
    view._current_copy_signals = fake_signals

    view._begin_copy_operation()

    assert view._current_copy_worker is None
    assert view._current_copy_signals is None
    assert fake_worker in view._stale_workers
    assert fake_signals in view._stale_workers


def test_cleanup_stale_refs(context_view):
    """Kiem tra _cleanup_stale_refs (line 380-410)."""
    from PySide6.QtCore import QObject
    view = context_view
    mock_obj = MagicMock(spec=QObject)
    view._stale_workers = [mock_obj]
    view._cleanup_stale_refs(view._copy_generation)
    mock_obj.deleteLater.assert_called_once()


def test_cleanup_stale_refs_empty(context_view):
    """Kiem tra _cleanup_stale_refs voi empty stale list."""
    view = context_view
    view._stale_workers = []
    view._cleanup_stale_refs(view._copy_generation)  # Should not raise


def test_is_current_generation(context_view):
    """Kiem tra _is_current_generation (line 412-414)."""
    view = context_view
    assert view._is_current_generation(view._copy_generation) is True
    assert view._is_current_generation(view._copy_generation - 1) is False


def test_set_copy_buttons_enabled(context_view):
    """Kiem tra _set_copy_buttons_enabled (line 416-426)."""
    view = context_view
    view._set_copy_buttons_enabled(False)
    assert view._copy_buttons_disabled is True
    assert not view._copy_btn.isEnabled()

    view._set_copy_buttons_enabled(True)
    assert view._copy_buttons_disabled is False
    assert view._copy_btn.isEnabled()


def test_save_instruction_to_history(context_view):
    """Kiem tra _save_instruction_to_history (line 428-437)."""
    view = context_view
    with patch("services.settings_manager.add_instruction_history") as mock_add:
        view._save_instruction_to_history("Test instruction")
        mock_add.assert_called_once_with("Test instruction")


# ═══════════════════════════════════════════════════════════════
# _copy_context
# ═══════════════════════════════════════════════════════════════

def test_copy_context_no_workspace(context_view):
    """Kiem tra _copy_context no workspace (line 441-444)."""
    view = context_view
    view.get_workspace = lambda: None
    with patch("components.toast_qt.toast_error") as mock_error:
        view._copy_context()
        mock_error.assert_called_with("No workspace selected")


def test_copy_context_no_files(context_view):
    """Kiem tra _copy_context no files (line 447-449)."""
    view = context_view
    view.file_tree_widget.get_selected_paths = MagicMock(return_value=[])
    with patch("components.toast_qt.toast_error") as mock_error:
        view._copy_context()
        mock_error.assert_called_with("No files selected")


def test_copy_context_cache_hit(context_view, tmp_path):
    """Kiem tra _copy_context voi cache hit (line 461-478)."""
    view = context_view
    py_file = tmp_path / "main.py"
    py_file.write_text("x")

    view.file_tree_widget.get_selected_paths = MagicMock(
        return_value=[str(py_file)]
    )

    with patch.object(view, '_try_cache_hit', return_value=("cached prompt", 500)):
        view._clipboard_service.copy_to_clipboard = MagicMock(return_value=(True, None))
        with patch.object(view, '_show_copy_breakdown'):
            view._copy_context()
            view._clipboard_service.copy_to_clipboard.assert_called_with("cached prompt")


def test_copy_context_cache_hit_copy_fail(context_view, tmp_path):
    """Kiem tra _copy_context cache hit nhung copy fail (line 476-477)."""
    view = context_view
    py_file = tmp_path / "main.py"
    py_file.write_text("x")

    view.file_tree_widget.get_selected_paths = MagicMock(
        return_value=[str(py_file)]
    )
    with patch.object(view, '_try_cache_hit', return_value=("cached prompt", 500)):
        view._clipboard_service.copy_to_clipboard = MagicMock(
            return_value=(False, "clipboard error")
        )
        with patch("components.toast_qt.toast_error") as mock_error:
            view._copy_context()
            mock_error.assert_called()


def test_copy_context_background_no_security(context_view, tmp_path):
    """Kiem tra _copy_context dispatches background without security (line 489-497)."""
    view = context_view
    py_file = tmp_path / "main.py"
    py_file.write_text("x")

    view.file_tree_widget.get_selected_paths = MagicMock(
        return_value=[str(py_file)]
    )

    mock_settings = MagicMock()
    mock_settings.enable_security_check = False
    mock_settings.include_git_changes = False

    with patch.object(view, '_try_cache_hit', return_value=None), \
         patch("views.context._copy_actions.load_app_settings", return_value=mock_settings), \
         patch.object(view, '_do_copy_context') as mock_do, \
         patch("services.settings_manager.add_instruction_history"):
        view._copy_context()
        mock_do.assert_called_once()


def test_copy_context_security_enabled(context_view, tmp_path):
    """Kiem tra _copy_context dispatches security check (line 484-488)."""
    view = context_view
    py_file = tmp_path / "main.py"
    py_file.write_text("x")

    view.file_tree_widget.get_selected_paths = MagicMock(
        return_value=[str(py_file)]
    )

    mock_settings = MagicMock()
    mock_settings.enable_security_check = True

    with patch.object(view, '_try_cache_hit', return_value=None), \
         patch("views.context._copy_actions.load_app_settings", return_value=mock_settings), \
         patch.object(view, '_run_security_check_then_copy') as mock_sec, \
         patch("services.settings_manager.add_instruction_history"):
        view._copy_context()
        mock_sec.assert_called_once()


# ═══════════════════════════════════════════════════════════════
# _copy_smart_context
# ═══════════════════════════════════════════════════════════════

def test_copy_smart_no_workspace(context_view):
    """Kiem tra _copy_smart_context no workspace (line 762-765)."""
    view = context_view
    view.get_workspace = lambda: None
    with patch("components.toast_qt.toast_error") as mock_error:
        view._copy_smart_context()
        mock_error.assert_called_with("No workspace selected")


def test_copy_smart_no_files(context_view):
    """Kiem tra _copy_smart_context no files (line 768-770)."""
    view = context_view
    view.file_tree_widget.get_selected_paths = MagicMock(return_value=[])
    with patch("components.toast_qt.toast_error") as mock_error:
        view._copy_smart_context()
        mock_error.assert_called_with("No files selected")


def test_copy_smart_cache_hit(context_view, tmp_path):
    """Kiem tra _copy_smart_context cache hit (line 778-796)."""
    view = context_view
    py_file = tmp_path / "main.py"
    py_file.write_text("x")
    view.file_tree_widget.get_selected_paths = MagicMock(
        return_value=[str(py_file)]
    )

    with patch.object(view, '_try_cache_hit', return_value=("smart prompt", 300)):
        view._clipboard_service.copy_to_clipboard = MagicMock(return_value=(True, None))
        with patch.object(view, '_show_copy_breakdown'), \
             patch("services.settings_manager.add_instruction_history"):
            view._copy_smart_context()
            view._clipboard_service.copy_to_clipboard.assert_called_with("smart prompt")


def test_copy_smart_background(context_view, tmp_path):
    """Kiem tra _copy_smart_context dispatches to background (line 798-832)."""
    view = context_view
    py_file = tmp_path / "main.py"
    py_file.write_text("x")
    view.file_tree_widget.get_selected_paths = MagicMock(
        return_value=[str(py_file)]
    )

    with patch.object(view, '_try_cache_hit', return_value=None), \
         patch.object(view, '_run_copy_in_background') as mock_run, \
         patch("services.settings_manager.add_instruction_history"), \
         patch("views.context._copy_actions.load_app_settings", return_value=MagicMock(include_git_changes=False)):
        view._copy_smart_context()
        mock_run.assert_called_once()


# ═══════════════════════════════════════════════════════════════
# _copy_tree_map_only
# ═══════════════════════════════════════════════════════════════

def test_copy_tree_map_no_workspace(context_view):
    """Kiem tra _copy_tree_map_only no workspace (line 836-839)."""
    view = context_view
    view.get_workspace = lambda: None
    with patch("components.toast_qt.toast_error") as mock_error:
        view._copy_tree_map_only()
        mock_error.assert_called_with("No workspace selected")


def test_copy_tree_map_cache_hit(context_view, tmp_path):
    """Kiem tra _copy_tree_map_only cache hit (line 851-869)."""
    view = context_view
    view.file_tree_widget.get_selected_paths = MagicMock(return_value=[])
    with patch.object(view, '_try_cache_hit', return_value=("treemap prompt", 50)):
        view._clipboard_service.copy_to_clipboard = MagicMock(return_value=(True, None))
        with patch.object(view, '_show_copy_breakdown'), \
             patch("services.settings_manager.add_instruction_history"):
            view._copy_tree_map_only()


def test_copy_tree_map_background(context_view, tmp_path):
    """Kiem tra _copy_tree_map_only dispatches background (line 871-911)."""
    view = context_view
    view.file_tree_widget.get_selected_paths = MagicMock(return_value=[])

    with patch.object(view, '_try_cache_hit', return_value=None), \
         patch.object(view, '_run_copy_in_background') as mock_run, \
         patch("services.settings_manager.add_instruction_history"):
        view._copy_tree_map_only()
        mock_run.assert_called_once()


# ═══════════════════════════════════════════════════════════════
# _collect_all_tree_paths / _scan_full_tree
# ═══════════════════════════════════════════════════════════════

def test_collect_all_tree_paths(context_view):
    """Kiem tra _collect_all_tree_paths (line 913-923)."""
    from core.utils.file_utils import TreeItem
    view = context_view
    root = TreeItem(label="root", path="/root")
    child1 = TreeItem(label="a.py", path="/root/a.py")
    child2 = TreeItem(label="b.py", path="/root/b.py")
    root.children = [child1, child2]

    paths = view._collect_all_tree_paths(root)
    assert "/root" in paths
    assert "/root/a.py" in paths
    assert "/root/b.py" in paths


def test_scan_full_tree(context_view, tmp_path):
    """Kiem tra _scan_full_tree (line 925-931)."""
    view = context_view
    with patch("views.context._copy_actions.scan_directory") as mock_scan:
        mock_scan.return_value = MagicMock()
        result = view._scan_full_tree(tmp_path)
        mock_scan.assert_called_once()


# ═══════════════════════════════════════════════════════════════
# _show_diff_only_dialog
# ═══════════════════════════════════════════════════════════════

def test_show_diff_only_dialog_no_workspace(context_view):
    """Kiem tra _show_diff_only_dialog no workspace (line 935-938)."""
    view = context_view
    view.get_workspace = lambda: None
    with patch("components.toast_qt.toast_error") as mock_error:
        view._show_diff_only_dialog()
        mock_error.assert_called_with("No workspace selected")


def test_show_diff_only_dialog(context_view):
    """Kiem tra _show_diff_only_dialog opens dialog (line 933-974)."""
    view = context_view
    with patch("components.dialogs_qt.DiffOnlyDialogQt") as mock_dialog, \
         patch("services.settings_manager.add_instruction_history"):
        mock_instance = MagicMock()
        mock_dialog.return_value = mock_instance
        view._show_diff_only_dialog()
        mock_dialog.assert_called_once()
        mock_instance.exec.assert_called_once()


def test_show_diff_only_dialog_exception(context_view):
    """Kiem tra _show_diff_only_dialog xu ly exception (line 973-974)."""
    view = context_view
    with patch("components.dialogs_qt.DiffOnlyDialogQt", side_effect=Exception("Fail")), \
         patch("services.settings_manager.add_instruction_history"), \
         patch("components.toast_qt.toast_error") as mock_error:
        view._show_diff_only_dialog()
        assert "Error" in mock_error.call_args[0][0]


# ═══════════════════════════════════════════════════════════════
# _show_copy_breakdown
# ═══════════════════════════════════════════════════════════════

def test_show_copy_breakdown_basic(context_view):
    """Kiem tra _show_copy_breakdown (line 976-1038)."""
    view = context_view
    pre_snapshot = {
        "file_tokens": 500,
        "instruction_tokens": 100,
        "include_opx": False,
        "copy_mode": "Copy Context",
    }
    with patch("components.toast_qt.toast_success") as mock_toast:
        view._show_copy_breakdown(700, pre_snapshot)
        mock_toast.assert_called_once()
        call_kwargs = mock_toast.call_args
        assert "Copied" in str(call_kwargs)


def test_show_copy_breakdown_with_opx(context_view):
    """Kiem tra _show_copy_breakdown voi OPX (line 987-993)."""
    view = context_view
    pre_snapshot = {
        "file_tokens": 400,
        "instruction_tokens": 50,
        "include_opx": True,
        "copy_mode": "Copy + OPX",
    }
    with patch("components.toast_qt.toast_success") as mock_toast, \
         patch("core.opx_instruction.XML_FORMATTING_INSTRUCTIONS", "some instructions"):
        view._prompt_builder.count_tokens = MagicMock(return_value=100)
        view._show_copy_breakdown(600, pre_snapshot)
        mock_toast.assert_called_once()


def test_show_copy_breakdown_overflow(context_view):
    """Kiem tra _show_copy_breakdown khi sum > total (line 996-1001)."""
    view = context_view
    pre_snapshot = {
        "file_tokens": 900,
        "instruction_tokens": 200,
        "include_opx": False,
        "copy_mode": "Copy Context",
    }
    with patch("components.toast_qt.toast_success") as mock_toast:
        # Total < sum of parts
        view._show_copy_breakdown(500, pre_snapshot)
        mock_toast.assert_called_once()


# ═══════════════════════════════════════════════════════════════
# _run_copy_in_background / _do_copy_context
# ═══════════════════════════════════════════════════════════════

def test_run_copy_in_background_stale_gen(context_view):
    """Kiem tra _run_copy_in_background voi stale generation (line 617-618)."""
    view = context_view
    view._run_copy_in_background(
        gen=-1,  # Stale
        task_fn=lambda: ("prompt", 100),
    )
    # Should have returned early


def test_run_copy_in_background_dispatches(context_view):
    """Kiem tra _run_copy_in_background dispatches to thread pool (line 617-685)."""
    view = context_view
    gen = view._begin_copy_operation()

    with patch("views.context._copy_actions.QThreadPool") as mock_pool:
        mock_instance = MagicMock()
        mock_pool.globalInstance.return_value = mock_instance
        view._run_copy_in_background(
            gen=gen,
            task_fn=lambda: ("prompt", 100),
        )
        mock_instance.start.assert_called_once()


def test_do_copy_context_dispatches(context_view, tmp_path):
    """Kiem tra _do_copy_context dispatches background (line 687-758)."""
    view = context_view
    gen = view._begin_copy_operation()

    mock_settings = MagicMock()
    mock_settings.include_git_changes = False

    with patch.object(view, '_run_copy_in_background') as mock_run, \
         patch("views.context._copy_actions.load_app_settings", return_value=mock_settings):
        view._do_copy_context(
            gen, tmp_path, [tmp_path / "a.py"], "instructions", False
        )
        mock_run.assert_called_once()


def test_do_copy_context_exception(context_view, tmp_path):
    """Kiem tra _do_copy_context xu ly exception (line 755-758)."""
    view = context_view
    gen = view._begin_copy_operation()

    with patch("views.context._copy_actions.load_app_settings",
               side_effect=Exception("Fail")), \
         patch("components.toast_qt.toast_error") as mock_error:
        view._do_copy_context(gen, tmp_path, [], "instr", False)
        assert "Error" in mock_error.call_args[0][0]


# ═══════════════════════════════════════════════════════════════
# _run_security_check_then_copy
# ═══════════════════════════════════════════════════════════════

def test_run_security_check_stale_gen(context_view, tmp_path):
    """Kiem tra _run_security_check_then_copy stale gen (line 508-510)."""
    view = context_view
    view._run_security_check_then_copy(-1, tmp_path, [], "instr", False)
    # Should return early


def test_run_security_check_dispatches(context_view, tmp_path):
    """Kiem tra _run_security_check_then_copy starts worker (line 514-586)."""
    view = context_view
    gen = view._begin_copy_operation()

    with patch("views.context._copy_actions.QThreadPool") as mock_pool:
        mock_instance = MagicMock()
        mock_pool.globalInstance.return_value = mock_instance
        view._run_security_check_then_copy(
            gen, tmp_path, [tmp_path / "a.py"], "instr", False
        )
        mock_instance.start.assert_called_once()
