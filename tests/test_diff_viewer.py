"""
Unit tests cho DiffViewer component va diff generation functions.

Test cac case:
- generate_diff_lines() voi modify
- generate_create_diff_lines() voi new file
- generate_delete_diff_lines() voi delete file
- DiffLine types va colors
"""

import pytest
from components.diff_viewer import (
    generate_diff_lines,
    generate_create_diff_lines,
    generate_delete_diff_lines,
    DiffLineType,
)


class TestGenerateDiffLines:
    """Test generate_diff_lines() function"""

    def test_simple_modification(self):
        """Test diff cho mot thay doi don gian"""
        old_content = "line1\nold_line\nline3"
        new_content = "line1\nnew_line\nline3"

        result = generate_diff_lines(old_content, new_content)

        # Kiem tra co it nhat 1 ADDED va 1 REMOVED
        added_lines = [ln for ln in result if ln.line_type == DiffLineType.ADDED]
        removed_lines = [ln for ln in result if ln.line_type == DiffLineType.REMOVED]

        assert len(added_lines) >= 1
        assert len(removed_lines) >= 1

        # Kiem tra content
        assert any("new_line" in ln.content for ln in added_lines)
        assert any("old_line" in ln.content for ln in removed_lines)

    def test_addition_only(self):
        """Test diff khi chi them dong moi"""
        old_content = "line1\nline2"
        new_content = "line1\nline2\nline3"

        result = generate_diff_lines(old_content, new_content)

        added_lines = [ln for ln in result if ln.line_type == DiffLineType.ADDED]

        # Phai co it nhat 1 dong duoc them
        assert len(added_lines) >= 1

    def test_deletion_only(self):
        """Test diff khi chi xoa dong"""
        old_content = "line1\nline2\nline3"
        new_content = "line1\nline2"

        result = generate_diff_lines(old_content, new_content)

        removed_lines = [ln for ln in result if ln.line_type == DiffLineType.REMOVED]

        # Phai co it nhat 1 dong bi xoa
        assert len(removed_lines) >= 1

    def test_empty_old_content(self):
        """Test diff khi old content rong (new file)"""
        old_content = ""
        new_content = "new line 1\nnew line 2"

        result = generate_diff_lines(old_content, new_content)

        # Tat ca lines moi phai la ADDED
        added_lines = [ln for ln in result if ln.line_type == DiffLineType.ADDED]
        assert len(added_lines) >= 2

    def test_empty_new_content(self):
        """Test diff khi new content rong (delete file)"""
        old_content = "old line 1\nold line 2"
        new_content = ""

        result = generate_diff_lines(old_content, new_content)

        # Tat ca lines cu phai la REMOVED
        removed_lines = [ln for ln in result if ln.line_type == DiffLineType.REMOVED]
        assert len(removed_lines) >= 2

    def test_no_changes(self):
        """Test diff khi khong co thay doi"""
        content = "line1\nline2\nline3"

        result = generate_diff_lines(content, content)

        # Khong co ADDED hoac REMOVED
        added_lines = [ln for ln in result if ln.line_type == DiffLineType.ADDED]
        removed_lines = [ln for ln in result if ln.line_type == DiffLineType.REMOVED]

        assert len(added_lines) == 0
        assert len(removed_lines) == 0


class TestGenerateCreateDiffLines:
    """Test generate_create_diff_lines() function"""

    def test_create_simple_file(self):
        """Test diff cho file moi"""
        content = "def hello():\n    return 'world'"

        result = generate_create_diff_lines(content, "test.py")

        # Tat ca lines phai la ADDED
        added_lines = [ln for ln in result if ln.line_type == DiffLineType.ADDED]
        assert len(added_lines) >= 2

        # Kiem tra content
        assert any("def hello" in ln.content for ln in added_lines)

    def test_create_empty_file(self):
        """Test diff cho file rong"""
        result = generate_create_diff_lines("", "empty.txt")

        # Khong co lines nao
        assert len(result) == 0


class TestGenerateDeleteDiffLines:
    """Test generate_delete_diff_lines() function"""

    def test_delete_simple_file(self):
        """Test diff cho xoa file"""
        content = "old content\nto be deleted"

        result = generate_delete_diff_lines(content, "old.py")

        # Tat ca lines phai la REMOVED
        removed_lines = [ln for ln in result if ln.line_type == DiffLineType.REMOVED]
        assert len(removed_lines) >= 2

    def test_delete_empty_file(self):
        """Test diff khi xoa file rong"""
        result = generate_delete_diff_lines("", "empty.txt")

        # Khong co lines nao
        assert len(result) == 0


class TestDiffLineType:
    """Test DiffLineType enum"""

    def test_line_types(self):
        """Verify all line types exist"""
        assert DiffLineType.ADDED.value == "added"
        assert DiffLineType.REMOVED.value == "removed"
        assert DiffLineType.CONTEXT.value == "context"
        assert DiffLineType.HEADER.value == "header"


class TestDiffLineNumbers:
    """Test line number tracking trong diff"""

    def test_line_numbers_for_added(self):
        """Test new_line_no duoc set cho ADDED lines"""
        old_content = "line1"
        new_content = "line1\nline2"

        result = generate_diff_lines(old_content, new_content)

        added_lines = [ln for ln in result if ln.line_type == DiffLineType.ADDED]
        for line in added_lines:
            assert line.new_line_no is not None
            assert line.old_line_no is None

    def test_line_numbers_for_removed(self):
        """Test old_line_no duoc set cho REMOVED lines"""
        old_content = "line1\nline2"
        new_content = "line1"

        result = generate_diff_lines(old_content, new_content)

        removed_lines = [ln for ln in result if ln.line_type == DiffLineType.REMOVED]
        for line in removed_lines:
            assert line.old_line_no is not None
            assert line.new_line_no is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
