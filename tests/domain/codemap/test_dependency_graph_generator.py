import unittest
from pathlib import Path
from unittest.mock import patch
from domain.codemap.dependency_graph_generator import DependencyGraphGenerator


class TestDependencyGraphGenerator(unittest.TestCase):
    def setUp(self):
        self.workspace_root = Path("/home/hao/Desktop/labs/Synapse-Desktop")

        # Patch DependencyResolver before initializing generator
        with patch(
            "domain.codemap.dependency_graph_generator.DependencyResolver"
        ) as mock_resolver_cls:
            self.mock_resolver = mock_resolver_cls.return_value
            self.generator = DependencyGraphGenerator(self.workspace_root)

    def test_generate_graph_simple(self):
        # Giả lập quan hệ dependency
        file_a = str(self.workspace_root / "src/a.py")
        file_b = str(self.workspace_root / "src/b.py")
        file_c = str(self.workspace_root / "src/c.py")

        # Mock get_related_files for each file
        def mock_get_related(path_obj):
            path_str = str(path_obj)
            if path_str == file_a:
                return {Path(file_b), Path(file_c)}
            elif path_str == file_b:
                return {Path(file_c)}
            return set()

        self.mock_resolver.get_related_files.side_effect = mock_get_related

        # Giả lập nội dung file (key trong dict)
        file_contents = {file_a: "content a", file_b: "content b", file_c: "content c"}

        # Thực hiện generate
        graph_output = self.generator.generate_graph(file_contents)

        # Kiểm tra output format
        # Thứ tự file_b, file_c trong file_a dep nên được sorted
        expected_output = """# Dependency Graph

src/a.py
  \u2192 src/b.py
  \u2192 src/c.py

src/b.py
  \u2192 src/c.py"""

        self.assertEqual(graph_output.strip(), expected_output.strip())

    def test_generate_graph_with_relative_paths(self):
        # Đảm bảo đường dẫn hiển thị là relative từ workspace root và dùng forward slash
        file_a = str(self.workspace_root / "src/subdir/a.py")
        file_b = str(self.workspace_root / "src/utils.py")

        self.mock_resolver.get_related_files.return_value = {Path(file_b)}

        file_contents = {file_a: "content"}
        graph_output = self.generator.generate_graph(file_contents)

        expected_line = "src/subdir/a.py"
        expected_dep = "  \u2192 src/utils.py"

        self.assertIn(expected_line, graph_output)
        self.assertIn(expected_dep, graph_output)


if __name__ == "__main__":
    unittest.main()
