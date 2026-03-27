from pathlib import Path

from domain.prompt.opx_parser import ChangeBlock, FileAction
from infrastructure.filesystem.file_actions import apply_file_actions


def test_modify_normalized_match_does_not_shift_offsets(tmp_path: Path) -> None:
    """Regression: normalized fallback must not apply replacement at wrong offset."""
    target = tmp_path / "sample.py"
    target.write_text(
        "line_before    \n"
        "another line\n"
        "\n"
        "def assemble_prompt(   \n"
        "    return 'old'\n"
        ")\n",
        encoding="utf-8",
    )

    action = FileAction(
        path="sample.py",
        action="modify",
        changes=[
            ChangeBlock(
                description="Update function body",
                search="def assemble_prompt(\n    return 'old'\n)",
                content="def assemble_prompt(\n    return 'new'\n)",
            )
        ],
    )

    results = apply_file_actions([action], workspace_roots=[tmp_path], dry_run=False)

    assert results[0].success, results[0].message
    assert target.read_text(encoding="utf-8") == (
        "line_before    \nanother line\n\ndef assemble_prompt(\n    return 'new'\n)\n"
    )


def test_modify_normalized_match_requires_occurrence_when_ambiguous(
    tmp_path: Path,
) -> None:
    """When normalized matching finds multiple regions, missing occurrence must fail safely."""
    target = tmp_path / "dupe.py"
    target.write_text(
        "value = 1   \nvalue = 1\n",
        encoding="utf-8",
    )

    action = FileAction(
        path="dupe.py",
        action="modify",
        changes=[
            ChangeBlock(
                description="Replace ambiguous block",
                search="value = 1",
                content="value = 2",
            )
        ],
    )

    results = apply_file_actions([action], workspace_roots=[tmp_path], dry_run=False)

    assert not results[0].success
    assert target.read_text(encoding="utf-8") == "value = 1   \nvalue = 1\n"


def test_modify_normalized_match_respects_numeric_occurrence(tmp_path: Path) -> None:
    """Normalized matching should support numeric occurrence deterministically."""
    target = tmp_path / "dupe_occurrence.py"
    target.write_text(
        "value = 1   \nvalue = 1\n",
        encoding="utf-8",
    )

    action = FileAction(
        path="dupe_occurrence.py",
        action="modify",
        changes=[
            ChangeBlock(
                description="Replace only second match",
                search="value = 1",
                content="value = 2",
                occurrence=2,
            )
        ],
    )

    results = apply_file_actions([action], workspace_roots=[tmp_path], dry_run=False)

    assert results[0].success, results[0].message
    assert target.read_text(encoding="utf-8") == "value = 1   \nvalue = 2\n"
