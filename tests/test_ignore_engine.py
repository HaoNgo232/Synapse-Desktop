"""
Tests cho core.ignore_engine - Unified Ignore Engine.

Kiem tra cac truong hop:
- build_ignore_patterns: VCS dirs, default ignores, user patterns, gitignore
- build_pathspec: PathSpec creation va caching
- read_gitignore: Doc .gitignore, .git/info/exclude
- find_git_root: Tim git root directory
- clear_cache: Xoa tat ca cache
"""

from pathlib import Path


from core.ignore_engine import (
    build_ignore_patterns,
    build_pathspec,
    read_gitignore,
    find_git_root,
    clear_cache,
    VCS_DIRS,
)


class TestBuildIgnorePatterns:
    """Test suite cho build_ignore_patterns."""

    def test_vcs_dirs_luon_co_mat(self, tmp_path: Path):
        """VCS directories (.git, .hg, .svn) luon co trong patterns."""
        patterns = build_ignore_patterns(tmp_path, use_default_ignores=False)
        for vcs_dir in VCS_DIRS:
            assert vcs_dir in patterns

    def test_default_ignores_khi_enabled(self, tmp_path: Path):
        """EXTENDED_IGNORE_PATTERNS duoc them khi use_default_ignores=True."""
        patterns = build_ignore_patterns(tmp_path, use_default_ignores=True)
        # node_modules la mot pattern mac dinh
        assert "node_modules" in patterns or any("node_modules" in p for p in patterns)

    def test_default_ignores_khi_disabled(self, tmp_path: Path):
        """Khong co EXTENDED_IGNORE_PATTERNS khi use_default_ignores=False."""
        patterns = build_ignore_patterns(
            tmp_path, use_default_ignores=False, use_gitignore=False
        )
        # Chi co VCS dirs
        assert len(patterns) == len(VCS_DIRS)

    def test_user_patterns_duoc_them(self, tmp_path: Path):
        """User-defined patterns duoc them vao list."""
        user_patterns = ["*.log", "temp/", "build/"]
        patterns = build_ignore_patterns(
            tmp_path,
            use_default_ignores=False,
            excluded_patterns=user_patterns,
            use_gitignore=False,
        )
        for p in user_patterns:
            assert p in patterns

    def test_gitignore_patterns_duoc_them(self, tmp_path: Path):
        """Gitignore patterns duoc them khi use_gitignore=True."""
        # Tao .gitignore
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n__pycache__/\n")

        # Clear cache de ensure fresh read
        clear_cache()

        patterns = build_ignore_patterns(
            tmp_path,
            use_default_ignores=False,
            use_gitignore=True,
        )
        assert "*.pyc" in patterns
        assert "__pycache__/" in patterns

    def test_thu_tu_uu_tien(self, tmp_path: Path):
        """Thu tu: VCS > Default > User > Gitignore."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("from_gitignore\n")
        clear_cache()

        patterns = build_ignore_patterns(
            tmp_path,
            use_default_ignores=True,
            excluded_patterns=["user_pattern"],
            use_gitignore=True,
        )

        # VCS dirs phai o dau tien
        for i, vcs in enumerate(VCS_DIRS):
            assert patterns[i] == vcs

        # User pattern phai truoc gitignore pattern
        user_idx = patterns.index("user_pattern")
        git_idx = patterns.index("from_gitignore")
        assert user_idx < git_idx


class TestBuildPathspec:
    """Test suite cho build_pathspec."""

    def test_tra_ve_pathspec(self, tmp_path: Path):
        """build_pathspec tra ve pathspec.PathSpec object."""
        import pathspec

        spec = build_pathspec(tmp_path, use_default_ignores=False, use_gitignore=False)
        assert isinstance(spec, pathspec.PathSpec)

    def test_match_vcs_dirs(self, tmp_path: Path):
        """PathSpec match VCS directories."""
        spec = build_pathspec(tmp_path, use_default_ignores=False, use_gitignore=False)
        assert spec.match_file(".git/")
        assert spec.match_file(".hg/")

    def test_match_gitignore_patterns(self, tmp_path: Path):
        """PathSpec match gitignore patterns."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.log\n")
        clear_cache()

        spec = build_pathspec(tmp_path, use_default_ignores=False, use_gitignore=True)
        assert spec.match_file("debug.log")
        assert not spec.match_file("main.py")


class TestReadGitignore:
    """Test suite cho read_gitignore."""

    def test_doc_gitignore(self, tmp_path: Path):
        """Doc .gitignore file thanh cong."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n__pycache__/\n# comment\n\n")
        clear_cache()

        patterns = read_gitignore(tmp_path)
        assert "*.pyc" in patterns
        assert "__pycache__/" in patterns
        assert "# comment" in patterns  # Raw lines - pathspec xu ly comments

    def test_khong_co_gitignore(self, tmp_path: Path):
        """Khong loi khi khong co .gitignore."""
        clear_cache()
        patterns = read_gitignore(tmp_path)
        # Van co the co patterns tu global gitignore
        assert isinstance(patterns, list)

    def test_doc_git_info_exclude(self, tmp_path: Path):
        """Doc .git/info/exclude neu co."""
        git_dir = tmp_path / ".git" / "info"
        git_dir.mkdir(parents=True)
        exclude = git_dir / "exclude"
        exclude.write_text("*.tmp\n")
        clear_cache()

        patterns = read_gitignore(tmp_path)
        assert "*.tmp" in patterns

    def test_cache_hoat_dong(self, tmp_path: Path):
        """Cache duoc su dung cho lan goi thu 2."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.log\n")
        clear_cache()

        patterns1 = read_gitignore(tmp_path)
        patterns2 = read_gitignore(tmp_path)
        assert patterns1 == patterns2


class TestFindGitRoot:
    """Test suite cho find_git_root."""

    def test_tim_git_root(self, tmp_path: Path):
        """Tim duoc .git directory."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        sub_dir = tmp_path / "src" / "core"
        sub_dir.mkdir(parents=True)

        root = find_git_root(sub_dir)
        assert root == tmp_path

    def test_khong_co_git(self, tmp_path: Path):
        """Tra ve start_path khi khong tim thay .git."""
        sub_dir = tmp_path / "no_git" / "deep"
        sub_dir.mkdir(parents=True)

        root = find_git_root(sub_dir)
        # Traverse len den root filesystem
        assert isinstance(root, Path)

    def test_git_root_la_path_hien_tai(self, tmp_path: Path):
        """Khi .git o ngay path hien tai."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        root = find_git_root(tmp_path)
        assert root == tmp_path


class TestClearCache:
    """Test suite cho clear_cache."""

    def test_clear_gitignore_cache(self, tmp_path: Path):
        """Clear cache khong loi."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.log\n")

        # Populate cache
        clear_cache()
        read_gitignore(tmp_path)

        # Clear - khong nen loi
        clear_cache()

        # Re-read should still work
        patterns = read_gitignore(tmp_path)
        assert "*.log" in patterns

    def test_clear_pathspec_cache(self, tmp_path: Path):
        """Clear pathspec cache khong loi."""
        clear_cache()
        build_pathspec(tmp_path, use_default_ignores=False, use_gitignore=False)
        clear_cache()
        # Should recreate without error
        build_pathspec(tmp_path, use_default_ignores=False, use_gitignore=False)
