from pathlib import Path
from unittest.mock import MagicMock, patch
from domain.prompt.opx_parser import FileAction, ChangeBlock
from application.services.preview_analyzer import (
    analyze_file_actions,
    _analyze_file_action,
    _calculate_change_summary,
    _generate_description,
    _count_lines,
    _resolve_path,
    format_change_summary,
    generate_preview_diff_lines,
    ChangeSummary,
    PreviewRow,
)
from domain.ports.registry import DomainRegistry


class TestPreviewAnalyzerExtra:
    def test_analyze_file_actions_success_and_exception(self):
        # 1. Success path and exception path in analyze_file_actions (lines 74, 75-76)
        action_success = FileAction(
            path="success.py",
            action="create",
            changes=[ChangeBlock(description="create success", content="print(1)")],
        )

        # Test loop with both a success action and a failing action
        with patch(
            "application.services.preview_analyzer._analyze_file_action"
        ) as mock_analyze:
            row_success = PreviewRow(
                path="success.py",
                action="create",
                description="create success",
                changes=ChangeSummary(1, 0),
            )
            # First call succeeds, second call raises exception
            mock_analyze.side_effect = [row_success, ValueError("Test crash")]

            action_fail = FileAction(path="fail.py", action="modify", changes=[])
            data = analyze_file_actions([action_success, action_fail])

            assert len(data.rows) == 1
            assert data.rows[0].path == "success.py"
            assert len(data.errors) == 1
            assert "Error analyzing fail.py: Test crash" in data.errors[0]

    def test_analyze_file_action_success_and_outer_exception(self):
        # 2. Success path with changes (lines 92-93)
        action_success = FileAction(
            path="success.py",
            action="create",
            changes=[ChangeBlock(description="create success", content="print(1)")],
        )
        row_success = _analyze_file_action(action_success)
        assert row_success.has_error is False
        assert len(row_success.change_blocks) == 1
        assert row_success.change_blocks[0]["description"] == "create success"

        # 3. Trigger outer exception inside _analyze_file_action (lines 111-121)
        # Passing changes=[None] triggers AttributeError during _count_lines(change.content)
        action_fail = FileAction(path="fail.py", action="create", changes=[None])
        row = _analyze_file_action(action_fail)
        assert row.has_error is True
        assert "Error:" in row.description
        assert row.error_message is not None

    def test_calculate_change_summary_actions(self, tmp_path):
        # 4. test action create success path (lines 131, 146-150, 219)
        act_create = FileAction(
            path="create.py",
            action="create",
            changes=[
                ChangeBlock(
                    description="my create file description", content="content\nlines"
                )
            ],
        )
        sum_create = _calculate_change_summary(act_create, workspace_root=tmp_path)
        assert sum_create.added == 2
        assert sum_create.removed == 0
        assert _generate_description(act_create) == "my create file description"

        # 5. test action rewrite success path (lines 133, 170)
        rewrite_file = tmp_path / "rewrite.py"
        rewrite_file.write_text("old line 1\nold line 2", encoding="utf-8")
        act_rewrite = FileAction(
            path="rewrite.py",
            action="rewrite",
            changes=[ChangeBlock(description="desc", content="new content")],
        )
        sum_rewrite = _calculate_change_summary(act_rewrite, workspace_root=tmp_path)
        assert sum_rewrite.added == 1
        assert sum_rewrite.removed == 2

        # 6. test action modify success path (lines 183-190)
        act_modify = FileAction(
            path="modify.py",
            action="modify",
            changes=[
                ChangeBlock(
                    description="desc",
                    search="find me\nline 2",
                    content="replace content",
                )
            ],
        )
        sum_modify = _calculate_change_summary(act_modify, workspace_root=tmp_path)
        assert sum_modify.added == 1
        assert sum_modify.removed == 2

        # 7. test action delete success path (lines 204-205)
        delete_file = tmp_path / "delete.py"
        delete_file.write_text("deleted content\nline 2", encoding="utf-8")
        act_delete = FileAction(path="delete.py", action="delete", changes=[])
        sum_delete = _calculate_change_summary(act_delete, workspace_root=tmp_path)
        assert sum_delete.added == 0
        assert sum_delete.removed == 2

        # 8. test action rename success path (line 139)
        act_rename = FileAction(
            path="rename.py", action="rename", new_path="new_rename.py", changes=[]
        )
        sum_rename = _calculate_change_summary(act_rename, workspace_root=tmp_path)
        assert sum_rename.added == 0
        assert sum_rename.removed == 0

        # 9. test unknown action (lines 140-141)
        act_unknown = FileAction(path="unknown.py", action="unknown", changes=[])
        sum_unknown = _calculate_change_summary(act_unknown, workspace_root=tmp_path)
        assert sum_unknown.added == 0
        assert sum_unknown.removed == 0

    def test_calculate_rewrite_changes_read_error(self, tmp_path):
        # 10. OSError during rewrite changes read (lines 171-172)
        rewrite_file = tmp_path / "rewrite.py"
        rewrite_file.write_text("old content", encoding="utf-8")

        act = FileAction(
            path="rewrite.py",
            action="rewrite",
            changes=[ChangeBlock(description="desc", content="new content")],
        )

        with patch.object(Path, "read_text", side_effect=OSError("Read denied")):
            changes = _calculate_change_summary(act, workspace_root=tmp_path)
            # added = 1, removed = 0 because read failed
            assert changes.added == 1
            assert changes.removed == 0

    def test_calculate_delete_changes_read_error(self, tmp_path):
        # 11. OSError during delete changes read (lines 206-207)
        del_file = tmp_path / "delete.py"
        del_file.write_text("old content", encoding="utf-8")

        act = FileAction(path="delete.py", action="delete", changes=[])

        with patch.object(Path, "read_text", side_effect=OSError("Read denied")):
            changes = _calculate_change_summary(act, workspace_root=tmp_path)
            # Default fallback 50 lines because read failed
            assert changes.added == 0
            assert changes.removed == 50

    def test_generate_description(self):
        # 12. Create action without description (line 220)
        a1 = FileAction(
            path="a.py",
            action="create",
            changes=[ChangeBlock(description="", content="a")],
        )
        assert _generate_description(a1) == "Create file"

        # 13. Rewrite action with/without description (lines 224-225)
        a2 = FileAction(
            path="a.py",
            action="rewrite",
            changes=[ChangeBlock(description="rewrite a", content="a")],
        )
        assert _generate_description(a2) == "rewrite a"
        a2_nodesc = FileAction(
            path="a.py",
            action="rewrite",
            changes=[ChangeBlock(description="", content="a")],
        )
        assert _generate_description(a2_nodesc) == "Rewrite file"

        # 14. Delete action (line 228)
        a3 = FileAction(path="a.py", action="delete", changes=[])
        assert _generate_description(a3) == "Delete file"

        # 15. Rename action (line 231)
        a4 = FileAction(path="a.py", action="rename", new_path="b.py", changes=[])
        assert _generate_description(a4) == "Rename to b.py"
        a4_no_new = FileAction(path="a.py", action="rename", changes=[])
        assert _generate_description(a4_no_new) == "Rename to new location"

        # 16. Modify action descriptions (lines 235, 238, 241-242, 245-247)
        # Empty changes
        a5_empty = FileAction(path="a.py", action="modify", changes=[])
        assert _generate_description(a5_empty) == "Modify file"

        # 1 change
        a5_one = FileAction(
            path="a.py",
            action="modify",
            changes=[ChangeBlock(description="desc 1", search="s", content="c")],
        )
        assert _generate_description(a5_one) == "desc 1"

        # 2-3 changes
        a5_three = FileAction(
            path="a.py",
            action="modify",
            changes=[
                ChangeBlock(description="desc 1", search="s", content="c"),
                ChangeBlock(description="desc 2", search="s", content="c"),
                ChangeBlock(description="desc 3", search="s", content="c"),
            ],
        )
        assert _generate_description(a5_three) == "desc 1 | desc 2 | desc 3"

        # >3 changes
        a5_many = FileAction(
            path="a.py",
            action="modify",
            changes=[
                ChangeBlock(description="desc 1", search="s", content="c"),
                ChangeBlock(description="desc 2", search="s", content="c"),
                ChangeBlock(description="desc 3", search="s", content="c"),
                ChangeBlock(description="desc 4", search="s", content="c"),
            ],
        )
        assert _generate_description(a5_many) == "desc 1 | desc 2 (+2 more)"

        # Unknown action (line 249)
        a6 = FileAction(path="a.py", action="unknown", changes=[])
        assert _generate_description(a6) == "Unknown action"

    def test_count_lines_none(self):
        # 17. None text (lines 254-255)
        assert _count_lines(None) == 0
        assert _count_lines("") == 0

    def test_resolve_path(self, tmp_path):
        # 18. Absolute path (lines 264-265)
        import sys
        if sys.platform == "win32":
            abs_path = "C:/usr/bin/local"
        else:
            abs_path = "/usr/bin/local"
        assert _resolve_path(abs_path) == Path(abs_path)


        # 19. Relative path but no workspace root (line 271)
        assert _resolve_path("local.py") is None

    def test_format_change_summary(self):
        assert format_change_summary(ChangeSummary(10, 5)) == "+10 / -5"

    def test_generate_preview_diff_lines_edge_cases(self, tmp_path):
        # 20. create action (line 316)
        act_create = FileAction(
            path="create.py",
            action="create",
            changes=[ChangeBlock(description="desc", content="new content")],
        )
        diffs_create = generate_preview_diff_lines(act_create, workspace_root=tmp_path)
        assert len(diffs_create) > 0

        # 21. read_text exception when getting old content (lines 303-304)
        file_path = tmp_path / "read_err.py"
        file_path.write_text("old content", encoding="utf-8")

        act_rewrite = FileAction(
            path="read_err.py",
            action="rewrite",
            changes=[ChangeBlock(description="desc", content="new content")],
        )
        with patch.object(Path, "read_text", side_effect=OSError("Read denied")):
            diffs = generate_preview_diff_lines(act_rewrite, workspace_root=tmp_path)
            # old_content is "" because of OSError. Diff should be empty or just adding new content.
            assert len(diffs) > 0

        # 22. delete action (line 320)
        act_delete = FileAction(path="del.py", action="delete", changes=[])
        # File not exists -> old content is "". Diff is empty
        diffs_del = generate_preview_diff_lines(act_delete, workspace_root=tmp_path)
        assert isinstance(diffs_del, list)

        # 23. rewrite action (line 324)
        act_rw = FileAction(
            path="rw.py",
            action="rewrite",
            changes=[ChangeBlock(description="desc", content="hello")],
        )
        diffs_rw = generate_preview_diff_lines(act_rw, workspace_root=tmp_path)
        assert isinstance(diffs_rw, list)

        # 24. rename action (line 351-353)
        act_rename = FileAction(
            path="old.py", action="rename", new_path="new.py", changes=[]
        )
        diffs_rename = generate_preview_diff_lines(act_rename, workspace_root=tmp_path)
        assert diffs_rename == []

        # 25. unknown action (line 355)
        act_unk = FileAction(path="unk.py", action="unknown", changes=[])
        diffs_unk = generate_preview_diff_lines(act_unk, workspace_root=tmp_path)
        assert diffs_unk == []

        # 26. modify action where change.search / change.content is missing (lines 330-332)
        act_mod_empty = FileAction(
            path="mod.py",
            action="modify",
            changes=[ChangeBlock(description="desc", search=None, content=None)],
        )
        diffs_mod_empty = generate_preview_diff_lines(
            act_mod_empty, workspace_root=tmp_path
        )
        assert isinstance(diffs_mod_empty, list)

        # 27. modify action success/failure search/replace (lines 333-348)
        act_mod = FileAction(
            path="mod.py",
            action="modify",
            changes=[ChangeBlock(description="desc", search="find", content="replace")],
        )

        # Mock file action service
        mock_service = MagicMock()
        # Case 1: Search replace fails (success = False) -> lines 347-348 skipped
        mock_service.normalize_eol.return_value = "find"
        mock_service.apply_search_replace_to_content.return_value = (False, "", "")

        old_service = None
        try:
            old_service = DomainRegistry.file_actions_service()
        except RuntimeError:
            pass

        DomainRegistry.register_file_actions_service(mock_service)
        try:
            diffs_fail = generate_preview_diff_lines(act_mod, workspace_root=tmp_path)
            assert isinstance(diffs_fail, list)

            # Case 2: Search replace succeeds (success = True) -> line 348 executed
            mock_service.apply_search_replace_to_content.return_value = (
                True,
                "new content after replace",
                "",
            )
            diffs_success = generate_preview_diff_lines(
                act_mod, workspace_root=tmp_path
            )
            assert isinstance(diffs_success, list)
        finally:
            if old_service is not None:
                DomainRegistry.register_file_actions_service(old_service)
