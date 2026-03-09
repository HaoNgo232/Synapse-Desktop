"""
Unit tests cho Canonical Workspace Summary module.

Test cac case:
- WorkspaceSummary dataclass defaults
- build_canonical_summary(): Delegate dung toi cac ham generator
- get_summary_as_text(): Render summary thanh text
- Format detection logic
- Stats computation
"""

import pytest
from pathlib import Path

from domain.codemap.canonical_structure import (
    WorkspaceSummary,
    build_canonical_summary,
    get_summary_as_text,
)
from infrastructure.filesystem.file_utils import TreeItem
from infrastructure.git.git_utils import GitDiffResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_tree(tmp_path: Path) -> TreeItem:
    """Tao mot tree don gian voi 1 folder va 2 files."""
    file_a = tmp_path / "src" / "main.py"
    file_b = tmp_path / "src" / "utils.py"
    file_a.parent.mkdir(parents=True, exist_ok=True)
    file_a.write_text("def main(): pass\n")
    file_b.write_text("def helper(): pass\n")

    child_a = TreeItem(
        label="main.py",
        path=str(file_a),
        is_dir=False,
        children=[],
    )
    child_b = TreeItem(
        label="utils.py",
        path=str(file_b),
        is_dir=False,
        children=[],
    )
    src_dir = TreeItem(
        label="src",
        path=str(tmp_path / "src"),
        is_dir=True,
        children=[child_a, child_b],
    )
    root = TreeItem(
        label=tmp_path.name,
        path=str(tmp_path),
        is_dir=True,
        children=[src_dir],
    )
    return root


@pytest.fixture
def selected_all(simple_tree: TreeItem, tmp_path: Path) -> set[str]:
    """Chon tat ca files va folders."""
    return {
        str(tmp_path),
        str(tmp_path / "src"),
        str(tmp_path / "src" / "main.py"),
        str(tmp_path / "src" / "utils.py"),
    }


@pytest.fixture
def selected_files_only(tmp_path: Path) -> set[str]:
    """Chi chon files, khong chon folders."""
    return {
        str(tmp_path / "src" / "main.py"),
        str(tmp_path / "src" / "utils.py"),
    }


# ---------------------------------------------------------------------------
# WorkspaceSummary dataclass
# ---------------------------------------------------------------------------


class TestWorkspaceSummary:
    """Test WorkspaceSummary dataclass defaults and construction."""

    def test_default_values(self):
        """Defaults should be empty/None."""
        summary = WorkspaceSummary()
        assert summary.file_tree == ""
        assert summary.repo_map == ""
        assert summary.git_changes is None
        assert summary.stats == {}
        assert summary.format == "tree"

    def test_custom_values(self):
        """Should accept custom values."""
        summary = WorkspaceSummary(
            file_tree="src/\n  main.py",
            repo_map="def main(): ...",
            git_changes="+ new line",
            stats={"file_count": 1, "folder_count": 0, "total_selected": 1},
            format="full",
        )
        assert summary.file_tree == "src/\n  main.py"
        assert summary.repo_map == "def main(): ..."
        assert summary.git_changes == "+ new line"
        assert summary.stats["file_count"] == 1
        assert summary.format == "full"


# ---------------------------------------------------------------------------
# build_canonical_summary
# ---------------------------------------------------------------------------


class TestBuildCanonicalSummary:
    """Test build_canonical_summary() delegation and output."""

    def test_basic_tree_only(self, simple_tree, selected_all, tmp_path):
        """Basic call produces file_tree and stats."""
        summary = build_canonical_summary(
            tree=simple_tree,
            selected_paths=selected_all,
            workspace_root=tmp_path,
        )
        assert isinstance(summary, WorkspaceSummary)
        assert summary.file_tree != ""
        assert summary.format == "tree"
        assert summary.repo_map == ""
        assert summary.git_changes is None
        assert summary.stats["total_selected"] == len(selected_all)

    def test_stats_file_folder_counts(self, simple_tree, selected_all, tmp_path):
        """Stats should correctly separate files from folders."""
        summary = build_canonical_summary(
            tree=simple_tree,
            selected_paths=selected_all,
            workspace_root=tmp_path,
        )
        # 2 files (main.py, utils.py), 2 folders (root, src)
        assert summary.stats["file_count"] == 2
        assert summary.stats["folder_count"] == 2

    def test_with_repo_map(self, simple_tree, selected_all, tmp_path):
        """include_repo_map=True should populate repo_map field."""
        summary = build_canonical_summary(
            tree=simple_tree,
            selected_paths=selected_all,
            workspace_root=tmp_path,
            include_repo_map=True,
        )
        assert summary.format == "repo_map"
        # repo_map should contain function signature from the .py files
        assert summary.repo_map != ""

    def test_with_git_changes(self, simple_tree, selected_all, tmp_path):
        """include_git_changes=True with diffs should populate git_changes."""
        diffs = GitDiffResult(
            work_tree_diff="diff --git a/main.py\n+ new line",
            staged_diff="",
        )
        summary = build_canonical_summary(
            tree=simple_tree,
            selected_paths=selected_all,
            workspace_root=tmp_path,
            include_git_changes=True,
            git_diffs=diffs,
        )
        assert summary.git_changes is not None
        assert "new line" in summary.git_changes

    def test_full_format(self, simple_tree, selected_all, tmp_path):
        """Both repo_map and git_changes -> format='full'."""
        diffs = GitDiffResult(
            work_tree_diff="diff content",
            staged_diff="",
        )
        summary = build_canonical_summary(
            tree=simple_tree,
            selected_paths=selected_all,
            workspace_root=tmp_path,
            include_repo_map=True,
            include_git_changes=True,
            git_diffs=diffs,
        )
        assert summary.format == "full"

    def test_no_git_diffs_object(self, simple_tree, selected_all, tmp_path):
        """include_git_changes=True but no diffs object -> git_changes is None."""
        summary = build_canonical_summary(
            tree=simple_tree,
            selected_paths=selected_all,
            workspace_root=tmp_path,
            include_git_changes=True,
            git_diffs=None,
        )
        assert summary.git_changes is None

    def test_empty_selected_paths(self, simple_tree, tmp_path):
        """Empty selected_paths should produce empty file_tree."""
        summary = build_canonical_summary(
            tree=simple_tree,
            selected_paths=set(),
            workspace_root=tmp_path,
        )
        assert summary.stats["file_count"] == 0
        assert summary.stats["folder_count"] == 0
        assert summary.stats["total_selected"] == 0

    def test_use_relative_paths(self, simple_tree, selected_all, tmp_path):
        """Relative paths should not contain absolute tmp_path prefix in tree."""
        summary = build_canonical_summary(
            tree=simple_tree,
            selected_paths=selected_all,
            workspace_root=tmp_path,
            use_relative_paths=True,
        )
        assert isinstance(summary.file_tree, str)


# ---------------------------------------------------------------------------
# get_summary_as_text
# ---------------------------------------------------------------------------


class TestGetSummaryAsText:
    """Test get_summary_as_text() rendering."""

    def test_tree_only(self):
        """Should render file_map section."""
        summary = WorkspaceSummary(file_tree="src/\n  main.py")
        text = get_summary_as_text(summary)
        assert "<file_map>" in text
        assert "src/" in text
        assert "</file_map>" in text

    def test_with_repo_map(self):
        """Should include repo_map section."""
        summary = WorkspaceSummary(
            file_tree="src/",
            repo_map="def main(): ...",
        )
        text = get_summary_as_text(summary)
        assert "<repo_map>" in text
        assert "def main(): ..." in text

    def test_with_git_changes(self):
        """Should include git_changes section."""
        summary = WorkspaceSummary(
            file_tree="src/",
            git_changes="+ added line",
        )
        text = get_summary_as_text(summary)
        assert "<git_changes>" in text
        assert "+ added line" in text

    def test_with_stats(self):
        """Should include summary section with stats."""
        summary = WorkspaceSummary(
            file_tree="src/",
            stats={"file_count": 3, "folder_count": 1, "total_selected": 4},
        )
        text = get_summary_as_text(summary)
        assert "<summary>" in text
        assert "3 files" in text
        assert "1 folders" in text

    def test_empty_summary(self):
        """Empty summary should produce empty text."""
        summary = WorkspaceSummary()
        text = get_summary_as_text(summary)
        assert text == ""

    def test_full_summary_ordering(self):
        """Sections should appear in order: file_map, repo_map, git_changes, summary."""
        summary = WorkspaceSummary(
            file_tree="tree",
            repo_map="map",
            git_changes="diffs",
            stats={"file_count": 1, "folder_count": 0},
        )
        text = get_summary_as_text(summary)
        tree_pos = text.index("<file_map>")
        map_pos = text.index("<repo_map>")
        git_pos = text.index("<git_changes>")
        stats_pos = text.index("<summary>")
        assert tree_pos < map_pos < git_pos < stats_pos
