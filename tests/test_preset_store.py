"""Tests for PresetStore."""

import pytest
from pathlib import Path
from services.preset_store import PresetStore, PRESET_FILENAME


@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "src").mkdir()
    (workspace / "src" / "main.py").write_text("print('hello')")
    (workspace / "src" / "utils.py").write_text("def helper(): pass")
    return workspace


@pytest.fixture
def store(temp_workspace):
    """Create PresetStore instance."""
    return PresetStore(temp_workspace)


class TestPresetStore:
    def test_create_preset(self, store, temp_workspace):
        """Test creating a new preset."""
        paths = [
            str(temp_workspace / "src" / "main.py"),
            str(temp_workspace / "src" / "utils.py"),
        ]

        entry = store.create_preset(
            name="Test Preset",
            selected_paths=paths,
            instructions="Test instructions",
            output_format="xml",
        )

        assert entry.name == "Test Preset"
        assert len(entry.selected_paths) == 2
        assert entry.instructions == "Test instructions"
        assert entry.output_format == "xml"
        assert entry.created_at
        assert entry.updated_at

        # Verify relative paths
        assert "src/main.py" in entry.selected_paths
        assert "src/utils.py" in entry.selected_paths

    def test_list_presets(self, store, temp_workspace):
        """Test listing presets sorted by updated_at."""
        paths = [str(temp_workspace / "src" / "main.py")]

        entry1 = store.create_preset("First", paths)
        entry2 = store.create_preset("Second", paths)

        presets = store.list_presets()
        assert len(presets) == 2
        # Most recent first
        assert presets[0].preset_id == entry2.preset_id
        assert presets[1].preset_id == entry1.preset_id

    def test_get_preset(self, store, temp_workspace):
        """Test getting preset by ID."""
        paths = [str(temp_workspace / "src" / "main.py")]
        entry = store.create_preset("Test", paths)

        retrieved = store.get_preset(entry.preset_id)
        assert retrieved is not None
        assert retrieved.preset_id == entry.preset_id
        assert retrieved.name == "Test"

        # Non-existent ID
        assert store.get_preset("invalid-id") is None

    def test_update_preset(self, store, temp_workspace):
        """Test updating preset."""
        paths = [str(temp_workspace / "src" / "main.py")]
        entry = store.create_preset("Original", paths)

        updated = store.update_preset(
            entry.preset_id,
            name="Updated",
            instructions="New instructions",
        )

        assert updated is not None
        assert updated.name == "Updated"
        assert updated.instructions == "New instructions"
        assert updated.selected_paths == entry.selected_paths  # Unchanged
        assert updated.updated_at >= entry.updated_at  # May be same if very fast

    def test_delete_preset(self, store, temp_workspace):
        """Test deleting preset."""
        paths = [str(temp_workspace / "src" / "main.py")]
        entry = store.create_preset("Test", paths)

        assert store.delete_preset(entry.preset_id) is True
        assert store.get_preset(entry.preset_id) is None

        # Delete non-existent
        assert store.delete_preset("invalid-id") is False

    def test_rename_preset(self, store, temp_workspace):
        """Test renaming preset."""
        paths = [str(temp_workspace / "src" / "main.py")]
        entry = store.create_preset("Old Name", paths)

        renamed = store.rename_preset(entry.preset_id, "New Name")
        assert renamed is not None
        assert renamed.name == "New Name"

    def test_to_absolute_paths(self, store, temp_workspace):
        """Test converting relative to absolute paths."""
        paths = [str(temp_workspace / "src" / "main.py")]
        entry = store.create_preset("Test", paths)

        absolute = store.to_absolute_paths(entry.selected_paths)
        assert len(absolute) == 1
        assert Path(absolute[0]).is_absolute()
        assert Path(absolute[0]).exists()

    def test_to_absolute_paths_missing_files(self, store, temp_workspace):
        """Test filtering out non-existent files."""
        paths = [str(temp_workspace / "src" / "main.py")]
        entry = store.create_preset("Test", paths)

        # Delete file
        (temp_workspace / "src" / "main.py").unlink()

        absolute = store.to_absolute_paths(entry.selected_paths)
        assert len(absolute) == 0  # Filtered out

    def test_persistence(self, store, temp_workspace):
        """Test that presets persist across store instances."""
        paths = [str(temp_workspace / "src" / "main.py")]
        entry = store.create_preset("Test", paths)

        # Create new store instance
        new_store = PresetStore(temp_workspace)
        retrieved = new_store.get_preset(entry.preset_id)

        assert retrieved is not None
        assert retrieved.name == "Test"
        assert retrieved.selected_paths == entry.selected_paths

    def test_atomic_write(self, store, temp_workspace):
        """Test atomic write doesn't leave temp files."""
        paths = [str(temp_workspace / "src" / "main.py")]
        store.create_preset("Test", paths)

        tmp_file = temp_workspace / ".synapse_presets.tmp"
        assert not tmp_file.exists()

    def test_corrupt_file_recovery(self, temp_workspace):
        """Test recovery from corrupt preset file."""
        preset_file = temp_workspace / PRESET_FILENAME
        preset_file.write_text("invalid json {{{")

        store = PresetStore(temp_workspace)
        presets = store.list_presets()

        assert len(presets) == 0  # Graceful fallback
        assert (temp_workspace / ".synapse_presets.json.bak").exists()

    def test_set_workspace(self, store, temp_workspace, tmp_path):
        """Test changing workspace invalidates cache."""
        paths = [str(temp_workspace / "src" / "main.py")]
        store.create_preset("Test", paths)

        # Change workspace
        new_workspace = tmp_path / "new_workspace"
        new_workspace.mkdir()
        store.set_workspace(new_workspace)

        presets = store.list_presets()
        assert len(presets) == 0  # New workspace has no presets

    def test_empty_workspace(self, temp_workspace):
        """Test store with no presets."""
        store = PresetStore(temp_workspace)

        assert len(store.list_presets()) == 0
        assert store.get_preset("any-id") is None
        assert not (temp_workspace / PRESET_FILENAME).exists()

    def test_path_traversal_security(self, temp_workspace):
        """Test that path traversal attempts are blocked."""
        store = PresetStore(temp_workspace)

        # Create a file outside workspace
        outside_dir = temp_workspace.parent / "outside"
        outside_dir.mkdir(exist_ok=True)
        outside_file = outside_dir / "secret.txt"
        outside_file.write_text("secret data")

        # Try to create preset with path traversal
        malicious_paths = [
            "../outside/secret.txt",
            "../../outside/secret.txt",
            str(outside_file),  # Absolute path outside workspace
        ]

        # to_absolute_paths should filter out all malicious paths
        result = store.to_absolute_paths(malicious_paths)

        # All paths should be blocked
        assert len(result) == 0

        # Cleanup
        outside_file.unlink()
        outside_dir.rmdir()

    def test_symlink_path_traversal(self, temp_workspace, tmp_path):
        """Test that symlinks outside workspace are blocked."""
        store = PresetStore(temp_workspace)

        # Create target outside workspace
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir(exist_ok=True)
        outside_file = outside_dir / "target.txt"
        outside_file.write_text("target data")

        # Create symlink inside workspace pointing outside
        symlink = temp_workspace / "link_to_outside"
        try:
            symlink.symlink_to(outside_file)
        except OSError:
            # Skip test if symlinks not supported
            return

        # Try to resolve symlink
        result = store.to_absolute_paths(["link_to_outside"])

        # Symlink should be blocked if it points outside workspace
        # (resolve() will follow symlink and relative_to will fail)
        assert len(result) == 0

        # Cleanup
        symlink.unlink()
        outside_file.unlink()
        outside_dir.rmdir()
