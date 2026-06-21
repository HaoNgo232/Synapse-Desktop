import unittest
from pathlib import Path
from infrastructure.adapters.code_intelligence.python_ast_backend import PythonAstBackend

class TestPythonAstBackend(unittest.TestCase):
    def test_supported_extensions(self):
        backend = PythonAstBackend()
        self.assertIn("py", backend.get_supported_extensions())

    def test_parse_python_file(self):
        backend = PythonAstBackend()
        content = "def test_func(x, y):\n    return x + y\n"
        result = backend.parse_file(Path("hello.py"), content)
        self.assertIsNotNone(result)
        if result:
            self.assertEqual(result.language, "py")
            self.assertIn("def test_func(x, y)", result.outline)
