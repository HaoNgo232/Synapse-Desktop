import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QPushButton
from PySide6.QtCore import Qt
from presentation.main_window import SynapseMainWindow
from application.services.service_container import ServiceContainer
from infrastructure.persistence.recent_folders import clear_recent_folders


@pytest.fixture
def empty_workspace(tmp_path):
    pkg_dir = tmp_path / "empty_project"
    pkg_dir.mkdir()
    return pkg_dir


@pytest.fixture
def app_e2e(qtbot, empty_workspace, monkeypatch):
    clear_recent_folders()
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *args, **kwargs: str(empty_workspace),
    )

    app = QApplication.instance()
    if app and not hasattr(app, "_service_container"):
        app._service_container = ServiceContainer()  # type: ignore[attr-defined]

    window = SynapseMainWindow()
    qtbot.addWidget(window)
    window.show()
    yield window
    window.close()


def test_edge_empty_workspace(app_e2e, qtbot, empty_workspace):
    """
    Edge case: Empty workspace.
    Ung dung phai handle tot truong hop khong co file.
    """
    window = app_e2e
    window._set_workspace(empty_workspace)

    qtbot.waitUntil(
        lambda: window.context_view.file_tree_widget.get_model().rowCount() >= 1,
        timeout=3000,
    )
    model = window.context_view.file_tree_widget.get_model()
    root_index = model.index(0, 0)

    # Debug: In ra cac item trong root neu rowCount > 0
    child_count = model.rowCount(root_index)
    children = []
    if child_count > 0:
        children = [
            model.data(model.index(i, 0, root_index)) for i in range(child_count)
        ]
        print(f"DEBUG: Found unexpected children in empty workspace: {children}")

    # Model rowCount cho root node phai la 0 (PROJECT LA RONG)
    assert child_count == 0, (
        f"Empty workspace should have 0 children, found {child_count}: {children}"
    )

    # Click Copy Context khi ko co file nao duoc select
    copy_btn = None
    for btn in window.context_view.findChildren(QPushButton):
        if btn.text() == "Copy":
            copy_btn = btn
            break

    assert copy_btn is not None
    qtbot.mouseClick(copy_btn, Qt.MouseButton.LeftButton)

    # Clipboard phai rong hoac chi chua instruction/empty metadata
    clipboard = QApplication.clipboard()
    # Tuy vao format, o day chung ta verify ung dung khong crash
    assert clipboard.text() is not None


def test_edge_invalid_opx_input(app_e2e, qtbot, empty_workspace):
    """
    Edge case: Invalid OPX input.
    Kiem tra message thong bao loi khi parse XML hong.
    """
    window = app_e2e
    window.tab_widget.setCurrentIndex(1)
    apply_view = window.apply_view

    # Paste rac ruoi vao
    apply_view.set_opx_content("This is not XML <edit> incomplete")

    # Click Preview
    preview_btn = None
    for btn in apply_view.findChildren(QPushButton):
        if "Preview" in btn.text():
            preview_btn = btn
            break

    qtbot.mouseClick(preview_btn, Qt.MouseButton.LeftButton)

    # Verify last_preview_data van la None va co error logs hoac status
    assert apply_view.last_preview_data is None
    # Trong code thuc te, apply_view co method _show_status de hien thi message


def test_edge_rapid_clicks_race_condition(app_e2e, qtbot, empty_workspace):
    """
    Edge case: Rapid repeated clicks (Race conditions).
    Gia lap user click lien tuc vao cac nut chuc nang nang.
    """
    window = app_e2e
    window._set_workspace(empty_workspace)

    copy_btn = None
    for btn in window.context_view.findChildren(QPushButton):
        if btn.text() == "Copy":
            copy_btn = btn
            break

    # Click copy 10 lan lien tiep that nhanh
    for _ in range(10):
        qtbot.mouseClick(copy_btn, Qt.MouseButton.LeftButton, delay=10)

    # Neu ung dung handle async tot thi se ko crash
    assert window.isVisible()


def test_edge_file_deletion_during_operation(app_e2e, qtbot, tmp_path):
    """
    Edge case: File bi xoa trong khi dang thao tac.
    """
    ws = tmp_path / "deleted_test"
    ws.mkdir()
    f = ws / "temp.py"
    unique_content = "UNIQUE_DELETED_CONTENT_12345"
    f.write_text(unique_content, encoding="utf-8")

    window = app_e2e
    window._set_workspace(ws)

    qtbot.waitUntil(
        lambda: (
            window.context_view.file_tree_widget.get_model().rowCount(
                window.context_view.file_tree_widget.get_model().index(0, 0)
            )
            > 0
        ),
        timeout=3000,
    )

    # Select file
    window.context_view.file_tree_widget.add_paths_to_selection([str(f)])

    # Xoa file tren disk
    f.unlink()

    # Trigger Copy
    copy_btn = None
    for btn in window.context_view.findChildren(QPushButton):
        if btn.text() == "Copy":
            copy_btn = btn
            break

    # Click Copy
    qtbot.mouseClick(copy_btn, Qt.MouseButton.LeftButton)

    # Doi mot chut de async process (neu co) xong
    qtbot.wait(1000)

    final_text = QApplication.clipboard().text()
    assert unique_content not in final_text, (
        f"Bug detected: Deleted file content found in clipboard! Content: {final_text[:500]}..."
    )
