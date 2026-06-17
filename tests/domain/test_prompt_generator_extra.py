import pytest
from pathlib import Path
import pathlib
from unittest.mock import patch
from domain.prompt.generator import (
    generate_file_structure_xml,
    generate_file_map,
    generate_file_contents_xml,
    generate_file_contents_plain,
    generate_smart_context,
    build_smart_prompt,
    generate_prompt,
)
from domain.smart_context.tree_item import TreeItem

import sys
# Determine correct platform Path class for mock patching
PATH_CLASS = pathlib.WindowsPath if sys.platform == "win32" else (pathlib.PosixPath if hasattr(pathlib, "PosixPath") else pathlib.Path)


class TestPromptGeneratorExtra:
    def test_generate_file_structure_xml_extra(self):
        # 1. Empty folder XML output (line 81)
        tree_empty = TreeItem(
            label="empty_dir", path="/workspace/empty_dir", is_dir=True, children=[]
        )
        xml_empty = generate_file_structure_xml(
            tree_empty, selected_paths=set(), show_all=True
        )
        assert '<folder name="empty_dir"/>' in xml_empty

        # 2. Show all = False and nothing selected (line 87)
        tree_nested = TreeItem(
            label="root",
            path="/workspace",
            is_dir=True,
            children=[
                TreeItem(label="main.py", path="/workspace/main.py", is_dir=False)
            ],
        )
        xml_none = generate_file_structure_xml(
            tree_nested, selected_paths=set(), show_all=False
        )
        assert xml_none == ""

        # 3. Show all = False and descendant selected (lines 73-74, 77, 83-84)
        xml_sel = generate_file_structure_xml(
            tree_nested,
            selected_paths={"/workspace/main.py"},
            workspace_root=Path("/workspace"),
            use_relative_paths=True,
            show_all=False,
        )
        assert '<folder name="root">' in xml_sel
        assert '<file path="main.py"/>' in xml_sel

    def test_generate_file_map_extra(self):
        # 1. show_all = True (line 124)
        tree = TreeItem(
            label="root",
            path="/workspace",
            is_dir=True,
            children=[
                TreeItem(label="main.py", path="/workspace/main.py", is_dir=False)
            ],
        )
        fmap = generate_file_map(tree, selected_paths=set(), show_all=True)
        assert "main.py" in fmap

        # 2. Nested directory strings (lines 183-184)
        tree_deep = TreeItem(
            label="root",
            path="/workspace",
            is_dir=True,
            children=[
                TreeItem(
                    label="src",
                    path="/workspace/src",
                    is_dir=True,
                    children=[
                        TreeItem(
                            label="helper.py",
                            path="/workspace/src/helper.py",
                            is_dir=False,
                        )
                    ],
                ),
                TreeItem(label="main.py", path="/workspace/main.py", is_dir=False),
            ],
        )
        fmap_deep = generate_file_map(tree_deep, selected_paths=set(), show_all=True)
        assert "├── src" in fmap_deep
        assert "│   └── helper.py" in fmap_deep
        assert "└── main.py" in fmap_deep

    def test_generate_file_contents_xml_extra(self, tmp_path):
        # 1. Normal XML contents without codemap_paths (lines 280-283)
        normal_file = tmp_path / "normal.py"
        normal_file.write_text("print('hello')", encoding="utf-8")
        xml = generate_file_contents_xml(
            {str(normal_file)}, workspace_root=tmp_path, use_relative_paths=True
        )
        assert '<file path="normal.py">' in xml

        # 2. Empty elements returns <files></files> (line 276)
        xml_empty = generate_file_contents_xml(set(), codemap_paths={"/fake.py"})
        assert xml_empty == "<files></files>"

        # 3. Both full paths and codemap paths present (line 253)
        other_file = tmp_path / "other.py"
        other_file.write_text("print('other')", encoding="utf-8")
        xml_mixed = generate_file_contents_xml(
            selected_paths={str(normal_file), str(other_file)},
            workspace_root=tmp_path,
            use_relative_paths=True,
            codemap_paths={str(normal_file)},
        )
        assert 'context="codemap"' in xml_mixed
        assert 'path="other.py"' in xml_mixed

    def test_generate_file_contents_plain_extra(self, tmp_path):
        # 1. Normal Plain contents without codemap_paths (lines 459-462)
        normal_file = tmp_path / "normal.py"
        normal_file.write_text("print('hello')", encoding="utf-8")
        plain = generate_file_contents_plain(
            {str(normal_file)}, workspace_root=tmp_path, use_relative_paths=True
        )
        assert "FILE: normal.py" in plain

        # 2. Both full paths and codemap paths present (lines 411-416)
        other_file = tmp_path / "other.py"
        other_file.write_text("print('other')", encoding="utf-8")
        plain_mixed = generate_file_contents_plain(
            selected_paths={str(normal_file), str(other_file)},
            workspace_root=tmp_path,
            use_relative_paths=True,
            codemap_paths={str(normal_file)},
        )
        assert "FILE: normal.py [codemap]" in plain_mixed
        assert "FILE: other.py" in plain_mixed

    def test_generate_file_contents_xml_codemap_edge_cases(self, tmp_path):
        # Create temp files: normal, binary, too large, unsupported
        normal_file = tmp_path / "normal.py"
        normal_file.write_text("def run(): pass", encoding="utf-8")

        binary_file = tmp_path / "binary.png"
        binary_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

        large_file = tmp_path / "large.py"
        large_file.write_text("a" * 1000, encoding="utf-8")  # size 1000

        unsupported_file = tmp_path / "doc.txt"
        unsupported_file.write_text("Hello text", encoding="utf-8")

        selected = {
            str(normal_file),
            str(binary_file),
            str(large_file),
            str(unsupported_file),
            "/nonexistent.py",
        }
        codemap = {
            str(normal_file),
            str(binary_file),
            str(large_file),
            str(unsupported_file),
            "/nonexistent.py",
        }

        # Call generate_file_contents_xml with codemap_paths and max_file_size = 500 (so large.py is skipped)
        xml = generate_file_contents_xml(
            selected_paths=selected,
            max_file_size=500,
            workspace_root=tmp_path,
            use_relative_paths=True,
            codemap_paths=codemap,
        )

        assert "normal.py" in xml
        assert "binary.png" not in xml
        assert "large.py" not in xml
        # unsupported doc.txt falls back to normal read
        assert "doc.txt" in xml
        assert "nonexistent.py" not in xml

    def test_generate_file_contents_xml_collision(self):
        # Trigger path collision ValueError (line 237-240)
        selected = {"a.py", "./a.py"}
        with pytest.raises(ValueError, match="Path collision"):
            generate_file_contents_xml(
                selected_paths=selected,
                workspace_root=Path("/workspace"),
                use_relative_paths=False,
                codemap_paths={"a.py"},
            )

    def test_generate_file_contents_plain_codemap(self, tmp_path):
        # Test generate_file_contents_plain with codemap_paths (line 375-457)
        normal_file = tmp_path / "normal.py"
        normal_file.write_text("def run(): pass", encoding="utf-8")

        binary_file = tmp_path / "binary.png"
        binary_file.write_bytes(b"\x00\x00\x00")

        unsupported_file = tmp_path / "doc.txt"
        unsupported_file.write_text("Hello text", encoding="utf-8")

        selected = {
            str(normal_file),
            str(binary_file),
            str(unsupported_file),
            "/nonexistent.py",
        }
        codemap = {
            str(normal_file),
            str(binary_file),
            str(unsupported_file),
            "/nonexistent.py",
        }

        plain = generate_file_contents_plain(
            selected_paths=selected,
            max_file_size=1000,
            workspace_root=tmp_path,
            use_relative_paths=True,
            codemap_paths=codemap,
        )

        assert "normal.py [codemap]" in plain
        assert "binary.png" not in plain
        assert "doc.txt [codemap-fallback]" in plain
        assert "nonexistent.py" not in plain

    def test_generate_file_contents_plain_collision(self):
        selected = {"a.py", "./a.py"}
        with pytest.raises(ValueError, match="Path collision"):
            generate_file_contents_plain(
                selected_paths=selected,
                workspace_root=Path("/workspace"),
                use_relative_paths=False,
                codemap_paths={"a.py"},
            )

    def test_generate_smart_context_edge_cases(self, tmp_path):
        # Create files for smart context
        normal_file = tmp_path / "normal.py"
        normal_file.write_text("def run(): pass", encoding="utf-8")

        binary_file = tmp_path / "binary.png"
        binary_file.write_bytes(b"\x00\x00\x00")

        large_file = tmp_path / "large.py"
        large_file.write_text("a" * 1000, encoding="utf-8")

        unsupported_file = tmp_path / "doc.txt"
        unsupported_file.write_text("hello text", encoding="utf-8")

        selected = {
            str(normal_file),
            str(binary_file),
            str(large_file),
            str(unsupported_file),
            "/nonexistent.py",
        }

        # Mock is_supported, smart_parse (line 541 fail case)
        with patch("domain.smart_context.smart_parse") as mock_parse:
            # First file (normal.py) returns None (parse fail)
            mock_parse.return_value = None

            context = generate_smart_context(
                selected_paths=selected,
                max_file_size=500,  # skip large_file
                workspace_root=tmp_path,
                use_relative_paths=True,
            )

            # verify error reports
            assert "Skipped: Not a file" in context  # nonexistent.py
            assert "Skipped: Binary file" in context  # binary.png
            assert "Skipped: File too large" in context  # large.py
            assert "Skipped: Smart Context not available" in context  # doc.txt
            assert "Skipped: Smart Context parse failed" in context  # normal.py

    def test_generate_smart_context_threadpool(self, tmp_path):
        # Create 6 files to trigger ThreadPoolExecutor (> 5 files, line 553-555)
        files = []
        for i in range(6):
            f = tmp_path / f"file_{i}.py"
            f.write_text(f"def f_{i}(): pass", encoding="utf-8")
            files.append(str(f))

        with patch("domain.smart_context.smart_parse") as mock_parse:
            mock_parse.return_value = "def mock_func(): pass"

            context = generate_smart_context(
                selected_paths=set(files),
                workspace_root=tmp_path,
                use_relative_paths=True,
            )
            assert "file_0.py" in context
            assert "file_5.py" in context
            assert "def mock_func(): pass" in context

    def test_generate_smart_context_sequential(self, tmp_path):
        # 1 file to trigger sequential execution (line 562)
        f = tmp_path / "seq.py"
        f.write_text("def seq_f(): pass", encoding="utf-8")

        with patch("domain.smart_context.smart_parse") as mock_parse:
            mock_parse.return_value = "def mock_seq(): pass"
            context = generate_smart_context(
                selected_paths={str(f)},
                workspace_root=tmp_path,
                use_relative_paths=True,
            )
            assert "seq.py" in context
            assert "def mock_seq(): pass" in context

    @patch("domain.prompt.generator.is_binary_file")
    @patch.object(PATH_CLASS, "is_file")
    def test_exceptions_coverage(self, mock_is_file, mock_is_binary, tmp_path):
        mock_is_file.return_value = True
        mock_is_binary.return_value = False

        target_file = tmp_path / "error_file.py"
        target_file.write_text("def run(): pass", encoding="utf-8")

        selected = {str(target_file)}

        # Helper mock for Path.stat to raise OSError when path contains error_file.py
        orig_stat = pathlib.Path.stat
        orig_posix_stat_stat = (
            pathlib.PosixPath.stat if hasattr(pathlib, "PosixPath") else None
        )
        orig_windows_stat_stat = (
            pathlib.WindowsPath.stat if hasattr(pathlib, "WindowsPath") else None
        )

        def mock_stat_func(self_obj, *args, **kwargs):
            if "error_file.py" in str(self_obj):
                raise OSError("Permission denied")
            return orig_stat(self_obj, *args, **kwargs)

        def apply_mock():
            pathlib.Path.stat = mock_stat_func
            if hasattr(pathlib, "PosixPath"):
                pathlib.PosixPath.stat = mock_stat_func
            if hasattr(pathlib, "WindowsPath"):
                pathlib.WindowsPath.stat = mock_stat_func

        def restore_mock():
            pathlib.Path.stat = orig_stat
            if orig_posix_stat_stat:
                pathlib.PosixPath.stat = orig_posix_stat_stat
            if orig_windows_stat_stat:
                pathlib.WindowsPath.stat = orig_windows_stat_stat

        # 1. OSError in stat inside _generate_codemap_xml_elements (line 318-319)
        apply_mock()
        try:
            xml = generate_file_contents_xml(
                selected, workspace_root=tmp_path, codemap_paths=selected
            )
            assert "error_file.py" not in xml
        finally:
            restore_mock()

        # 2. OSError in read_text inside _generate_codemap_xml_elements (line 347-348)
        with patch.object(PATH_CLASS, "read_text", side_effect=OSError("Read error")):
            xml = generate_file_contents_xml(
                selected, workspace_root=tmp_path, codemap_paths=selected
            )
            assert "error_file.py" not in xml

        # 3. OSError in read_text inside generate_file_contents_plain (line 454-455)
        with patch.object(PATH_CLASS, "read_text", side_effect=OSError("Read error")):
            plain = generate_file_contents_plain(
                selected, workspace_root=tmp_path, codemap_paths=selected
            )
            assert "error_file.py" not in plain

        # 4. OSError in stat inside _process_single_file (line 519-520)
        apply_mock()
        try:
            context = generate_smart_context(selected, workspace_root=tmp_path)
            assert "error_file.py" in context  # Skipped: Error reading file
        finally:
            restore_mock()

        # 5. OSError in read_text inside _process_single_file (line 543-544)
        with patch.object(PATH_CLASS, "read_text", side_effect=OSError("Read error")):
            context = generate_smart_context(selected, workspace_root=tmp_path)
            assert "Skipped: Error reading file:" in context

    def test_api_delegation(self):
        # Build smart prompt and generate prompt delegation coverage
        with (
            patch("domain.prompt.generator.assemble_smart_prompt") as mock_smart,
            patch("domain.prompt.generator.assemble_prompt") as mock_prompt,
        ):
            mock_smart.return_value = "smart_prompt_val"
            mock_prompt.return_value = "prompt_val"

            res1 = build_smart_prompt("smart", "map")
            mock_smart.assert_called_once()
            assert res1 == "smart_prompt_val"

            res2 = generate_prompt("map", "contents")
            mock_prompt.assert_called_once()
            assert res2 == "prompt_val"
