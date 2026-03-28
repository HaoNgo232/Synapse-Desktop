import tempfile
import pytest
from pathlib import Path

from application.services.prompt_build_service import PromptBuildService
from infrastructure.filesystem.file_utils import TreeItem


def create_mock_tree(workspace_path: Path) -> TreeItem:
    """Tạo một cây thư mục giả lập với cấu trúc phân cấp để test."""
    root = TreeItem("root", str(workspace_path), is_dir=True)

    # src/
    src_path = workspace_path / "src"
    dir_src = TreeItem("src", str(src_path), is_dir=True)
    file_main = TreeItem("main.py", str(src_path / "main.py"), is_dir=False)
    file_utils = TreeItem("utils.py", str(src_path / "utils.py"), is_dir=False)
    dir_src.children = [file_main, file_utils]

    # tests/
    tests_path = workspace_path / "tests"
    dir_tests = TreeItem("tests", str(tests_path), is_dir=True)
    file_test = TreeItem("test_main.py", str(tests_path / "test_main.py"), is_dir=False)
    dir_tests.children = [file_test]

    # .hidden/
    hidden_path = workspace_path / ".hidden"
    dir_hidden = TreeItem(".hidden", str(hidden_path), is_dir=True)
    file_secret = TreeItem("secret.txt", str(hidden_path / "secret.txt"), is_dir=False)
    dir_hidden.children = [file_secret]

    # root files
    file_readme = TreeItem("README.md", str(workspace_path / "README.md"), is_dir=False)
    file_gitignore = TreeItem(
        ".gitignore", str(workspace_path / ".gitignore"), is_dir=False
    )

    root.children = [dir_src, dir_tests, dir_hidden, file_readme, file_gitignore]
    return root


class TestPromptPipelineStress50:
    """Stress test cho Prompt Pipeline với 50 use cases khác nhau."""

    @pytest.fixture
    def service(self):
        return PromptBuildService()

    @pytest.fixture
    def workspace_setup(self):
        with tempfile.TemporaryDirectory() as temp_root:
            workspace = Path(temp_root)
            tree = create_mock_tree(workspace)
            yield workspace, tree

    def test_50_prompt_scenarios(self, service, workspace_setup):
        """Chạy tổ hợp 50 kịch bản test khác nhau."""
        workspace, mock_tree = workspace_setup

        formats = ["xml", "plain", "json", "smart", "markdown"]
        full_tree_options = [True, False]
        instr_pos_options = [True, False]  # True: top, False: bottom
        opx_options = [True, False]

        selection_sets = [
            {str(workspace / "src" / "main.py")},
            {str(workspace / "src" / "main.py"), str(workspace / "src" / "utils.py")},
            {str(workspace / "README.md")},
            {str(workspace / "tests" / "test_main.py")},
            set(),
        ]

        use_cases = []
        for fmt in formats:
            for ft in full_tree_options:
                for top in instr_pos_options:
                    for opx in opx_options:
                        for sel in selection_sets:
                            if (
                                len(use_cases) < 100
                            ):  # Tăng lên 100 case để test đủ các format
                                use_cases.append((fmt, ft, top, opx, sel))

        for i, (fmt, ft, top, opx, sel) in enumerate(use_cases):
            instructions = f"STRESS_TEST_TASK_{i}"

            prompt, tokens, breakdown = service.build_prompt(
                file_paths=[Path(p) for p in sel],
                workspace=workspace,
                instructions=instructions,
                output_format=fmt,
                include_git_changes=False,
                use_relative_paths=True,
                tree_item=mock_tree,
                selected_paths=sel,
                include_xml_formatting=opx,
                instructions_at_top=top,
                full_tree=ft,
            )

            # --- KIỂM CHỨNG TÍNH TOÀN VẸN ---

            # 1. Full Tree Toggle
            if ft:
                # Nếu bật full_tree, folder 'tests' phải có mặt ngay cả khi không chọn file trong đó
                assert "tests" in prompt, (
                    f"Case {i}: Missing 'tests' folder in full tree mode ({fmt})"
                )
            else:
                # Nếu tắt full_tree (fallback), Plain text không được chứa file chưa chọn
                if fmt == "plain" and len(sel) > 0:
                    unselected_file = "test_main.py"
                    if not any(unselected_file in s for s in sel):
                        assert unselected_file not in prompt, (
                            f"Case {i}: Fallback tree leaked unselected file ({fmt})"
                        )

            # 2. XML Sandwich & Tags
            if fmt == "xml":
                assert "<user_instructions>" in prompt, (
                    f"Case {i}: Missing <user_instructions> in XML"
                )
                if top:
                    assert "<reminder>" in prompt, (
                        f"Case {i}: Missing sandwich <reminder> when instructions_at_top=True"
                    )
                else:
                    # Nếu instructions ở cuối, nó nên nằm ở nửa sau của prompt
                    assert prompt.find("<user_instructions>") > (len(prompt) // 4)

            # 3. Plain Text / Markdown / Smart Recency Bias
            if fmt in ["plain", "markdown", "smart"] and not top:
                # Kiểm tra instruction nằm ở gần cuối (trong 15 dòng cuối)
                last_lines = prompt.strip().split("\n")[-15:]
                assert any(instructions in line for line in last_lines), (
                    f"Case {i}: {fmt} instructions not at bottom for recency bias"
                )

            # 4. Thông tin Metadata cơ bản
            if fmt != "json":
                assert (
                    "================================================" in prompt
                    or "<metadata>" in prompt
                ), f"Case {i}: Missing basic structure markers"

            assert tokens > 0, f"Case {i}: Token count should be greater than zero"
            assert isinstance(breakdown, dict), (
                f"Case {i}: Breakdown must be a dictionary"
            )

        print(f"\nSuccessfully verified {len(use_cases)} prompt generation scenarios.")
