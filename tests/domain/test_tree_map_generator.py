import unittest
from pathlib import Path
from domain.smart_context.tree_item import TreeItem
from domain.codemap.tree_map_generator import (
    generate_tree_map_only,
    generate_tree_map_with_summary,
    tree_item_is_dir,
    _tree_contains_path,
)


class TestTreeMapGenerator(unittest.TestCase):
    def setUp(self):
        # Thiết lập cấu trúc file tree giả lập:
        # root (dir, path="/workspace")
        #  ├── src (dir, path="/workspace/src")
        #  │    └── main.py (file, path="/workspace/src/main.py")
        #  └── README.md (file, path="/workspace/README.md")
        self.dir_subdir = TreeItem(
            label="subdir",
            path="/workspace/src/subdir",
            is_dir=True,
            children=[],
        )
        self.file_main = TreeItem(label="main.py", path="/workspace/src/main.py", is_dir=False)
        self.dir_src = TreeItem(
            label="src",
            path="/workspace/src",
            is_dir=True,
            children=[self.file_main, self.dir_subdir],
        )
        self.file_readme = TreeItem(
            label="README.md", path="/workspace/README.md", is_dir=False
        )
        self.root = TreeItem(
            label="root",
            path="/workspace",
            is_dir=True,
            children=[self.dir_src, self.file_readme],
        )

        self.workspace_root = Path("/workspace")

    def test_generate_tree_map_only(self):
        selected = {"/workspace/src/main.py", "/workspace/README.md"}
        prompt = generate_tree_map_only(
            tree=self.root,
            selected_paths=selected,
            user_instructions="Please look at this map",
            workspace_root=self.workspace_root,
            use_relative_paths=True,
        )
        self.assertIn("<file_map>", prompt)
        self.assertIn("main.py", prompt)
        self.assertIn("src", prompt)
        self.assertIn("README.md", prompt)
        self.assertIn("<user_instructions>", prompt)
        self.assertIn("Please look at this map", prompt)

    def test_generate_tree_map_only_empty_instructions(self):
        selected = {"/workspace/src/main.py"}
        prompt = generate_tree_map_only(
            tree=self.root,
            selected_paths=selected,
            workspace_root=self.workspace_root,
            use_relative_paths=True,
        )
        self.assertIn("<file_map>", prompt)
        self.assertNotIn("<user_instructions>", prompt)

    def test_generate_tree_map_with_summary(self):
        # Test generate_tree_map_with_summary
        selected = {
            "/workspace/src/main.py",
            "/workspace/src",
            "/workspace/README.md",
        }
        prompt = generate_tree_map_with_summary(
            tree=self.root,
            selected_paths=selected,
            user_instructions="Fix bug",
            workspace_root=self.workspace_root,
            use_relative_paths=True,
        )
        self.assertIn("<file_map>", prompt)
        self.assertIn("<summary>", prompt)
        # 2 files: main.py, README.md; 1 folder: src
        self.assertIn("Selected: 2 files, 1 folders", prompt)
        self.assertIn("<user_instructions>", prompt)
        self.assertIn("Fix bug", prompt)

    def test_generate_tree_map_with_summary_no_instructions(self):
        selected = {"/workspace/src/main.py"}
        prompt = generate_tree_map_with_summary(
            tree=self.root,
            selected_paths=selected,
            workspace_root=self.workspace_root,
            use_relative_paths=True,
        )
        self.assertIn("<file_map>", prompt)
        self.assertIn("Selected: 1 files, 0 folders", prompt)
        self.assertNotIn("<user_instructions>", prompt)

    def test_tree_item_is_dir_with_map(self):
        # Có maps
        is_dir_map = {
            "/workspace": True,
            "/workspace/src": True,
            "/workspace/src/main.py": False,
            "/workspace/README.md": False,
        }
        self.assertTrue(tree_item_is_dir(self.root, "/workspace/src", is_dir_map))
        self.assertFalse(
            tree_item_is_dir(self.root, "/workspace/src/main.py", is_dir_map)
        )
        self.assertFalse(
            tree_item_is_dir(self.root, "/workspace/not_exists", is_dir_map)
        )

    def test_tree_item_is_dir_fallback(self):
        # Không map, fallback đệ quy
        # Root check
        self.assertTrue(tree_item_is_dir(self.root, "/workspace"))
        # Con trực tiếp (file)
        self.assertFalse(tree_item_is_dir(self.root, "/workspace/README.md"))
        # Con trực tiếp (dir)
        self.assertTrue(tree_item_is_dir(self.root, "/workspace/src"))
        # Cháu (dir trong dir)
        self.assertTrue(tree_item_is_dir(self.root, "/workspace/src/subdir"))
        # Cháu (file trong dir)
        self.assertFalse(tree_item_is_dir(self.root, "/workspace/src/main.py"))
        # Không tồn tại
        self.assertFalse(tree_item_is_dir(self.root, "/workspace/not_exists"))

    def test_tree_contains_path(self):
        # Test helper _tree_contains_path trực tiếp để đạt 100% coverage
        self.assertTrue(_tree_contains_path(self.root, "/workspace"))
        self.assertTrue(_tree_contains_path(self.root, "/workspace/src/main.py"))
        self.assertFalse(_tree_contains_path(self.root, "/workspace/not_exists"))


if __name__ == "__main__":
    unittest.main()
