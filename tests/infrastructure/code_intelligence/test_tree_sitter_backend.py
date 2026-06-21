import unittest
from pathlib import Path
from infrastructure.adapters.code_intelligence.tree_sitter_backend import TreeSitterBackend

class TestTreeSitterBackend(unittest.TestCase):
    def test_supported_extensions(self):
        backend = TreeSitterBackend()
        self.assertIn("py", backend.get_supported_extensions())

    def test_parse_tree_sitter_python(self):
        backend = TreeSitterBackend()
        content = "def sample():\n    pass\n"
        result = backend.parse_file(Path("sample.py"), content)
        self.assertIsNotNone(result)
        if result:
            self.assertEqual(result.language, "py")
            self.assertTrue(len(result.symbols) > 0)
