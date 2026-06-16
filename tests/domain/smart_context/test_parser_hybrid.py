import unittest
from domain.smart_context.parser import smart_parse


class TestParserHybrid(unittest.TestCase):
    def test_smart_parse_hybrid_python(self):
        content = """import os
from pathlib import Path
from domain.types import Symbol

@dataclass
class MyClass:
    \"\"\"A docstring.\"\"\"
    def my_method(self, name: str) -> None:
        print(f"Hello {name}")
        self._internal_call()

    def _internal_call(self):
        pass
"""
        file_path = "test.py"
        result = smart_parse(file_path, content)
        self.assertIsNotNone(result)
        if result:
            # Kiểm tra: Giữ lại imports
            self.assertIn("import os", result)
            self.assertIn("from pathlib import Path", result)
            self.assertIn("from domain.types import Symbol", result)

            # Kiểm tra: Có signatures của class và methods
            self.assertIn("class MyClass", result)
            self.assertIn("def my_method(self, name: str) -> None", result)

            # Kiểm tra: Có marker ⋮----
            self.assertIn("⋮----", result)

            # Kiểm tra: KHÔNG CÓ line numbers (L1-10)
            self.assertNotIn("(L", result)

            # Kiểm tra: KHÔNG CÓ call graph nội bộ (Internal relationships section)
            self.assertNotIn("## Relationships", result)
            self.assertNotIn("calls", result)

    def test_smart_parse_hybrid_ts(self):
        content = """import { Injectable } from '@nestjs/common';
import { Service } from './service';

@Injectable()
export class MyService {
  constructor(private readonly service: Service) {}

  async doSomething(id: string): Promise<void> {
    await this.service.call(id);
  }
}
"""
        file_path = "src/service.ts"
        result = smart_parse(file_path, content)
        self.assertIsNotNone(result)
        if result:
            # Kiểm tra imports
            self.assertIn("import { Injectable }", result)

            # Kiểm tra signatures
            self.assertIn("export class MyService", result)
            self.assertIn("async doSomething(id: string): Promise<void>", result)

            # Kiểm tra marker
            self.assertIn("⋮----", result)

    def test_smart_parse_hybrid_go(self):
        content = """package main

import (
	"fmt"
	"net/http"
)

// Main function
func main() {
	fmt.Println("Hello")
}
"""
        file_path = "main.go"
        result = smart_parse(file_path, content)
        self.assertIsNotNone(result)
        if result:
            # Kiểm tra imports (Go query) - raw import sau khi strip quote
            self.assertIn("fmt", result)
            self.assertIn("net/http", result)

            # Kiểm tra signatures
            self.assertIn("func main()", result)

            # Kiểm tra marker
            self.assertIn("⋮----", result)


class TestMultiLineImportExtraction(unittest.TestCase):
    """
    Regression tests cho bug: multi-line imports bị truncate thành 1 dòng.

    Trước khi fix, code dùng Relationship.source_line để lấy chỉ 1 dòng text,
    nên `from PySide6.QtWidgets import (` không bao gồm các items bên trong.
    Sau khi fix, dùng AST node.text để lấy toàn bộ import block.
    """

    def test_multiline_import_parentheses_preserved(self):
        """
        Bug regression: from X import (\\n    A,\\n    B,\\n) bị cắt thành 'from X import ('.
        Sau fix phải lấy đủ toàn bộ block.
        """
        content = """\
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
)
from typing import Optional

class MyClass:
    def my_method(self) -> None:
        pass
"""
        result = smart_parse("test.py", content)
        self.assertIsNotNone(result)
        assert result is not None

        # Import phải có đủ các items bên trong, không bị truncate
        self.assertIn("QWidget", result, "Multi-line import items must be preserved")
        self.assertIn("QVBoxLayout", result)
        self.assertIn("QLabel", result)

        # Dòng đầu của import phải được giữ
        self.assertIn("from PySide6.QtWidgets import (", result)

        # Dấu đóng ngoặc cũng phải có
        self.assertIn(")", result)

    def test_multiline_import_not_truncated_to_single_line(self):
        """Đảm bảo import không bị rút gọn thành 1 dòng duy nhất khi có nhiều items."""
        content = """\
from domain.config.model_config import (
    MODEL_CONFIGS,
    DEFAULT_MODEL_ID,
    get_model_by_id,
    ModelConfig,
)

def foo() -> None:
    pass
"""
        result = smart_parse("test.py", content)
        self.assertIsNotNone(result)
        assert result is not None

        self.assertIn("MODEL_CONFIGS", result)
        self.assertIn("DEFAULT_MODEL_ID", result)
        self.assertIn("get_model_by_id", result)
        self.assertIn("ModelConfig", result)

    def test_single_line_import_still_works(self):
        """Single-line imports vẫn hoạt động bình thường sau khi refactor."""
        content = """\
import os
from pathlib import Path
from typing import Optional, List

def bar() -> None:
    pass
"""
        result = smart_parse("test.py", content)
        self.assertIsNotNone(result)
        assert result is not None

        self.assertIn("import os", result)
        self.assertIn("from pathlib import Path", result)
        self.assertIn("from typing import Optional, List", result)

    def test_mixed_single_and_multiline_imports(self):
        """File có cả single-line và multi-line imports đều phải được extract đúng."""
        content = """\
import os
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
)
from typing import Optional

class Widget(QWidget):
    def __init__(self) -> None:
        super().__init__()
"""
        result = smart_parse("test.py", content)
        self.assertIsNotNone(result)
        assert result is not None

        # Single-line
        self.assertIn("import os", result)
        self.assertIn("from typing import Optional", result)

        # Multi-line
        self.assertIn("QWidget", result)
        self.assertIn("QLabel", result)

        # Signatures
        self.assertIn("class Widget", result)

    def test_import_order_preserved(self):
        """Imports phải xuất hiện trước class/function signatures trong output."""
        content = """\
from typing import Optional

class MyClass:
    def method(self) -> Optional[str]:
        return None
"""
        result = smart_parse("test.py", content)
        self.assertIsNotNone(result)
        assert result is not None

        import_pos = result.find("from typing import Optional")
        class_pos = result.find("class MyClass")

        self.assertGreater(import_pos, -1, "Import must be present")
        self.assertGreater(class_pos, -1, "Class must be present")
        self.assertLess(
            import_pos, class_pos, "Imports must appear before class definitions"
        )

    def test_empty_file_returns_none_or_empty(self):
        """File rỗng không được crash, trả về None hoặc empty string."""
        result = smart_parse("test.py", "")
        # Không crash là đủ; None hoặc empty string đều chấp nhận được
        self.assertTrue(result is None or result == "")

    def test_only_imports_no_crash(self):
        """File chỉ có imports (như __init__.py) không được crash."""
        content = """\
from .module_a import ClassA
from .module_b import ClassB
"""
        result = smart_parse("__init__.py", content)
        # Không crash; kết quả có thể là None hoặc chứa imports
        if result:
            self.assertIn("ClassA", result)
            self.assertIn("ClassB", result)


class TestExtractImportTextsHelper(unittest.TestCase):
    """Unit tests cho hàm helper _extract_import_texts."""

    def _parse_tree(self, content: str):
        """Helper: parse Python content thành tree-sitter tree."""
        from domain.smart_context.loader import get_language
        from tree_sitter import Parser

        language = get_language("py")
        parser = Parser(language)
        return parser.parse(bytes(content, "utf-8"))

    def test_extracts_single_line_import(self):
        from domain.smart_context.parser import _extract_import_texts

        content = "import os\n"
        tree = self._parse_tree(content)
        results = _extract_import_texts(tree, content)
        self.assertIn("import os", results)

    def test_extracts_multiline_import_fully(self):
        from domain.smart_context.parser import _extract_import_texts

        content = "from PySide6.QtWidgets import (\n    QWidget,\n    QLabel,\n)\n"
        tree = self._parse_tree(content)
        results = _extract_import_texts(tree, content)

        self.assertEqual(len(results), 1)
        self.assertIn("QWidget", results[0])
        self.assertIn("QLabel", results[0])
        self.assertIn("from PySide6.QtWidgets import (", results[0])

    def test_no_duplicates(self):
        """Mỗi import chỉ xuất hiện một lần dù walk nhiều node."""
        from domain.smart_context.parser import _extract_import_texts

        content = "import os\nimport sys\n"
        tree = self._parse_tree(content)
        results = _extract_import_texts(tree, content)

        self.assertEqual(len(results), 2)
        self.assertIn("import os", results)
        self.assertIn("import sys", results)

    def test_empty_content_returns_empty_list(self):
        from domain.smart_context.parser import _extract_import_texts

        content = ""
        tree = self._parse_tree(content)
        results = _extract_import_texts(tree, content)
        self.assertEqual(results, [])

    def test_no_imports_returns_empty_list(self):
        from domain.smart_context.parser import _extract_import_texts

        content = "def foo():\n    pass\n"
        tree = self._parse_tree(content)
        results = _extract_import_texts(tree, content)
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
