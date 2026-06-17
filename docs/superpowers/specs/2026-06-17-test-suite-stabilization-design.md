# Design Spec: Test Suite Stabilization on Windows

## Goal Description
The purpose of this work is to stabilize the test suite for Synapse Desktop in the Windows environment, achieving a 100% pass rate for active tests. Specifically, this resolves issues related to path separators (`\\` vs `/`), EOL line endings (`\r\n` vs `\n`), obsolete tests targeting deleted MCP handlers, and invalid UI mocks resulting from recent UI redesigns.

## User Review Required
> [!IMPORTANT]
> The following obsolete test files will be permanently deleted from the codebase as they test MCP handlers and features that were completely removed in previous commits:
> - `tests/test_auto_codemap_integration.py`
> - `tests/test_mcp_server/test_handler_registration.py`
> - `tests/test_mcp_server/test_skill_installer.py`
> - `tests/test_workflows/test_codebase_analysis_tools.py`
> - `tests/test_workflows/test_workspace_auto_detect.py`

## Proposed Changes

### Deletion of Obsolete Test Files
- Delete `tests/test_auto_codemap_integration.py`
- Delete `tests/test_mcp_server/test_handler_registration.py`
- Delete `tests/test_mcp_server/test_skill_installer.py`
- Delete `tests/test_workflows/test_codebase_analysis_tools.py`
- Delete `tests/test_workflows/test_workspace_auto_detect.py`

### Correct Domain Logic & Imports
- **`tests/domain/prompt/test_template_registry.py`**: Fix the typo `"roi_analyer"` -> `"roi_analyzer"` in template loading and listing test cases.
- **`tests/test_binary_file_detection.py`**: Fix import of `is_binary_file` and `is_binary_by_extension` to pull from `shared.utils.file_utils` instead of `infrastructure.filesystem.file_utils`. Remove `test_json_format_skip_binary` as JSON output formatting is no longer supported.
- **`tests/test_bug_verification.py`**: Update `_generate_codemap_xml` imports and usage to use `_generate_codemap_xml_elements` and handle list-of-strings return type.
- **`tests/domain/test_prompt_generator_extra.py`**: Update mock and call syntax from `_generate_codemap_xml` to `_generate_codemap_xml_elements`.

### Windows Path & EOL Normalization
- **Path Separators (`\\` vs `/`)**:
  Normalize paths to slash (`/`) or use `os.path.normpath` / `PurePath.as_posix()` in path assertions within:
  - `tests/application/test_workspace_index_extra.py`
  - `tests/domain/prompt/test_patch_detection_service.py`
  - `tests/test_file_collector.py`
  - `tests/test_ignore_selected.py`
  - `tests/test_preset_store.py`
  - `tests/test_prompt_generator.py`
  - `tests/test_prompt_assembler.py`
  - `tests/presentation/test_context_controllers.py`
- **EOL (`\r\n` vs `\n`)**:
  - `tests/test_preview_diff_accuracy.py` (`test_preview_diff_eol_normalization`): Ensure the search block contains correct newlines (`\r\n` on Windows) or normalize before matching.
  - `tests/test_tokenization.py` (`test_multiline_file`): Specify `newline='\n'` when writing test files to prevent Python from auto-converting to CRLF on Windows, allowing clean byte/mmap comparisons.
- **Windows Symlinks**:
  - `tests/integration/test_tokenization_service.py` (`test_symlink_to_file`): Skip this test case on Windows if the user lacks administrator privileges using `@pytest.mark.skipif`.

### UI and Integration Tests Adjustment
- **`tests/ui/test_history_ui.py`**: Update or skip tests accessing obsolete history view methods (e.g. `get_history_entries` which was moved or redesigned).
- **`tests/ui/test_copy_actions.py`**: Fix mock targets for `load_app_settings` and `scan_directory` to use correct import path.
- **`tests/ui/test_main_ui.py`**: Fix mock targets for `get_memory_monitor`.
- **`tests/test_fast_workspace_change.py`**: Update import for `compute_semantic_index` if it was moved, or skip/mock if the feature is no longer supported.

## Verification Plan
1. Run Ruff format and lint checks to ensure code quality.
2. Run targeted tests for modified files.
3. Run the complete pytest test suite:
   ```bash
   pytest tests/ -v
   ```
4. Verify that all 1700+ tests pass successfully in the local Windows environment.
