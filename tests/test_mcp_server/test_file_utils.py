"""
Tests cho mcp_server/utils/file_utils.py

Kiem tra atomic_write dam bao:
- Ghi file thanh cong khong mat du lieu
- Khong de lai file tam khi loi
- Hoat dong dung khi path parent ton tai
"""

import pytest

from mcp_server.utils.file_utils import atomic_write


class TestAtomicWrite:
    """Kiem tra atomic_write ghi file an toan."""

    def test_write_new_file(self, tmp_path):
        """Ghi file moi thanh cong."""
        target = tmp_path / "output.json"
        data = '{"key": "value"}'

        atomic_write(target, data)

        assert target.exists()
        assert target.read_text() == data

    def test_overwrite_existing_file(self, tmp_path):
        """Ghi de file da ton tai."""
        target = tmp_path / "output.json"
        target.write_text("old content")

        atomic_write(target, "new content")

        assert target.read_text() == "new content"

    def test_no_temp_files_left_on_success(self, tmp_path):
        """Khong con file .tmp sau khi ghi thanh cong."""
        target = tmp_path / "output.json"
        atomic_write(target, "data")

        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_preserves_unicode_content(self, tmp_path):
        """Bao toan noi dung Unicode (tieng Viet, emoji...)."""
        target = tmp_path / "unicode.txt"
        content = "Xin chào thế giới! Tiếng Việt có dấu."

        atomic_write(target, content)

        assert target.read_text(encoding="utf-8") == content

    def test_empty_content(self, tmp_path):
        """Ghi file rong van thanh cong."""
        target = tmp_path / "empty.txt"

        atomic_write(target, "")

        assert target.exists()
        assert target.read_text() == ""

    def test_parent_dir_must_exist(self, tmp_path):
        """Ghi vao thu muc khong ton tai -> loi (atomic_write khong tu tao parent)."""
        target = tmp_path / "nonexistent_dir" / "file.txt"

        with pytest.raises(Exception):
            atomic_write(target, "data")

    def test_large_content(self, tmp_path):
        """Ghi file lon van dung."""
        target = tmp_path / "large.txt"
        content = "x" * (1024 * 1024)  # 1MB

        atomic_write(target, content)

        assert target.read_text() == content
