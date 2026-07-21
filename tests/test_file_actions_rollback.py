"""
Unit tests for Session Rollback System in infrastructure/filesystem/file_actions.py
"""

from pathlib import Path
from domain.prompt.opx_parser import FileAction, ChangeBlock
from infrastructure.filesystem.file_actions import (
    apply_file_actions,
    rollback_apply_session,
    get_last_apply_session,
)


def test_rollback_create_action(tmp_path: Path):
    target_file = tmp_path / "new_file.py"
    assert not target_file.exists()

    action = FileAction(
        action="create",
        path="new_file.py",
        changes=[ChangeBlock(description="Create", content="print('Hello World')")],
    )

    results = apply_file_actions([action], workspace_roots=[tmp_path])
    assert results[0].success
    assert target_file.exists()
    assert target_file.read_text(encoding="utf-8") == "print('Hello World')"

    # Rollback session
    rb_res = rollback_apply_session(workspace_roots=[tmp_path])
    assert rb_res.success
    assert not target_file.exists()


def test_rollback_modify_action(tmp_path: Path):
    target_file = tmp_path / "existing.py"
    original_content = "def hello():\n    return 'old'\n"
    target_file.write_text(original_content, encoding="utf-8")

    action = FileAction(
        action="modify",
        path="existing.py",
        changes=[
            ChangeBlock(
                description="Modify", search="return 'old'", content="return 'new'"
            )
        ],
    )

    results = apply_file_actions([action], workspace_roots=[tmp_path])
    assert results[0].success
    assert "return 'new'" in target_file.read_text(encoding="utf-8")

    # Rollback session
    rb_res = rollback_apply_session(workspace_roots=[tmp_path])
    assert rb_res.success
    assert target_file.read_text(encoding="utf-8") == original_content


def test_rollback_rewrite_action(tmp_path: Path):
    target_file = tmp_path / "rewrite.txt"
    original_content = "Line 1\nLine 2\nLine 3"
    target_file.write_text(original_content, encoding="utf-8")

    action = FileAction(
        action="rewrite",
        path="rewrite.txt",
        changes=[ChangeBlock(description="Rewrite", content="Completely new content")],
    )

    results = apply_file_actions([action], workspace_roots=[tmp_path])
    assert results[0].success
    assert target_file.read_text(encoding="utf-8") == "Completely new content"

    # Rollback session
    rb_res = rollback_apply_session(workspace_roots=[tmp_path])
    assert rb_res.success
    assert target_file.read_text(encoding="utf-8") == original_content


def test_rollback_delete_action(tmp_path: Path):
    target_file = tmp_path / "to_delete.txt"
    original_content = "Important data to protect"
    target_file.write_text(original_content, encoding="utf-8")

    action = FileAction(
        action="delete",
        path="to_delete.txt",
    )

    results = apply_file_actions([action], workspace_roots=[tmp_path])
    assert results[0].success
    assert not target_file.exists()

    # Rollback session
    rb_res = rollback_apply_session(workspace_roots=[tmp_path])
    assert rb_res.success
    assert target_file.exists()
    assert target_file.read_text(encoding="utf-8") == original_content


def test_rollback_rename_action(tmp_path: Path):
    old_file = tmp_path / "old_name.txt"
    new_file = tmp_path / "new_name.txt"
    content = "Renamed file content"
    old_file.write_text(content, encoding="utf-8")

    action = FileAction(
        action="rename",
        path="old_name.txt",
        new_path="new_name.txt",
    )

    results = apply_file_actions([action], workspace_roots=[tmp_path])
    assert results[0].success
    assert not old_file.exists()
    assert new_file.exists()

    # Rollback session
    rb_res = rollback_apply_session(workspace_roots=[tmp_path])
    assert rb_res.success
    assert old_file.exists()
    assert not new_file.exists()
    assert old_file.read_text(encoding="utf-8") == content


def test_rollback_mixed_atomic_session(tmp_path: Path):
    # Setup files
    file_created = tmp_path / "created.py"

    file_modified = tmp_path / "modified.py"
    orig_modified_content = "A = 1\nB = 2"
    file_modified.write_text(orig_modified_content, encoding="utf-8")

    file_deleted = tmp_path / "deleted.py"
    orig_deleted_content = "SECRET_KEY = 12345"
    file_deleted.write_text(orig_deleted_content, encoding="utf-8")

    file_renamed_old = tmp_path / "renamed_old.py"
    file_renamed_new = tmp_path / "renamed_new.py"
    orig_renamed_content = "def foo(): pass"
    file_renamed_old.write_text(orig_renamed_content, encoding="utf-8")

    actions = [
        FileAction(
            action="create",
            path="created.py",
            changes=[ChangeBlock(description="Create", content="# Created")],
        ),
        FileAction(
            action="modify",
            path="modified.py",
            changes=[
                ChangeBlock(description="Modify", search="B = 2", content="B = 999")
            ],
        ),
        FileAction(action="delete", path="deleted.py"),
        FileAction(action="rename", path="renamed_old.py", new_path="renamed_new.py"),
    ]

    results = apply_file_actions(actions, workspace_roots=[tmp_path])
    assert all(r.success for r in results)

    # Verify changes applied
    assert file_created.exists()
    assert "B = 999" in file_modified.read_text(encoding="utf-8")
    assert not file_deleted.exists()
    assert not file_renamed_old.exists()
    assert file_renamed_new.exists()

    # Rollback session
    session = get_last_apply_session()
    assert session is not None
    assert len(session.items) == 4

    rb_res = rollback_apply_session(session, workspace_roots=[tmp_path])
    assert rb_res.success
    assert len(rb_res.item_results) == 4

    # Verify 100% restored project state
    assert not file_created.exists()
    assert file_modified.read_text(encoding="utf-8") == orig_modified_content
    assert file_deleted.exists()
    assert file_deleted.read_text(encoding="utf-8") == orig_deleted_content
    assert file_renamed_old.exists()
    assert not file_renamed_new.exists()
    assert file_renamed_old.read_text(encoding="utf-8") == orig_renamed_content
