import pytest
from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtCore import Qt
from presentation.main_window import SynapseMainWindow
from infrastructure.di.service_container import ServiceContainer
from infrastructure.persistence.recent_folders import clear_recent_folders


@pytest.fixture
def multi_level_workspace(tmp_path):
    """
    Tao workspace voi nhieu loai ignore:
    - Default ignore (node_modules)
    - Root .gitignore (*.log)
    - Subdir .gitignore (*.tmp) -> DE TEST XEM CO HO TRO NESTED KHONG
    - User pattern (to be set in test)
    """
    ws = tmp_path / "multi_level_ignore"
    ws.mkdir()

    # 1. Default ignore candidate
    node_modules = ws / "node_modules"
    node_modules.mkdir()
    (node_modules / "pkg.js").write_text("console.log('ignored')", encoding="utf-8")

    # 2. Root .gitignore
    (ws / ".gitignore").write_text("*.log\nignore_me/", encoding="utf-8")
    (ws / "app.py").write_text("print('hello')", encoding="utf-8")
    (ws / "debug.log").write_text("log content", encoding="utf-8")

    ignore_me = ws / "ignore_me"
    ignore_me.mkdir()
    (ignore_me / "secret.txt").write_text("secret", encoding="utf-8")

    # 3. Subdir with nested .gitignore
    subdir = ws / "subdir"
    subdir.mkdir()
    (subdir / ".gitignore").write_text("*.tmp", encoding="utf-8")
    (subdir / "important.doc").write_text("doc", encoding="utf-8")
    (subdir / "temp.tmp").write_text("temp", encoding="utf-8")

    # 4. Visible file in nested subdir
    other = subdir / "other"
    other.mkdir()
    (other / "readme.txt").write_text("read me", encoding="utf-8")

    return ws


@pytest.fixture
def app_e2e(qtbot, multi_level_workspace, monkeypatch, tmp_path):
    # Isolated settings for each test
    fake_config = tmp_path / "fake_config"
    fake_config.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_config))

    # Reload paths module to pick up new XDG_CONFIG_HOME
    import importlib
    import presentation.config.paths
    import infrastructure.persistence.settings_manager
    import shared.types.app_settings

    importlib.reload(presentation.config.paths)
    importlib.reload(shared.types.app_settings)
    importlib.reload(infrastructure.persistence.settings_manager)

    clear_recent_folders()

    app = QApplication.instance()
    if app and not hasattr(app, "_service_container"):
        app._service_container = ServiceContainer()  # type: ignore[attr-defined]

    window = SynapseMainWindow()
    qtbot.addWidget(window)
    window.show()
    yield window
    window.close()
    if app and hasattr(app, "_service_container"):
        app._service_container.shutdown()  # type: ignore[attr-defined]


def test_ignore_engine_multi_level_visibility(app_e2e, qtbot, multi_level_workspace):
    """
    Verify Ignore Engine levels in UI:
    1. node_modules (Default) -> Hidden
    2. *.log (Root .gitignore) -> Hidden
    3. ignore_me/ (Root .gitignore) -> Hidden
    4. *.tmp (Nested .gitignore) -> CHECK IF SUPPORTED
    5. normal files -> Visible
    """
    window = app_e2e
    window._set_workspace(multi_level_workspace)

    # Wait for scan
    def get_model():
        return window.context_view.file_tree_widget.get_model()

    qtbot.waitUntil(
        lambda: get_model().rowCount(get_model().index(0, 0)) > 0, timeout=3000
    )

    model = get_model()
    root_idx = model.index(0, 0)

    # helper to find item in tree
    def find_item_recursive(parent_index, label):
        for i in range(model.rowCount(parent_index)):
            idx = model.index(i, 0, parent_index)
            curr_label = model.data(idx)
            if curr_label == label:
                return idx
            # If it's a folder, recurse if loaded
            if model.rowCount(idx) > 0:
                res = find_item_recursive(idx, label)
                if res:
                    return res
        return None

    def print_tree(parent_idx, depth=0):
        for i in range(model.rowCount(parent_idx)):
            idx = model.index(i, 0, parent_idx)
            print(
                "  " * depth
                + f"- {model.data(idx)} (col0={model.data(idx, Qt.ItemDataRole.DisplayRole)})"
            )
            if model.rowCount(idx) > 0:
                print_tree(idx, depth + 1)

    # 1. Verify visible files
    app_py_idx = find_item_recursive(root_idx, "app.py")
    if app_py_idx is None:
        print("\nDEBUG: Root children:")
        print_tree(root_idx)

    assert app_py_idx is not None, "app.py should be visible in the tree"
    assert find_item_recursive(root_idx, "subdir") is not None

    # 2. Verify hidden files (Default & Root Ignore)
    assert find_item_recursive(root_idx, "node_modules") is None
    assert find_item_recursive(root_idx, "debug.log") is None
    assert find_item_recursive(root_idx, "ignore_me") is None
    assert find_item_recursive(root_idx, ".synapse") is None, (
        ".synapse should be ignored by default"
    )

    # 3. Verify nested ignore (Subdir .gitignore)
    subdir_idx = find_item_recursive(root_idx, "subdir")
    assert subdir_idx is not None

    # Force expand subdir to load its children (lazy loading)
    # subdir_idx is a source index, need to map to proxy for the view
    proxy_idx = window.context_view.file_tree_widget._filter_proxy.mapFromSource(
        subdir_idx
    )
    window.context_view.file_tree_widget._tree_view.expand(proxy_idx)
    qtbot.waitUntil(lambda: model.rowCount(subdir_idx) > 0, timeout=3000)

    assert find_item_recursive(subdir_idx, "important.doc") is not None

    # 3. Verify nested ignore (Subdir .gitignore)
    # temp.tmp should be ignored by subdir/.gitignore
    temp_tmp_idx = find_item_recursive(subdir_idx, "temp.tmp")
    assert temp_tmp_idx is None, (
        "Bug detected: Nested ignore (*.tmp) was not respected!"
    )


def test_ignore_engine_user_patterns(app_e2e, qtbot, multi_level_workspace):
    """
    Kiem tra user-defined ignore patterns tu Settings tab.
    """
    window = app_e2e
    window._set_workspace(multi_level_workspace)

    # 1. Ban dau app.py hien thi
    def get_model():
        return window.context_view.file_tree_widget.get_model()

    qtbot.waitUntil(
        lambda: get_model().rowCount(get_model().index(0, 0)) > 0, timeout=3000
    )

    def find_node(label):
        model = get_model()
        root = model.index(0, 0)
        for i in range(model.rowCount(root)):
            idx = model.index(i, 0, root)
            if model.data(idx) == label:
                return idx
        return None

    assert find_node("app.py") is not None

    # 2. Them "app.py" vao ignore list thong qua Settings service (gia lap UI change)
    from infrastructure.persistence.settings_manager import (
        update_app_setting,
        load_app_settings,
    )

    current_settings = load_app_settings()
    current_patterns = current_settings.get_excluded_patterns_list()
    new_patterns = current_patterns + ["app.py"]
    update_app_setting(excluded_folders="\n".join(new_patterns))

    # 3. Refresh tree thông qua nút Reload trong ContextView
    from PySide6.QtWidgets import QToolButton

    reload_btn = None
    # Search for QToolButton or QPushButton
    for btn_type in (QPushButton, QToolButton):
        for btn in window.context_view.findChildren(btn_type):
            if "Reload" in btn.text():
                reload_btn = btn
                break
        if reload_btn:
            break

    assert reload_btn is not None
    qtbot.mouseClick(reload_btn, Qt.MouseButton.LeftButton)

    # 4. Verify app.py da bien mat
    qtbot.wait(1000)
    assert find_node("app.py") is None


def test_e2e_ui_exclude_deep_path(app_e2e, qtbot, multi_level_workspace):
    """
    Kiem tra tinh nang Exclude tu context menu cho file o level thap.
    Verify rang pattern duoc luu la relative path va file bien mat khoi tree.
    """
    window = app_e2e
    window._set_workspace(multi_level_workspace)

    # 1. Doi tree load
    def get_model():
        return window.context_view.file_tree_widget.get_model()

    qtbot.waitUntil(
        lambda: get_model().rowCount(get_model().index(0, 0)) > 0, timeout=3000
    )

    model = get_model()
    root_idx = model.index(0, 0)

    # Helper tim node theo label
    def find_node_recursive(parent_idx, target_label):
        for i in range(model.rowCount(parent_idx)):
            idx = model.index(i, 0, parent_idx)
            if model.data(idx) == target_label:
                return idx
            if model.rowCount(idx) > 0:
                res = find_node_recursive(idx, target_label)
                if res:
                    return res
        return None

    # 2. Mo rong cac folder de tim den file 'readme.txt' o level thap (subdir/other/readme.txt)
    subdir_idx = find_node_recursive(root_idx, "subdir")
    assert subdir_idx is not None

    # Expand subdir
    proxy_subdir = window.context_view.file_tree_widget._filter_proxy.mapFromSource(
        subdir_idx
    )
    window.context_view.file_tree_widget._tree_view.expand(proxy_subdir)
    qtbot.wait(200)  # Cho lazy load

    other_idx = find_node_recursive(subdir_idx, "other")
    assert other_idx is not None

    # Expand other
    proxy_other = window.context_view.file_tree_widget._filter_proxy.mapFromSource(
        other_idx
    )
    window.context_view.file_tree_widget._tree_view.expand(proxy_other)
    qtbot.wait(200)  # Cho lazy load

    readme_idx = find_node_recursive(other_idx, "readme.txt")
    assert readme_idx is not None

    # 3. Kich hoat action Exclude (gia lap menu trigger)
    readme_path = model.data(
        readme_idx, 260
    )  # FileTreeRoles.FILE_PATH_ROLE = UserRole + 4 = 32 + 4 = 36?
    # Actually I check FileTreeRoles: TOKEN_COUNT_ROLE = UserRole + 1 = 33?
    # UserRole is 32.
    # TOKEN_COUNT = 33, LINE_COUNT = 34, IS_SELECTED = 35, FILE_PATH = 36.

    from presentation.components.file_tree.file_tree_model import FileTreeRoles

    readme_path = model.data(readme_idx, FileTreeRoles.FILE_PATH_ROLE)

    # Goi truc tiep method _exclude_path cua widget (flow that UI dung)
    window.context_view.file_tree_widget._exclude_path(
        multi_level_workspace, readme_path, False
    )

    # 4. Wait for reload and verify
    # file_tree_widget.exclude_patterns_changed signal triggers re-scan
    qtbot.wait(1500)

    # RE-FETCH model and root because it might have been reset
    new_model = get_model()
    new_root_idx = new_model.index(0, 0)

    # readme.txt phai bien mat khoi model
    assert find_node_recursive(new_root_idx, "readme.txt") is None, (
        "Deeply nested file should be excluded"
    )

    # Verify pattern in settings
    from application.services.workspace_config import get_excluded_patterns

    patterns = get_excluded_patterns()
    # Path should be "subdir/other/readme.txt"
    assert "subdir/other/readme.txt" in patterns, (
        f"Expected subdir/other/readme.txt in {patterns}"
    )


def test_e2e_glob_exclude_deep(app_e2e, qtbot, multi_level_workspace):
    """
    Kiem tra tinh nang Exclude su dung glob patterns (**, *) tai nhieu level.
    """
    window = app_e2e

    # 1. Tao them mot so file o cac level khac nhau de test glob
    (multi_level_workspace / "level1").mkdir()
    (multi_level_workspace / "level1" / "test.testfile").write_text("content1")

    (multi_level_workspace / "subdir" / "other" / "deep.testfile").write_text(
        "content2"
    )

    window._set_workspace(multi_level_workspace)

    def get_model():
        return window.context_view.file_tree_widget.get_model()

    qtbot.waitUntil(
        lambda: get_model().rowCount(get_model().index(0, 0)) > 0, timeout=3000
    )

    model = get_model()
    root_idx = model.index(0, 0)

    # Helper tim node
    def find_node(parent_idx, target_label):
        for i in range(model.rowCount(parent_idx)):
            idx = model.index(i, 0, parent_idx)
            label = model.data(idx)
            if label == target_label:
                return idx
            if model.rowCount(idx) > 0:
                res = find_node(idx, target_label)
                if res:
                    return res
        return None

    # Verify ban dau cac file .testfile deu hien thi
    level1_idx = find_node(root_idx, "level1")
    assert level1_idx is not None, "level1 should be found in root"

    # Force load level1
    if model.canFetchMore(level1_idx):
        model.fetchMore(level1_idx)
    qtbot.waitUntil(lambda: model.rowCount(level1_idx) > 0, timeout=3000)

    assert find_node(level1_idx, "test.testfile") is not None

    # Expand to find deep.testfile
    subdir_idx = find_node(root_idx, "subdir")
    assert subdir_idx is not None
    if model.canFetchMore(subdir_idx):
        model.fetchMore(subdir_idx)
    qtbot.waitUntil(lambda: model.rowCount(subdir_idx) > 0, timeout=3000)

    other_idx = find_node(subdir_idx, "other")
    assert other_idx is not None
    if model.canFetchMore(other_idx):
        model.fetchMore(other_idx)
    qtbot.waitUntil(lambda: model.rowCount(other_idx) > 0, timeout=3000)

    assert find_node(other_idx, "deep.testfile") is not None

    # 2. Them glob pattern "**/*.testfile" vao settings
    from application.services.workspace_config import add_excluded_patterns

    add_excluded_patterns(["**/*.testfile"])

    # 3. Reload tree
    window.context_view.file_tree_widget.exclude_patterns_changed.emit()
    qtbot.wait(1000)

    # 4. Tat ca cac file .testfile phai bien mat o moi level
    new_model = get_model()
    new_root = new_model.index(0, 0)

    assert find_node(new_root, "test.testfile") is None, (
        "test.testfile should be excluded by glob"
    )
    assert find_node(new_root, "deep.testfile") is None, (
        "deep.testfile should be excluded by glob"
    )

    # Verify file khac van hien thi
    assert find_node(new_root, "app.py") is not None
