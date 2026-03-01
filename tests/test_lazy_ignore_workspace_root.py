"""
Regression tests for lazy loading ignore behavior with workspace-root matching.
"""

from pathlib import Path

from core.utils.file_utils import TreeItem, load_folder_children, scan_directory_shallow


def _collect_file_labels(item: TreeItem) -> list[str]:
    labels: list[str] = []

    def walk(node: TreeItem) -> None:
        if not node.is_dir:
            labels.append(node.label)
        for child in node.children:
            walk(child)

    walk(item)
    return labels


def test_lazy_load_children_respects_workspace_relative_pattern(tmp_path: Path) -> None:
    """Lazy load must honor workspace-relative patterns at deep levels."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    (workspace / "a").mkdir()
    (workspace / "a" / "b").mkdir()
    (workspace / "a" / "b" / "c").mkdir()
    (workspace / "a" / "b" / "c" / "deep.py").write_text("# deep", encoding="utf-8")
    (workspace / "a" / "b" / "ok.py").write_text("# ok", encoding="utf-8")

    tree = scan_directory_shallow(
        workspace,
        depth=1,
        excluded_patterns=["a/b/c/deep.py"],
        use_gitignore=False,
        use_default_ignores=False,
    )

    folder_a = next(child for child in tree.children if child.label == "a")
    load_folder_children(
        folder_a,
        excluded_patterns=["a/b/c/deep.py"],
        use_gitignore=False,
        use_default_ignores=False,
        workspace_root=workspace,
    )

    folder_b = next(child for child in folder_a.children if child.label == "b")
    load_folder_children(
        folder_b,
        excluded_patterns=["a/b/c/deep.py"],
        use_gitignore=False,
        use_default_ignores=False,
        workspace_root=workspace,
    )

    folder_c = next(child for child in folder_b.children if child.label == "c")
    load_folder_children(
        folder_c,
        excluded_patterns=["a/b/c/deep.py"],
        use_gitignore=False,
        use_default_ignores=False,
        workspace_root=workspace,
    )

    labels = _collect_file_labels(tree)
    assert "ok.py" in labels
    assert "deep.py" not in labels


def test_lazy_load_matches_full_scan_with_same_config(tmp_path: Path) -> None:
    """Lazy expansion should produce same visible files as full shallow scan depth."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    (workspace / "src").mkdir()
    (workspace / "src" / "keep.py").write_text("# keep", encoding="utf-8")
    (workspace / "src" / "secret.py").write_text("# secret", encoding="utf-8")
    (workspace / "nested").mkdir()
    (workspace / "nested" / "deeper").mkdir()
    (workspace / "nested" / "deeper" / "hide.py").write_text("# hide", encoding="utf-8")
    (workspace / "nested" / "deeper" / "show.py").write_text("# show", encoding="utf-8")

    patterns = ["src/secret.py", "nested/deeper/hide.py"]

    deep_scan_tree = scan_directory_shallow(
        workspace,
        depth=5,
        excluded_patterns=patterns,
        use_gitignore=False,
        use_default_ignores=False,
    )

    lazy_tree = scan_directory_shallow(
        workspace,
        depth=1,
        excluded_patterns=patterns,
        use_gitignore=False,
        use_default_ignores=False,
    )

    for child in lazy_tree.children:
        if child.is_dir:
            load_folder_children(
                child,
                excluded_patterns=patterns,
                use_gitignore=False,
                use_default_ignores=False,
                workspace_root=workspace,
            )
            for nested in child.children:
                if nested.is_dir:
                    load_folder_children(
                        nested,
                        excluded_patterns=patterns,
                        use_gitignore=False,
                        use_default_ignores=False,
                        workspace_root=workspace,
                    )

    full_labels = sorted(_collect_file_labels(deep_scan_tree))
    lazy_labels = sorted(_collect_file_labels(lazy_tree))

    assert full_labels == lazy_labels


def test_load_folder_children_raises_without_workspace_root(tmp_path: Path) -> None:
    """workspace_root=None phai raise ValueError."""
    import pytest

    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "sub").mkdir()

    tree = scan_directory_shallow(
        workspace,
        depth=1,
        use_gitignore=False,
        use_default_ignores=False,
    )
    folder = next(c for c in tree.children if c.is_dir)

    with pytest.raises(
        ValueError,
        match="workspace_root is required|Caller must provide workspace root",
    ):
        # Bo thieu parameter workspace_root (hoac set explicitly la None)
        load_folder_children(
            folder,
            use_gitignore=False,
            use_default_ignores=False,
        )
