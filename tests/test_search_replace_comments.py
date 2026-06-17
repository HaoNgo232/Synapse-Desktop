"""
Unit tests for SEARCH/REPLACE block comments and description parsing.
"""

from domain.prompt.opx_parser import parse_search_replace_response


class TestSearchReplaceComments:
    """Test cases for parsing inline comments/descriptions in SEARCH/REPLACE blocks."""

    def test_parse_with_description_modify(self):
        """Verify parsing a description/comment on a modify patch block."""
        text = """
<<<<<<< SEARCH src/hello.py - Sửa lỗi hiển thị UI và cập nhật logic
def old_hello():
    return "old"
=======
def new_hello():
    return "new"
>>>>>>> REPLACE
        """
        result = parse_search_replace_response(text)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 1

        action = result.file_actions[0]
        assert action.path == "src/hello.py"
        assert action.action == "modify"
        assert len(action.changes) == 1

        change = action.changes[0]
        assert change.description == "Sửa lỗi hiển thị UI và cập nhật logic"
        assert change.search == 'def old_hello():\n    return "old"'
        assert change.content == 'def new_hello():\n    return "new"'

    def test_parse_with_description_create(self):
        """Verify parsing a description/comment on a create file block."""
        text = """
<<<<<<< SEARCH src/new_file.py - Khởi tạo file mới với cấu hình mặc định
=======
print("File content")
>>>>>>> REPLACE
        """
        result = parse_search_replace_response(text)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 1

        action = result.file_actions[0]
        assert action.path == "src/new_file.py"
        assert action.action == "create"
        assert len(action.changes) == 1

        change = action.changes[0]
        assert change.description == "Khởi tạo file mới với cấu hình mặc định"
        assert change.search is None
        assert change.content == 'print("File content")'

    def test_parse_without_description_backward_compatibility(self):
        """Verify parsing works without description and falls back to default text."""
        text = """
<<<<<<< SEARCH src/app.py
x = 1
=======
x = 10
>>>>>>> REPLACE
        """
        result = parse_search_replace_response(text)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 1

        action = result.file_actions[0]
        assert action.path == "src/app.py"
        assert len(action.changes) == 1

        change = action.changes[0]
        assert change.description == "Search/Replace patch"

    def test_parse_with_special_characters_in_description(self):
        """Verify description parsing handles special characters (regex symbols, unicode, emojis) correctly."""
        text = """
<<<<<<< SEARCH src/main.py - Sửa hàm render() với regex: \w+ [a-z]* (như $1?!). 🎉
import sys
=======
import os
import sys
>>>>>>> REPLACE
        """
        result = parse_search_replace_response(text)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 1

        action = result.file_actions[0]
        change = action.changes[0]
        assert (
            change.description
            == "Sửa hàm render() với regex: \\w+ [a-z]* (như $1?!). 🎉"
        )

    def test_parse_with_space_but_no_comment(self):
        """Verify parser handles space and hyphen but empty description gracefully."""
        text = """
<<<<<<< SEARCH src/main.py - 
import sys
=======
import os
import sys
>>>>>>> REPLACE
        """
        result = parse_search_replace_response(text)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 1

        action = result.file_actions[0]
        change = action.changes[0]
        assert change.description == "Search/Replace patch"
