import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt
from presentation.views.context.context_view_qt import ContextViewQt


@pytest.fixture
def workspace_path(tmp_path):
    # Tao dummy workspace
    workspace = tmp_path / "test_project"
    workspace.mkdir()
    (workspace / "a.py").write_text("def a(): pass")
    (workspace / "b.py").write_text("import a; def b(): a.a()")
    return workspace


@pytest.fixture
def context_view(qtbot, workspace_path):
    # Mocking dependencies
    get_workspace = MagicMock(return_value=workspace_path)
    view = ContextViewQt(get_workspace=get_workspace)
    qtbot.addWidget(view)

    # Load tree
    view.on_workspace_changed(workspace_path)

    # Select files
    view.file_tree_widget.set_selected_paths(
        {str(workspace_path / "a.py"), str(workspace_path / "b.py")}
    )

    return view


def test_compress_output_with_semantic_toggle(qtbot, context_view, workspace_path):
    view = context_view

    # 1. Bat Semantic Index
    qtbot.mouseClick(view._semantic_index_toggle, Qt.MouseButton.LeftButton)
    assert view._semantic_index_toggle.isChecked() is True

    # 2. Mock PromptBuildService.build_prompt_full de xem arguments truyen vao
    with patch.object(
        view._prompt_builder,
        "build_prompt_full",
        wraps=view._prompt_builder.build_prompt_full,
    ):
        # Click Compress
        qtbot.mouseClick(view._smart_btn, Qt.MouseButton.LeftButton)

        # Wait for background task (mac du o day dang chay dong bo do QThreadPool?)
        # Thuc te CopyTaskWorker chay tren globalInstance pool.
        # Chung ta can wait hoac mock worker.

        # De don gian, kiem tra ngay Argument call vao builder tu controller
        # vi controller goi ngay lap tuc truoc khi day vao worker.

    # Wait mot chut de worker chay neu can
    # qtbot.wait(1000)

    # Kiem tra xem build_prompt_full duoc goi voi semantic_index=True
    # Wait, controller goi builder trong task() function tren background thread.

    # Mock task_fn in _run_copy_in_background to capture what it returns
    pass


def test_semantic_index_affects_compressed_output(qtbot, context_view, workspace_path):
    view = context_view

    # Chung ta se mock build_prompt cua prompt_builder de xem semantic_index co duoc truyen dung khong
    with patch.object(
        view._prompt_builder, "build_prompt", wraps=view._prompt_builder.build_prompt
    ) as mock_build:
        # Case 1: Semantic ON
        view._semantic_index_toggle.setChecked(True)
        view.on_copy_smart_requested()  # Goi truc tiep controller method

        # Cho worker finish (hoac mock Worker de no chay dong bo)
        # Nhung thuc ra chung ta chi quan tam call vao build_prompt (xay ra trong worker)

        qtbot.waitUntil(lambda: mock_build.call_count >= 1, timeout=5000)

        args, kwargs = mock_build.call_args
        assert kwargs.get("semantic_index") is True

        # Check the result of build_prompt (which is BuildResult or tuple depending on which method)
        # Actually build_prompt returns (prompt, token_count, breakdown)
        res = mock_build.return_value
        prompt = res[0]

        print(f"\nPROMPT (Semantic ON):\n{prompt[:500]}...")
        # If it's REALLY compressed, it should have <smart_context> and NOT <file>
        # However, I suspect it current has <file>
        assert "<smart_context>" in prompt
        assert "<file name=" not in prompt  # This should fail if my theory is right

        mock_build.reset_mock()

        # Case 2: Semantic OFF
        view._semantic_index_toggle.setChecked(False)
        view.on_copy_smart_requested()

        qtbot.waitUntil(lambda: mock_build.call_count >= 1, timeout=5000)
        args, kwargs = mock_build.call_args
        assert kwargs.get("semantic_index") is False
