# Test Suite Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up obsolete test files, fix Windows-specific path separator issues, EOL differences, and mock import paths to ensure 100% of the active tests pass on Windows local environment.

**Architecture:** We will clean up the test suite in 5 logical tasks starting from deleting completely removed handlers tests, then domain logic fixes, path separators adjustments, Windows-specific EOL/symlink fixes, and finally UI redesign mock adjustments.

**Tech Stack:** Python 3.12, PySide6, pytest, pytest-qt, unittest.mock.

## Global Constraints
- Absolute imports must be used at all times.
- DO NOT run any git commit commands automatically (`RULE[user_global]`: Tuyệt đối không tự ý commit).
- Paths in tests should be compared using OS-agnostic methods.

---

### Task 1: Delete Obsolete Test Files

**Files:**
- Delete: `tests/test_auto_codemap_integration.py`
- Delete: `tests/test_mcp_server/test_handler_registration.py`
- Delete: `tests/test_mcp_server/test_skill_installer.py`
- Delete: `tests/test_workflows/test_codebase_analysis_tools.py`
- Delete: `tests/test_workflows/test_workspace_auto_detect.py`

- [ ] **Step 1: Delete the obsolete files from the filesystem**
  Execute deletion of the files:
  - `tests/test_auto_codemap_integration.py`
  - `tests/test_mcp_server/test_handler_registration.py`
  - `tests/test_mcp_server/test_skill_installer.py`
  - `tests/test_workflows/test_codebase_analysis_tools.py`
  - `tests/test_workflows/test_workspace_auto_detect.py`

- [ ] **Step 2: Run pytest collection to verify success**
  Run: `.venv\Scripts\pytest tests/ --collect-only`
  Expected: Collection succeeds with no ImportErrors or ModuleNotFoundErrors from the deleted files.

---

### Task 2: Correct Domain Logic Typos, Imports, and XML Generator Helpers

**Files:**
- Modify: `tests/domain/prompt/test_template_registry.py`
- Modify: `tests/test_binary_file_detection.py`
- Modify: `tests/test_bug_verification.py`
- Modify: `tests/domain/test_prompt_generator_extra.py`

- [ ] **Step 1: Fix typo "roi_analyer" -> "roi_analyzer"**
  In `tests/domain/prompt/test_template_registry.py`, replace all occurrences of `roi_analyer` with `roi_analyzer`.

- [ ] **Step 2: Fix import path and remove obsolete JSON skip test**
  In `tests/test_binary_file_detection.py`, change import of `is_binary_file` and `is_binary_by_extension` from `infrastructure.filesystem.file_utils` to `shared.utils.file_utils`. Delete `test_json_format_skip_binary` test case since JSON formatter is removed.

- [ ] **Step 3: Update `_generate_codemap_xml` to `_generate_codemap_xml_elements`**
  In `tests/test_bug_verification.py` and `tests/domain/test_prompt_generator_extra.py`, update calls to `_generate_codemap_xml` to call `_generate_codemap_xml_elements` (which returns a list of XML strings) and join them using `"\n"`.

- [ ] **Step 4: Run these domain tests to verify they pass**
  Run: `.venv\Scripts\pytest tests/domain/prompt/test_template_registry.py tests/test_binary_file_detection.py tests/test_bug_verification.py tests/domain/test_prompt_generator_extra.py -v`
  Expected: All targeted tests PASS.

---

### Task 3: Windows Path Normalization in Test Assertions

**Files:**
- Modify: `tests/application/test_workspace_index_extra.py`
- Modify: `tests/domain/prompt/test_patch_detection_service.py`
- Modify: `tests/test_file_collector.py`
- Modify: `tests/test_ignore_selected.py`
- Modify: `tests/test_preset_store.py`
- Modify: `tests/test_prompt_generator.py`
- Modify: `tests/test_prompt_assembler.py`
- Modify: `tests/presentation/test_context_controllers.py`

- [ ] **Step 1: Normalize path separators in test assertions**
  Update comparisons in assertions to use posix format (`.replace('\\', '/')`) or `os.path.normpath` so they are OS-independent:
  - `tests/application/test_workspace_index_extra.py` (e.g., in `test_collect_files_from_disk_os_walk_branches` normalize walk paths).
  - `tests/domain/prompt/test_patch_detection_service.py` (e.g., `test_affected_files_populated_correctly` normalize path comparisons).
  - `tests/test_file_collector.py` (e.g., `test_relative_path_display` normalize relative paths).
  - `tests/test_ignore_selected.py` (e.g., `test_relative_path_pattern` normalize paths).
  - `tests/test_preset_store.py` (e.g., `test_create_preset` normalize paths).
  - `tests/test_prompt_generator.py` (e.g., `test_xml_use_relative_paths` handle backslashes in paths).
  - `tests/test_prompt_assembler.py` (e.g., `test_build_diff_only_with_related_files` normalize path check).
  - `tests/presentation/test_context_controllers.py` (e.g., `test_tree_management_add_and_undo_ignore` normalize paths).

- [ ] **Step 2: Run targeted path tests to verify**
  Run: `.venv\Scripts\pytest tests/application/test_workspace_index_extra.py tests/domain/prompt/test_patch_detection_service.py tests/test_file_collector.py tests/test_ignore_selected.py tests/test_preset_store.py tests/test_prompt_generator.py tests/test_prompt_assembler.py tests/presentation/test_context_controllers.py -v`
  Expected: All targeted tests PASS.

---

### Task 4: Windows EOL and Symlink Handling

**Files:**
- Modify: `tests/test_preview_diff_accuracy.py`
- Modify: `tests/test_tokenization.py`
- Modify: `tests/integration/test_tokenization_service.py`

- [ ] **Step 1: Normalize EOL line endings in search patch test**
  In `tests/test_preview_diff_accuracy.py` (`test_preview_diff_eol_normalization`), normalize the expected EOL formats in search patches or handle EOL mismatch by converting `\n` to `\r\n` before applying changes in tests on Windows.

- [ ] **Step 2: Set newline flag to preserve LF in tokenization test**
  In `tests/test_tokenization.py` (`test_multiline_file`), write the temporary file with `newline='\n'` in `write_text()` to prevent Windows from auto-converting EOL to CRLF, or normalize the read output.

- [ ] **Step 3: Skip symlink tests on Windows without admin privileges**
  In `tests/integration/test_tokenization_service.py` (`test_symlink_to_file`), add `@pytest.mark.skipif(sys.platform == 'win32', reason="Symlinks require admin rights on Windows")`.
  Also skip/mock other obsolete `TokenizationService` tests in `tests/integration/test_tokenization_service.py` (like `test_read_normal_file` requesting `_read_file_mmap`) if they are no longer supported.

- [ ] **Step 4: Run targeted EOL and symlink tests**
  Run: `.venv\Scripts\pytest tests/test_preview_diff_accuracy.py tests/test_tokenization.py tests/integration/test_tokenization_service.py -v`
  Expected: PASS.

---

### Task 5: UI and Integration Mock/Import Fixes or Skip

**Files:**
- Modify: `tests/ui/test_history_ui.py`
- Modify: `tests/ui/test_copy_actions.py`
- Modify: `tests/ui/test_main_ui.py`
- Modify: `tests/ui/test_context_ui.py`
- Modify: `tests/test_fast_workspace_change.py`

- [ ] **Step 1: Fix or skip obsolete UI test cases**
  - In `tests/ui/test_history_ui.py`, skip history view tests since the history view UI has been completely redesigned and no longer uses `get_history_entries` directly at presentation setup level.
  - In `tests/ui/test_copy_actions.py`, fix the mock target for `load_app_settings` and `scan_directory` in `presentation.views.context.copy_action_controller` (e.g. mock from `infrastructure.persistence.settings_manager.load_app_settings`).
  - In `tests/ui/test_main_ui.py`, fix `get_memory_monitor` mock path or import path.
  - In `tests/test_fast_workspace_change.py`, skip `test_semantic_index_is_disabled_and_fast` if `compute_semantic_index` is removed.

- [ ] **Step 2: Run targeted UI tests**
  Run: `.venv\Scripts\pytest tests/ui/ -v`
  Expected: Targeted UI tests pass or are skipped gracefully.

- [ ] **Step 3: Run the full test suite**
  Run: `.venv\Scripts\pytest tests/ -v`
  Expected: 100% of the active tests PASS.
