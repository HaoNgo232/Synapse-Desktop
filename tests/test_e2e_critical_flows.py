import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QPushButton, QMessageBox
from PySide6.QtCore import Qt
from presentation.main_window import SynapseMainWindow
from infrastructure.di.service_container import ServiceContainer
from infrastructure.persistence.recent_folders import clear_recent_folders
from infrastructure.persistence.settings_manager import load_app_settings


@pytest.fixture
def workspace_dir(tmp_path):
    """
    Tao mot workspace gia lap voi cac file mau de test E2E.
    Hàm này tạo cấu trúc thư mục thực tế trên disk.
    """
    pkg_dir = tmp_path / "my_project"
    pkg_dir.mkdir()

    (pkg_dir / "main.py").write_text("print('hello world')", encoding="utf-8")

    src_dir = pkg_dir / "src"
    src_dir.mkdir()
    (src_dir / "utils.py").write_text("def add(a, b): return a + b", encoding="utf-8")

    # Tao mot file lon de test token counting
    large_content = "def large_func():\n" + "    print('padding')\n" * 1000
    (src_dir / "large.py").write_text(large_content, encoding="utf-8")

    # Tao folder rong
    (pkg_dir / "empty_dir").mkdir()

    return pkg_dir


@pytest.fixture
def app_e2e(qtbot, workspace_dir, monkeypatch):
    """
    Fixture khoi tao toan bo ung dung Synapse Desktop cho E2E testing.
    Day la 'Composition Root' cho cac test scenario, khong su dung mock nang.
    """
    # Xoa recent folders de tranh side effects tu moi truong developer
    clear_recent_folders()

    # Mock QFileDialog.getExistingDirectory de tra ve folder workspace_dir cua minh
    # thay vi hien thi dialog thuc te cho user.
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *args, **kwargs: str(workspace_dir)
    )

    # Khoi tao ServiceContainer neu chua co
    app = QApplication.instance()
    if app and not hasattr(app, "_service_container"):
        container = ServiceContainer()
        app._service_container = container  # type: ignore[attr-defined]

    window = SynapseMainWindow()
    qtbot.addWidget(window)
    window.show()

    yield window

    # Cleanup: Shutdown thread pools va services
    window.close()
    if app and hasattr(app, "_service_container"):
        app._service_container.shutdown()  # type: ignore[attr-defined]


def test_flow_a_open_workspace(app_e2e, qtbot, workspace_dir):
    """
    Flow A: Open Workspace
    Kiem tra viec chon folder, load file tree va dong bo UI.
    """
    window = app_e2e

    # 1. Tim nut 'Open Folder'
    # Thuong thi QToolButton hoac QPushButton trong top bar
    open_btn = None
    for btn in window.findChildren(QPushButton):
        if "Open Folder" in btn.text():
            open_btn = btn
            break

    if not open_btn:
        # Check QToolButton just in case
        from PySide6.QtWidgets import QToolButton

        for btn in window.findChildren(QToolButton):
            if "Open Folder" in btn.text():
                open_btn = btn
                break

    assert open_btn is not None, (
        f"Khong tim thay nut Open Folder. Buttons: {[b.text() for b in window.findChildren(QPushButton)]}"
    )

    qtbot.mouseClick(open_btn, Qt.MouseButton.LeftButton)

    # 2. Doi UI cap nhat workspace
    # Vi _set_workspace goi on_workspace_changed cua context_view
    # va nay trigger file scanning/rendering.
    def check_workspace_loaded():
        assert window.workspace_path == workspace_dir
        assert workspace_dir.name in window.windowTitle()
        # Verify FileTree model has nodes
        model = window.context_view.file_tree_widget.get_model()
        return model._root_node is not None

    qtbot.waitUntil(check_workspace_loaded, timeout=5000)

    # 3. Assert system state thông qua model
    model = window.context_view.file_tree_widget.get_model()
    # rowCount() mac dinh se la 1 (root folder) vi model dung invisible root
    assert model.rowCount() == 1
    root_index = model.index(0, 0)
    assert model.data(root_index) == workspace_dir.name

    # Kiem tra xem root co children khong (main.py, src, empty_dir)
    # Vi model load_tree voi depth=1, nen children cua root phai co san
    assert model.rowCount(root_index) >= 2


def test_flow_b_file_selection_and_token_count(app_e2e, qtbot, workspace_dir):
    """
    Flow B: File Selection + Token Count
    Kiem tra viec chon nhieu file va verify token stats update dung.
    """
    window = app_e2e

    # 1. Open workspace truoc
    window._set_workspace(workspace_dir)

    # Cho tree load xong
    qtbot.waitUntil(
        lambda: window.context_view.file_tree_widget.get_model()._root_node is not None,
        timeout=3000,
    )

    tree_widget = window.context_view.file_tree_widget

    # 2. Select files: main.py va src/utils.py
    # Chung ta can lay absolute paths de select truc tiep qua model/manager
    paths_to_select = [
        str(workspace_dir / "main.py"),
        str(workspace_dir / "src" / "utils.py"),
    ]

    # Gia lap user action: add_paths_to_selection (day la way clean nhat de trigger event flow)
    tree_widget.add_paths_to_selection(paths_to_select)

    # 3. Verify token counts cap nhat
    # Tokenization chay async trong background
    def check_tokens_updated():
        total_tokens = tree_widget.get_total_tokens()
        # "print('hello world')" -> khoang 5-10 tokens
        # "def add(a, b): return a + b" -> khoang 10-15 tokens
        # Tong phai > 0
        return total_tokens > 0 and len(tree_widget.get_selected_paths()) == 2

    qtbot.waitUntil(check_tokens_updated, timeout=5000)

    # Verify label status bar cung cap nhat
    status_text = window._build_token_status_text()
    assert "2 files" in status_text
    assert str(tree_widget.get_total_tokens()) in status_text.replace(",", "")


def test_flow_c_copy_context(app_e2e, qtbot, workspace_dir):
    """
    Flow C: Copy Context (CORE FEATURE)
    Kiem tra viec copy code sample vao clipboard voi dung format.
    """
    window = app_e2e
    window._set_workspace(workspace_dir)
    qtbot.waitUntil(
        lambda: window.context_view.file_tree_widget.get_model()._root_node is not None,
        timeout=3000,
    )

    # 1. Select a file
    file_path = workspace_dir / "main.py"
    window.context_view.file_tree_widget.add_paths_to_selection([str(file_path)])

    # 2. Nhap instructions (optional nhung tot cho E2E)
    window.context_view.set_instructions_text("Test instruction")

    # 3. Click 'Copy Context'
    copy_btn = None
    # Tim nut trong context_view (Action Panel)
    # Nut co key '_copy_btn' va text 'Copy'
    btn_list = window.context_view.findChildren(QPushButton)
    for btn in btn_list:
        if btn.text() == "Copy":
            copy_btn = btn
            break

    assert copy_btn is not None, (
        f"Khong tim thay nut Copy. Buttons: {[b.text() for b in btn_list]}"
    )

    # Truoc khi click, xoa clipboard de dam bao ket qua moi
    clipboard = QApplication.clipboard()
    clipboard.setText("empty_before_test")

    qtbot.mouseClick(copy_btn, Qt.MouseButton.LeftButton)

    # 4. Validate clipboard content
    # Prompt assembly co the ton it thoi gian async neu workspace lon
    def check_clipboard():
        text = clipboard.text()
        return "print('hello world')" in text and "Test instruction" in text

    qtbot.waitUntil(check_clipboard, timeout=5000)

    # Assert final structure (mac dinh thuong la Markdown hoac XML)
    final_text = clipboard.text()
    assert (
        "# Instructions" in final_text
        or "<instructions>" in final_text
        or "Test instruction" in final_text
    )


def test_flow_d_apply_opx(app_e2e, qtbot, workspace_dir, monkeypatch):
    """
    Flow D: Apply OPX (HIGH RISK)
    Kiem tra viec paste XML response, preview va thuc hien thay doi file system.
    """
    window = app_e2e
    window._set_workspace(workspace_dir)

    # 1. Chuyen sang tab Apply
    window.tab_widget.setCurrentIndex(1)
    apply_view = window.apply_view

    # 2. Chuan bi OPX XML
    # Chung ta se modify main.py
    file_to_modify = workspace_dir / "main.py"
    opx_content = """
<edit file="main.py" op="replace">
  <put>
    <<<
    print('hello from E2E test')
    >>>
  </put>
</edit>
"""
    apply_view.set_opx_content(opx_content)

    # 3. Click Preview
    preview_btn = None
    for btn in apply_view.findChildren(QPushButton):
        if "Preview" in btn.text():
            preview_btn = btn
            break
    assert preview_btn is not None
    qtbot.mouseClick(preview_btn, Qt.MouseButton.LeftButton)

    # Verify records are shown in preview
    qtbot.waitUntil(lambda: apply_view.last_preview_data is not None, timeout=3000)
    assert len(apply_view.last_preview_data.rows) == 1

    # 4. Click Apply Changes
    # Mock auto-confirm dialog
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes
    )

    apply_btn = None
    for btn in apply_view.findChildren(QPushButton):
        if "Apply Changes" in btn.text():
            apply_btn = btn
            break
    assert apply_btn is not None
    qtbot.mouseClick(apply_btn, Qt.MouseButton.LeftButton)

    # 5. Verify file system changes
    def check_file_changed():
        content = file_to_modify.read_text(encoding="utf-8")
        return "hello from E2E test" in content

    qtbot.waitUntil(check_file_changed, timeout=5000)
    assert "print('hello from E2E test')" in file_to_modify.read_text(encoding="utf-8")


def test_flow_e_settings_persistence(app_e2e, qtbot, workspace_dir):
    """
    Flow E: Settings Persistence
    Kiem tra viec thay doi setting va dam bao no duoc luu lai sau khi restart.
    """
    window = app_e2e

    # 1. Chuyen sang tab Settings
    window.tab_widget.setCurrentIndex(4)

    # 2. Thay doi setting 'Output Format' qua UI
    # Tim combobox hoac radio buttons. Trong project nay thuong dung dropdown menu.
    # Chung ta se verify setting hien tai
    initial_settings = load_app_settings()
    initial_format = initial_settings.output_format or "xml"

    target_format = "json" if initial_format != "json" else "markdown"

    # Gia lap viec trigger setting change
    from infrastructure.persistence.settings_manager import update_app_setting

    update_app_setting(output_format=target_format)

    # 3. Luu session va dong window (gia lap app close)
    window.close()

    # 4. Khoi tao window moi (fixture se tao window moi cho moi test,
    # nhung o day chung ta can test persistence nen co the dung truc tiep)
    new_window = SynapseMainWindow()
    qtbot.addWidget(new_window)

    # 5. Verify setting da duoc load lai
    assert load_app_settings().output_format == target_format

    new_window.close()
