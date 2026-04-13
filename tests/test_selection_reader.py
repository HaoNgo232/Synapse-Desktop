"""Tests cho domain.selection.selection_reader (v2-only format)."""

import json
from pathlib import Path

from domain.selection.selection_reader import read_selection_paths, read_selection_state


def test_read_selection_state_v2(tmp_path: Path) -> None:
    session_file = tmp_path / ".synapse" / "selection.json"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(
        json.dumps(
            {
                "version": 2,
                "paths": ["src/main.py", "README.md"],
                "provenance": {"src/main.py": "agent", "README.md": "user"},
            }
        ),
        encoding="utf-8",
    )

    state = read_selection_state(session_file)
    assert state.paths == ["src/main.py", "README.md"]
    assert state.provenance["src/main.py"] == "agent"


def test_read_selection_state_ignores_v1_payload(tmp_path: Path) -> None:
    session_file = tmp_path / ".synapse" / "selection.json"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(
        json.dumps({"selected_files": ["src/main.py"]}),
        encoding="utf-8",
    )

    state = read_selection_state(session_file)
    assert state.paths == []
    assert read_selection_paths(session_file) == []
