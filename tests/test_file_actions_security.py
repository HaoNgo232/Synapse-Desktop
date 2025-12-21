import unittest
from pathlib import Path
import tempfile
import shutil
import os
from core.file_actions import apply_file_actions, _resolve_path, FileAction, ChangeBlock


class TestFileActionsSecurity(unittest.TestCase):
    def setUp(self):
        # Create a temporary workspace
        self.test_dir = tempfile.mkdtemp()
        self.workspace_root = Path(self.test_dir)
        self.workspace_roots = [self.workspace_root]

        # Create a file inside workspace
        self.file_path = self.workspace_root / "test.txt"
        self.file_path.write_text("Original Content")

        # Create a file OUTSIDE workspace
        self.outside_dir = tempfile.mkdtemp()
        self.outside_file = Path(self.outside_dir) / "hack.txt"
        self.outside_file.write_text("Secret Data")

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        shutil.rmtree(self.outside_dir)

    def test_path_traversal_prevention(self):
        """Test blocking access to files outside workspace"""
        # Try to access a file outside using relative path traversal
        # Calculates relative path from workspace to outside file
        rel_path = os.path.relpath(self.outside_file, self.workspace_root)

        # Sanity check: ensure it starts with ..
        self.assertTrue(rel_path.startswith(".."))

        # Try to resolve malicious path
        with self.assertRaises(ValueError) as cm:
            _resolve_path(rel_path, None, self.workspace_roots)

        self.assertIn("Access denied", str(cm.exception))
        self.assertIn("outside workspace", str(cm.exception))

    def test_dry_run_create(self):
        """Test dry run does not create files"""
        new_file = "new_file.txt"
        action = FileAction(
            path=new_file,
            action="create",
            changes=[ChangeBlock(content="New Content", description="Create file")],
        )

        results = apply_file_actions([action], self.workspace_roots, dry_run=True)

        # Should succeed in logic
        self.assertTrue(results[0].success)
        self.assertIn("Dry Run", results[0].message)

        # But should NOT exist on disk
        self.assertFalse((self.workspace_root / new_file).exists())

    def test_dry_run_modify(self):
        """Test dry run does not modify files"""
        action = FileAction(
            path="test.txt",
            action="modify",
            changes=[
                ChangeBlock(
                    search="Original", content="Modified", description="Update content"
                )
            ],
        )

        results = apply_file_actions([action], self.workspace_roots, dry_run=True)

        self.assertTrue(results[0].success)
        self.assertIn("Dry Run", results[0].message)

        # Content should be UNCHANGED
        self.assertEqual(self.file_path.read_text(), "Original Content")

    def test_dry_run_delete(self):
        """Test dry run does not delete files"""
        action = FileAction(path="test.txt", action="delete")

        results = apply_file_actions([action], self.workspace_roots, dry_run=True)

        self.assertTrue(results[0].success)
        self.assertIn("Dry Run", results[0].message)

        # File should still EXIST
        self.assertTrue(self.file_path.exists())


if __name__ == "__main__":
    unittest.main()
