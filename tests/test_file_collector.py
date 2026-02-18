"""
Unit tests cho file_collector module.

Test cac case:
- collect_files(): Thu thap files tu disk
- FileEntry: Dataclass dai dien cho file da doc
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from core.prompting.file_collector import collect_files
from core.prompting.types import FileEntry


class TestCollectFilesBasic:
    """Test collect_files() voi cac case co ban."""

    def test_empty_set(self):
        """Empty set tra ve empty list."""
        result = collect_files(set())
        assert result == []

    def test_single_text_file(self, tmp_path):
        """Doc 1 file text thanh cong."""
        f = tmp_path / "hello.py"
        f.write_text("print('hello')", encoding="utf-8")

        result = collect_files({str(f)})
        assert len(result) == 1
        entry = result[0]
        assert entry.content == "print('hello')"
        assert entry.error is None
        assert entry.language == "python"

    def test_multiple_files_sorted(self, tmp_path):
        """Nhieu files tra ve theo thu tu sorted."""
        b = tmp_path / "b.py"
        a = tmp_path / "a.py"
        b.write_text("b", encoding="utf-8")
        a.write_text("a", encoding="utf-8")

        result = collect_files({str(b), str(a)})
        assert len(result) == 2
        # Kiem tra thu tu sorted
        assert "a.py" in result[0].display_path
        assert "b.py" in result[1].display_path

    def test_empty_file(self, tmp_path):
        """File rong co content="" va khong co error."""
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")

        result = collect_files({str(f)})
        assert len(result) == 1
        assert result[0].content == ""
        assert result[0].error is None

    def test_nonexistent_file_skipped(self, tmp_path):
        """File khong ton tai bi skip (khong co entry)."""
        result = collect_files({str(tmp_path / "nonexistent.py")})
        # is_file() returns False -> skip, khong them entry
        assert result == []

    def test_directory_skipped(self, tmp_path):
        """Directory bi skip (khong co entry)."""
        d = tmp_path / "subdir"
        d.mkdir()
        result = collect_files({str(d)})
        assert result == []


class TestCollectFilesBinary:
    """Test collect_files() voi binary files."""

    def test_binary_file_detected(self, tmp_path):
        """Binary file co error='Binary file'."""
        f = tmp_path / "image.png"
        # Viet PNG magic bytes
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        result = collect_files({str(f)})
        assert len(result) == 1
        assert result[0].content is None
        assert result[0].error == "Binary file"

    def test_binary_by_null_bytes(self, tmp_path):
        """File chua null bytes bi phat hien la binary."""
        f = tmp_path / "data.bin"
        f.write_bytes(b"some\x00binary\x00data")

        result = collect_files({str(f)})
        assert len(result) == 1
        assert result[0].content is None
        assert result[0].error == "Binary file"


class TestCollectFilesSize:
    """Test collect_files() voi file size limits."""

    def test_file_too_large(self, tmp_path):
        """File qua lon co error chua size."""
        f = tmp_path / "big.txt"
        # Tao file 2KB, set max = 1KB
        f.write_text("x" * 2048, encoding="utf-8")

        result = collect_files({str(f)}, max_file_size=1024)
        assert len(result) == 1
        assert result[0].content is None
        assert "File too large" in result[0].error
        assert "2KB" in result[0].error or "1KB" in result[0].error

    def test_file_at_limit_included(self, tmp_path):
        """File dung bang limit van duoc doc."""
        f = tmp_path / "exact.txt"
        content = "x" * 1024
        f.write_text(content, encoding="utf-8")

        result = collect_files({str(f)}, max_file_size=1024)
        assert len(result) == 1
        assert result[0].content == content
        assert result[0].error is None


class TestCollectFilesRelativePaths:
    """Test collect_files() voi relative path display."""

    def test_relative_path_display(self, tmp_path):
        """Khi use_relative_paths=True, display_path la relative."""
        sub = tmp_path / "src"
        sub.mkdir()
        f = sub / "main.py"
        f.write_text("pass", encoding="utf-8")

        result = collect_files(
            {str(f)},
            workspace_root=tmp_path,
            use_relative_paths=True,
        )
        assert len(result) == 1
        assert result[0].display_path == "src/main.py"

    def test_absolute_path_display(self, tmp_path):
        """Khi use_relative_paths=False, display_path la absolute."""
        f = tmp_path / "main.py"
        f.write_text("pass", encoding="utf-8")

        result = collect_files(
            {str(f)},
            workspace_root=tmp_path,
            use_relative_paths=False,
        )
        assert len(result) == 1
        # Absolute path chua tmp_path
        assert str(tmp_path) in result[0].display_path


class TestCollectFilesErrorHandling:
    """Test collect_files() xu ly loi doc file."""

    def test_oserror_during_read(self, tmp_path):
        """OSError khi doc content tra ve FileEntry voi error."""
        f = tmp_path / "unreadable.py"
        f.write_text("content", encoding="utf-8")

        with patch.object(Path, "read_text", side_effect=OSError("Permission denied")):
            result = collect_files({str(f)})

        assert len(result) == 1
        assert result[0].content is None
        assert "Error reading file" in result[0].error


class TestFileEntryDataclass:
    """Test FileEntry dataclass properties."""

    def test_frozen(self):
        """FileEntry la immutable (frozen)."""
        entry = FileEntry(
            path=Path("/test"),
            display_path="test",
            content="hello",
            error=None,
            language="python",
        )
        with pytest.raises(AttributeError):
            entry.content = "modified"

    def test_equality(self):
        """FileEntry equality dua tren gia tri."""
        e1 = FileEntry(
            path=Path("/test"),
            display_path="test",
            content="hello",
            error=None,
            language="python",
        )
        e2 = FileEntry(
            path=Path("/test"),
            display_path="test",
            content="hello",
            error=None,
            language="python",
        )
        assert e1 == e2
