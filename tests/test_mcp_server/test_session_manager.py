"""
Tests cho mcp_server/core/session_manager.py

Kiem tra SessionManager xu ly dung CRUD operations cho file selection:
- get: doc danh sach files da chon
- set: thay the danh sach
- add: them files moi (khong trung lap)
- clear: xoa toan bo selection
- Path traversal / file khong ton tai bi tu choi

Note: SessionManager su dung SelectionState v2 (paths + provenance).
Backward-compatible voi v1 format ({\"selected_files\": [...]}).
"""

import json

import pytest

from domain.selection.provenance import SelectionState
from infrastructure.mcp.core.session_manager import SessionManager


@pytest.fixture
def workspace(tmp_path):
    """Tao workspace voi mot so files mau."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "src" / "utils.py").write_text("def helper(): pass")
    (tmp_path / "README.md").write_text("# Project")
    return tmp_path


@pytest.fixture
def session_file(workspace):
    """Tao session file (.synapse/selection.json) trong workspace (v2 format)."""
    synapse_dir = workspace / ".synapse"
    synapse_dir.mkdir(parents=True, exist_ok=True)
    sf = synapse_dir / "selection.json"
    # Ghi v2 format
    state = SelectionState()
    sf.write_text(json.dumps(state.to_dict()))
    return sf


class TestSessionManagerGet:
    """Kiem tra get_selection doc danh sach files tu selection file."""

    def test_get_empty_selection(self, session_file, workspace):
        """File selection rong -> tra ve 'No selection found'."""
        result = SessionManager.get_selection(session_file, workspace)
        assert "No selection found" in result or "empty" in result.lower()

    def test_get_with_files(self, session_file, workspace):
        """File selection co noi dung -> liet ke files."""
        state = SelectionState()
        state.add_paths(["src/main.py", "README.md"], "user")
        session_file.write_text(json.dumps(state.to_dict()))

        result = SessionManager.get_selection(session_file, workspace)
        assert "src/main.py" in result
        assert "README.md" in result
        assert "2 files" in result

    def test_get_nonexistent_file(self, workspace):
        """Session file chua ton tai -> tra ve thong bao no selection."""
        fake_sf = workspace / ".synapse" / "nonexistent.json"
        result = SessionManager.get_selection(fake_sf, workspace)
        assert "No selection found" in result


class TestSessionManagerSet:
    """Kiem tra set_selection thay the danh sach selection."""

    def test_set_valid_files(self, session_file, workspace):
        """Set danh sach valid files -> ghi vao file (v2 format)."""
        result = SessionManager.set_selection(
            session_file, workspace, ["src/main.py", "README.md"]
        )
        assert "2" in result

        # Kiem tra file da duoc ghi dung (v2 format)
        data = json.loads(session_file.read_text())
        assert "paths" in data  # v2 format
        assert "src/main.py" in data["paths"]
        assert "README.md" in data["paths"]

    def test_set_rejects_nonexistent_file(self, session_file, workspace):
        """File khong ton tai -> tra ve Error (early return)."""
        result = SessionManager.set_selection(
            session_file, workspace, ["nonexistent/file.py"]
        )
        assert "Error" in result

    def test_set_empty_list(self, session_file, workspace):
        """Set danh sach rong -> selection rong (v2 format)."""
        SessionManager.set_selection(session_file, workspace, [])
        data = json.loads(session_file.read_text())
        assert data["paths"] == []

    def test_set_blocks_path_traversal(self, session_file, workspace):
        """Path traversal bi chan voi error message."""
        result = SessionManager.set_selection(
            session_file, workspace, ["../../../etc/passwd"]
        )
        assert "Error" in result
        assert "traversal" in result.lower()


class TestSessionManagerAdd:
    """Kiem tra add_selection them files moi khong bi trung lap."""

    def test_add_new_files(self, session_file, workspace):
        """Them file moi vao selection rong."""
        SessionManager.add_selection(session_file, workspace, ["src/main.py"])
        data = json.loads(session_file.read_text())
        assert "src/main.py" in data["paths"]

    def test_add_no_duplicates(self, session_file, workspace):
        """Them file da co san -> khong bi trung lap."""
        state = SelectionState()
        state.add_paths(["src/main.py"], "user")
        session_file.write_text(json.dumps(state.to_dict()))

        SessionManager.add_selection(
            session_file, workspace, ["src/main.py", "src/utils.py"]
        )
        data = json.loads(session_file.read_text())
        # chi co 1 lan src/main.py
        assert data["paths"].count("src/main.py") == 1
        assert "src/utils.py" in data["paths"]

    def test_add_rejects_nonexistent_file(self, session_file, workspace):
        """Them file khong ton tai -> Error."""
        result = SessionManager.add_selection(session_file, workspace, ["not_there.py"])
        assert "Error" in result


class TestSessionManagerClear:
    """Kiem tra clear_selection xoa toan bo selection."""

    def test_clear_selection(self, session_file):
        """Clear -> selection rong (v2 format)."""
        state = SelectionState()
        state.add_paths(["a.py", "b.py"], "user")
        session_file.write_text(json.dumps(state.to_dict()))

        SessionManager.clear_selection(session_file)
        data = json.loads(session_file.read_text())
        assert data["paths"] == []

    def test_clear_returns_confirmation(self, session_file):
        """Clear tra ve confirmation message."""
        result = SessionManager.clear_selection(session_file)
        assert "cleared" in result.lower()
