# Synapse Desktop - Refactor Plan

> Incremental refactoring from current state to target architecture.
> Each milestone is a standalone deliverable that keeps tests green.

## Current Baseline
- **226 tests pass**, 5 skipped
- Command: `.venv/bin/python -m pytest tests/ -q`

---

## M1: Unify `path_for_display` (LOW RISK)

### Scope
- Create `core/prompting/path_utils.py` with single `path_for_display()` function
- Replace duplicates in:
  - `core/prompt_generator.py` line 18 (`_path_for_display`)
  - `core/utils/git_utils.py` line 13 (`_path_for_display`)

### Changes
| File | Action |
|------|--------|
| `core/prompting/__init__.py` | **[NEW]** Package init |
| `core/prompting/path_utils.py` | **[NEW]** Extracted `path_for_display()` |
| `core/prompt_generator.py` | **[MODIFY]** Import from `core.prompting.path_utils` |
| `core/utils/git_utils.py` | **[MODIFY]** Import from `core.prompting.path_utils` |

### Risk: LOW
- Pure function extraction, no side effects
- Circular import previously prevented this - verify import graph works

### Tests
- Existing `test_prompt_generator.py` (28 tests) must pass unchanged
- Existing `test_git_utils.py` (21 tests) must pass unchanged
- **[NEW]** `tests/test_path_utils.py` - unit tests for `path_for_display`

---

## M2: Unified Ignore Engine (MEDIUM RISK)

### Scope
- Create `core/ignore/engine.py` - single `IgnoreEngine` class
- Move `EXTENDED_IGNORE_PATTERNS` to `core/ignore/patterns.py`
- All scan functions delegate to `IgnoreEngine.should_ignore()`

### Changes
| File | Action |
|------|--------|
| `core/ignore/__init__.py` | **[NEW]** |
| `core/ignore/engine.py` | **[NEW]** IgnoreEngine class |
| `core/ignore/patterns.py` | **[NEW]** EXTENDED_IGNORE_PATTERNS moved here |
| `core/utils/file_utils.py` | **[MODIFY]** Use IgnoreEngine internally, keep public API |
| `core/utils/file_scanner.py` | **[MODIFY]** Use IgnoreEngine internally |
| `components/file_tree_model.py` | **[MODIFY]** `_collect_files_from_disk` uses IgnoreEngine |

### Risk: MEDIUM
- Ignore logic is critical path for file tree display
- Must verify: same files shown/hidden before and after
- Gitignore cache invalidation must still work

### Tests
- Existing `test_ignore_selected.py` (20 patterns) must pass
- Existing `test_tier2.py` must pass
- Existing `test_binary_file_detection.py` must pass
- **[NEW]** `tests/test_ignore_engine.py` - unit tests for IgnoreEngine

---

## M3: Prompt Pipeline Split + Formatters (HIGH RISK)

### Scope
Split `core/prompt_generator.py` (901 lines) into:
- `core/prompting/types.py` - dataclasses
- `core/prompting/file_collector.py` - file reading, binary detection
- `core/prompting/formatters/` - XML, JSON, Plain, Markdown formatters
- `core/prompting/prompt_assembler.py` - section composition
- Keep `core/prompt_generator.py` as thin adapter (calls new modules)

### Changes
| File | Action |
|------|--------|
| `core/prompting/types.py` | **[NEW]** OutputStyle, FileEntry, PromptConfig |
| `core/prompting/file_collector.py` | **[NEW]** Collect + read files |
| `core/prompting/formatters/__init__.py` | **[NEW]** |
| `core/prompting/formatters/base.py` | **[NEW]** Formatter protocol |
| `core/prompting/formatters/xml_formatter.py` | **[NEW]** |
| `core/prompting/formatters/json_formatter.py` | **[NEW]** |
| `core/prompting/formatters/plain_formatter.py` | **[NEW]** |
| `core/prompting/formatters/markdown_formatter.py` | **[NEW]** |
| `core/prompting/prompt_assembler.py` | **[NEW]** |
| `core/prompt_generator.py` | **[MODIFY]** Thin adapter delegating to new modules |

### Risk: HIGH
- Prompt output is user-facing; character-level differences break workflows
- Must use snapshot tests to verify exact output match

### Tests
- Existing `test_prompt_generator.py` (28 tests) MUST pass unchanged
- **[NEW]** `tests/test_formatters.py` - tests for each formatter
- **[NEW]** `tests/test_prompt_snapshots.py` - snapshot comparison tests:
  - XML format output
  - JSON format output
  - Plain format output
  - Markdown format output
  - With git diffs/logs on/off
  - With relative paths on/off
  - Binary files skipped correctly

---

## M4: Token Counting Facade + Service (MEDIUM RISK)

### Scope
- Create `core/tokenization/` package
- Consolidate token counting into facade
- Remove duplication between `TokenCountWorker` and `TokenDisplayService`

### Changes
| File | Action |
|------|--------|
| `core/tokenization/__init__.py` | **[NEW]** |
| `core/tokenization/types.py` | **[NEW]** TokenCountResult, TokenConfig |
| `core/tokenization/counter.py` | **[NEW]** Core counting logic (from token_counter.py) |
| `core/tokenization/cache.py` | **[NEW]** Token cache with mtime invalidation |
| `core/tokenization/batch.py` | **[NEW]** Parallel processing |
| `core/token_counter.py` | **[MODIFY]** Thin adapter importing from core.tokenization |
| `services/token_display.py` | **[MODIFY]** Delegate to core.tokenization.cache |

### Risk: MEDIUM
- Performance-critical path
- Must verify parallel/batch still works
- Cache invalidation must be correct

### Tests
- Existing `test_token_counter.py` (10 tests) must pass
- Existing `test_claude_tokenizer.py` (5 tests) must pass
- **[NEW]** `tests/test_tokenization/test_counter.py`
- **[NEW]** `tests/test_tokenization/test_cache.py`
- **[NEW]** `tests/test_tokenization/test_batch.py`

---

## M5: DIP for Encoders/Settings (LOW RISK)

### Scope
- `core/encoders.py` stops importing `services.settings_manager`
- Functions receive `model_id` and `tokenizer_repo` as parameters
- `core/tokenization/encoder_registry.py` wraps with parameter injection

### Changes
| File | Action |
|------|--------|
| `core/tokenization/encoder_registry.py` | **[NEW]** Wraps encoders with config injection |
| `core/encoders.py` | **[MODIFY]** Remove settings_manager imports, accept params |

### Risk: LOW
- Only changes internal wiring
- Public API via adapter remains same

### Tests
- Existing `test_claude_tokenizer.py` must pass
- Existing `test_token_counter.py` must pass

---

## M6: Workspace Index Separation (HIGH RISK)

### Scope
- Extract tree building, search index, file collection from `file_tree_model.py`
- Create `services/workspace_index.py` (pure data, no Qt)
- `FileTreeModel` becomes thin Qt adapter

### Changes
| File | Action |
|------|--------|
| `services/workspace_index.py` | **[NEW]** Tree building, search, deep collect |
| `components/file_tree_model.py` | **[MODIFY]** Remove scan/search/collect logic |

### Risk: HIGH
- `file_tree_model.py` is 1305 lines, deeply entangled with Qt
- Many methods reference `TreeNode` internal state
- Lazy loading (canFetchMore/fetchMore) must still work correctly
- Search index async building must remain functional
- Selection state management is complex

### Tests
- **Must test manually**: open app, verify tree loads, expand folders, search works
- Existing race condition tests must pass
- **[NEW]** `tests/test_workspace_index.py` - unit tests

---

## M7: Cleanup + Snapshot Tests (LOW RISK)

### Scope
- Remove all deprecated adapter code
- Tighten types (replace `Any` with proper types where possible)
- Add comprehensive snapshot tests
- Update README/docs
- Final test pass

### Changes
- Remove thin adapter wrappers from M1-M5
- Add type annotations
- CHANGELOG with API migration mapping

### Tests
- Full test suite: `.venv/bin/python -m pytest tests/ -v`
- All snapshot tests pass
- Manual smoke test of all app features

---

## Verification Plan

### Automated Tests
```bash
# Chạy sau mỗi milestone
cd /home/hao/Desktop/labs/Synapse-Desktop
.venv/bin/python -m pytest tests/ -q

# Chạy snapshot tests (M3+)
.venv/bin/python -m pytest tests/test_prompt_snapshots.py -v

# Chạy test cho module cụ thể
.venv/bin/python -m pytest tests/test_path_utils.py -v
.venv/bin/python -m pytest tests/test_ignore_engine.py -v
.venv/bin/python -m pytest tests/test_formatters.py -v
```

### Manual Verification (M6 especially)
1. Start app: `.venv/bin/python -m main_window`
2. Select a workspace folder
3. Verify: tree loads correctly, folders expand with lazy loading
4. Verify: search finds files correctly
5. Verify: token counting works (numbers appear next to files)
6. Verify: Copy Context produces correct output
7. Verify: OPX Apply still works
