import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import application.services.workspace_index as ws_idx
from application.services.workspace_index import (
    build_search_index,
    search_in_index,
    collect_files_from_disk,
    WorkspaceScanner,
    WorkspaceScanService,
    get_related_files_for_paths,
)
from domain.ports.registry import DomainRegistry


class TestWorkspaceIndexExtra:
    @pytest.fixture(autouse=True)
    def patch_quick_skip(self):
        from shared.constants import file_patterns
        import shared.constants

        original_skip = file_patterns.DIRECTORY_QUICK_SKIP
        new_skip = frozenset(original_skip - {"tmp", "temp"})
        with (
            patch.object(file_patterns, "DIRECTORY_QUICK_SKIP", new_skip),
            patch.object(shared.constants, "DIRECTORY_QUICK_SKIP", new_skip),
        ):
            yield

    @pytest.fixture(autouse=True)
    def setup_scandir_rs_mock(self):
        # Setup fake scandir_rs in sys.modules
        self.mock_scandir = MagicMock()
        sys.modules["scandir_rs"] = self.mock_scandir

        # Enable it in workspace_index
        orig_has_scandir = ws_idx.HAS_SCANDIR_RS
        ws_idx.HAS_SCANDIR_RS = True

        yield

        ws_idx.HAS_SCANDIR_RS = orig_has_scandir
        if "scandir_rs" in sys.modules:
            del sys.modules["scandir_rs"]

    @pytest.fixture(autouse=True)
    def patch_file_utils(self):
        # Patch is_binary_file and is_system_path_str in shared.utils.file_utils
        with (
            patch(
                "shared.utils.file_utils.is_binary_file", return_value=False
            ) as self.mock_is_binary,
            patch(
                "shared.utils.file_utils.is_system_path_str", return_value=False
            ) as self.mock_is_system,
        ):
            yield

    def test_build_search_index_scandir_success(self, tmp_path):
        # 1. scandir_rs Walk success path (lines 87-134)
        mock_entry1 = MagicMock()
        mock_entry1.path = str(tmp_path / "src" / "main.py")

        mock_entry2 = MagicMock()
        mock_entry2.path = str(
            tmp_path / "node_modules" / "pkg.py"
        )  # Should be skipped by DIRECTORY_QUICK_SKIP

        mock_entry3 = MagicMock()
        mock_entry3.path = str(tmp_path / "bin.png")  # skipped because binary

        mock_entry4 = MagicMock()
        mock_entry4.path = "/other/dir/other.py"  # Does not start with root_path_str

        mock_entry5 = MagicMock()
        mock_entry5.path = str(tmp_path / "ignored.py")  # skipped by spec

        # Setup mock_scandir.Walk().collect()
        self.mock_scandir.Walk.return_value.collect.return_value = [
            mock_entry1,
            mock_entry2,
            mock_entry3,
            mock_entry4,
            mock_entry5,
        ]

        # Setup mock_is_binary side effect
        self.mock_is_binary.side_effect = lambda p: "bin.png" in p

        mock_spec = MagicMock()
        mock_spec.match_file.side_effect = lambda p: "ignored.py" in p

        with patch(
            "application.services.workspace_index._get_ignore_spec",
            return_value=mock_spec,
        ):
            index = build_search_index(tmp_path)
            print("DEBUG INDEX:", index)
            assert "main.py" in index
            assert len(index["main.py"]) == 1
            assert index["main.py"][0] == str(tmp_path / "src" / "main.py")
            # other.py is collected with rel_path = filename fallback
            assert "other.py" in index
            assert index["other.py"][0] == "/other/dir/other.py"
            # node_modules and bin.png and ignored.py skipped
            assert "pkg.py" not in index
            assert "bin.png" not in index
            assert "ignored.py" not in index

    def test_build_search_index_scandir_cancellation(self, tmp_path):
        # 2. scandir_rs cancellation (lines 103-104)
        mock_entry = MagicMock()
        mock_entry.path = str(tmp_path / "main.py")
        self.mock_scandir.Walk.return_value.collect.return_value = [mock_entry]

        # generation_check returns False
        gen_check = MagicMock(return_value=False)
        index = build_search_index(tmp_path, generation_check=gen_check)
        assert index == {}

    def test_build_search_index_scandir_exception(self, tmp_path):
        # 3. Exception in scandir_rs fallback to os.walk (lines 135-136)
        self.mock_scandir.Walk.side_effect = Exception("Scandir crashed")

        # Make os.walk return something
        with patch("os.walk") as mock_walk:
            mock_walk.return_value = [(str(tmp_path), [], ["main.py"])]
            index = build_search_index(tmp_path)
            assert "main.py" in index

    def test_build_search_index_scandir_import_error(self, tmp_path):
        # Cover ImportError during import scandir_rs in build_search_index (lines 65-66)
        orig_import = __import__

        def mock_import(name, *args, **kwargs):
            if name == "scandir_rs":
                raise ImportError("no scandir")
            return orig_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            index = build_search_index(tmp_path)
            assert isinstance(index, dict)

    def test_build_search_index_os_walk_exceptions_and_relative(self, tmp_path):
        with patch("application.services.workspace_index.HAS_SCANDIR_RS", False):
            # 4. Exception in os.walk (lines 165-166)
            with patch("os.walk", side_effect=Exception("Walk error")):
                index = build_search_index(tmp_path)
                assert index == {}

            # 5. relative path fallback in os.walk (line 156)
            # We pass a root path str that doesn't match full_path
            # os.walk yields a file path outside root_path
            with patch("os.walk") as mock_walk:
                mock_walk.return_value = [("/other/dir", [], ["other.py"])]
                index2 = build_search_index(tmp_path)
                # Should fall back to rel_path = filename
                assert "other.py" in index2

    def test_search_in_index_code_prefix_empty(self):
        # 6. empty query after "code:" prefix (line 185)
        index = {"main.py": ["/path/main.py"]}
        res = search_in_index(index, "code:   ")
        assert res == []

    def test_collect_files_from_disk_scandir_success(self, tmp_path):
        # 7. collect_files_from_disk using scandir_rs (lines 265-299)
        mock_entry1 = MagicMock()
        mock_entry1.path = str(tmp_path / "src" / "main.py")
        mock_entry2 = MagicMock()
        mock_entry2.path = str(tmp_path / "node_modules" / "pkg.py")  # directory skip
        mock_entry3 = MagicMock()
        mock_entry3.path = "/other/dir/other.py"  # Does not start with root_path_str
        mock_entry4 = MagicMock()
        mock_entry4.path = str(tmp_path / "bin.png")  # skipped because binary
        mock_entry5 = MagicMock()
        mock_entry5.path = str(tmp_path / "ignored.py")  # skipped by spec

        self.mock_scandir.Walk.return_value.collect.return_value = [
            mock_entry1,
            mock_entry2,
            mock_entry3,
            mock_entry4,
            mock_entry5,
        ]

        # Setup mock_is_binary side effect
        self.mock_is_binary.side_effect = lambda p: "bin.png" in p

        mock_spec = MagicMock()
        mock_spec.match_file.side_effect = lambda p: "ignored.py" in p

        with patch(
            "application.services.workspace_index._get_ignore_spec",
            return_value=mock_spec,
        ):
            res = collect_files_from_disk(tmp_path, workspace_path=tmp_path)
            assert str(tmp_path / "src" / "main.py") in res
            assert "/other/dir/other.py" in res
            assert str(tmp_path / "node_modules" / "pkg.py") not in res
            assert str(tmp_path / "bin.png") not in res
            assert str(tmp_path / "ignored.py") not in res

    def test_collect_files_from_disk_scandir_exception(self, tmp_path):
        # 8. Exception in scandir_rs collect_files (lines 300-301)
        self.mock_scandir.Walk.side_effect = Exception("Scandir crashed")
        with patch("os.walk") as mock_walk:
            mock_walk.return_value = [(str(tmp_path), [], ["main.py"])]
            res = collect_files_from_disk(tmp_path, workspace_path=tmp_path)
            assert str(tmp_path / "main.py") in res

    def test_collect_files_from_disk_scandir_import_error(self, tmp_path):
        # 9. ImportError during import scandir_rs (lines 238-241)
        orig_import = __import__

        def mock_import(name, *args, **kwargs):
            if name == "scandir_rs":
                raise ImportError("no scandir")
            return orig_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            # Even if HAS_SCANDIR_RS is True, if it raises ImportError it should pass
            res = collect_files_from_disk(tmp_path, workspace_path=tmp_path)
            # fallback to os.walk
            assert isinstance(res, list)

    def test_collect_files_from_disk_os_walk_branches(self, tmp_path):
        # 10. rel_path fallback when path doesn't start with root_path_str (line 316)
        # 11. skip directory match (line 321)
        # 12. spec.match_file is True (line 328)
        # We mock spec.match_file to return True for ignored.py
        mock_spec = MagicMock()
        mock_spec.match_file.side_effect = lambda p: "ignored.py" in p

        with (
            patch("application.services.workspace_index.HAS_SCANDIR_RS", False),
            patch(
                "application.services.workspace_index._get_ignore_spec",
                return_value=mock_spec,
            ),
            patch("os.walk") as mock_walk,
        ):
            # Yield:
            # dirpath = "/other/dir"
            # filenames = ["other.py", "ignored.py", "node_modules/pkg.py"]
            # directory skip (line 321) is triggered if rel_path contains directory in DIRECTORY_QUICK_SKIP
            mock_walk.return_value = [
                ("/other/dir", [], ["other.py", "ignored.py", os.path.normpath("node_modules/pkg.py")])
            ]

            res = collect_files_from_disk(tmp_path, workspace_path=tmp_path)
            res_normalized = [os.path.normpath(r) for r in res]
            # other.py is collected
            assert os.path.normpath("/other/dir/other.py") in res_normalized
            # ignored.py is skipped (match_file is True)
            assert os.path.normpath("/other/dir/ignored.py") not in res_normalized
            # node_modules/pkg.py is skipped (directory check contains sep + node_modules + sep)
            assert os.path.normpath("/other/dir/node_modules/pkg.py") not in res_normalized

    def test_workspace_scanner_adapter(self, tmp_path):
        adapter = WorkspaceScanner()
        with patch(
            "application.services.workspace_index.collect_files_from_disk",
            return_value=["file1"],
        ) as mock_collect:
            res = adapter.collect_files(tmp_path)
            mock_collect.assert_called_once_with(tmp_path, workspace_path=tmp_path)
            assert res == ["file1"]

    def test_workspace_scan_service(self, tmp_path):
        # 13. WorkspaceScanService.scan_directory (lines 361-367)
        mock_scanner = MagicMock()
        mock_scanner.scan_directory.return_value = "scan_result"
        DomainRegistry.register_directory_scanner(mock_scanner)

        res = WorkspaceScanService.scan_directory(
            tmp_path, "ignore_engine", ["pattern"], True
        )
        assert res == "scan_result"
        mock_scanner.scan_directory.assert_called_once_with(
            tmp_path, excluded_patterns=["pattern"], use_gitignore=True
        )

    def test_get_related_files_for_paths_edge_cases(self, tmp_path):
        # 14. path is not a file (line 389)
        # 15. target does not exist (line 392-393)

        # Mock DependencyResolver
        mock_resolver = MagicMock()

        # We return a mock target path that does not exist
        target_path = tmp_path / "nonexistent.py"  # does not exist on disk
        mock_resolver.get_related_files.return_value = {target_path}

        with patch(
            "domain.codemap.dependency_resolver.DependencyResolver",
            return_value=mock_resolver,
        ):
            # Pass a directory (which is not a file -> line 389 continue) and a file path
            dir_path = str(tmp_path)
            file_path = str(tmp_path / "exists.py")
            # Create the file exists.py
            Path(file_path).write_text("content", encoding="utf-8")

            res = get_related_files_for_paths(
                tmp_path, None, {dir_path, file_path}, depth=1
            )
            # Since target_path "nonexistent.py" does not exist, the result should be empty
            assert len(res) == 0

            # Now let's make target_path exist and check if it is added
            target_path.write_text("exists", encoding="utf-8")
            res2 = get_related_files_for_paths(tmp_path, None, {file_path}, depth=1)
            assert str(target_path.resolve()) in res2
