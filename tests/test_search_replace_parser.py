"""
Unit tests cho bộ phân tích định dạng Search/Replace (Aider-style)
"""

from domain.prompt.opx_parser import (
    parse_search_replace_response,
    parse_any_response,
)


class TestSearchReplaceParser:
    """Các trường hợp kiểm thử cho bộ phân tích Search/Replace (Aider-style)"""

    def test_parse_simple_modify(self):
        """Phân tích một thay đổi (modify) đơn giản"""
        text = """
<<<<<<< SEARCH src/hello.py
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
        assert change.search == 'def old_hello():\n    return "old"'
        assert change.content == 'def new_hello():\n    return "new"'

    def test_parse_simple_create(self):
        """Phân tích một hành động tạo file mới (SEARCH block trống)"""
        text = """
<<<<<<< SEARCH src/new_file.py
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
        assert change.search is None
        assert change.content == 'print("File content")'

    def test_parse_multiple_blocks_same_file(self):
        """Kiểm tra gom nhóm nhiều block thay đổi trong cùng một file"""
        text = """
<<<<<<< SEARCH src/app.py
x = 1
=======
x = 10
>>>>>>> REPLACE

Nội dung mô tả trung gian.

<<<<<<< SEARCH src/app.py
y = 2
=======
y = 20
>>>>>>> REPLACE
        """
        result = parse_search_replace_response(text)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 1

        action = result.file_actions[0]
        assert action.path == "src/app.py"
        assert action.action == "modify"
        assert len(action.changes) == 2

        assert action.changes[0].search == "x = 1"
        assert action.changes[0].content == "x = 10"
        assert action.changes[1].search == "y = 2"
        assert action.changes[1].content == "y = 20"

    def test_parse_multiple_files(self):
        """Phân tích các thay đổi trên nhiều file khác nhau"""
        text = """
<<<<<<< SEARCH src/a.py
a = 1
=======
a = 2
>>>>>>> REPLACE

<<<<<<< SEARCH src/b.py
b = 1
=======
b = 2
>>>>>>> REPLACE
        """
        result = parse_search_replace_response(text)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 2

        paths = {action.path for action in result.file_actions}
        assert paths == {"src/a.py", "src/b.py"}

    def test_parse_errors(self):
        """Trường hợp dữ liệu đầu vào không hợp lệ hoặc thiếu Search/Replace block"""
        result = parse_search_replace_response("Không có gì ở đây cả")
        assert len(result.errors) > 0
        assert len(result.file_actions) == 0

    def test_parse_with_carriage_returns(self):
        """Kiểm tra xử lý ký tự xuống dòng dạng Windows \\r\\n"""
        text = "<<<<<<< SEARCH src/app.py\r\nold_code\r\n=======\r\nnew_code\r\n>>>>>>> REPLACE\r\n"
        result = parse_search_replace_response(text)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 1
        action = result.file_actions[0]
        assert action.changes[0].search == "old_code"
        assert action.changes[0].content == "new_code"

    def test_parse_with_markdown_fences(self):
        """Xử lý block Search/Replace nằm bên trong code block Markdown"""
        text = """
```python
<<<<<<< SEARCH src/app.py
old
=======
new
>>>>>>> REPLACE
```
        """
        result = parse_search_replace_response(text)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 1
        assert result.file_actions[0].changes[0].search == "old"
        assert result.file_actions[0].changes[0].content == "new"


class TestParseAnyResponse:
    """Kiểm thử hàm nhận diện tự động parse_any_response"""

    def test_detect_and_parse_opx(self):
        """Nhận diện và phân tích thành công định dạng OPX"""
        xml = """
        <edit file="src/utils/hello.py" op="new">
            <put>
<<<
def hello():
    return "Hello"
>>>
            </put>
        </edit>
        """
        result = parse_any_response(xml)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 1
        assert result.file_actions[0].path == "src/utils/hello.py"
        assert result.file_actions[0].action == "create"

    def test_detect_and_parse_search_replace(self):
        """Nhận diện và phân tích thành công định dạng Search/Replace"""
        text = """
<<<<<<< SEARCH src/hello.py
def old():
    pass
=======
def new():
    pass
>>>>>>> REPLACE
        """
        result = parse_any_response(text)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 1
        assert result.file_actions[0].path == "src/hello.py"
        assert result.file_actions[0].action == "modify"

    def test_parse_any_invalid_format(self):
        """Trả về lỗi khi không khớp bất kỳ định dạng nào"""
        result = parse_any_response("Random text without matches")
        assert len(result.errors) > 0
        assert len(result.file_actions) == 0
