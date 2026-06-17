# Implementation Plan - SEARCH/REPLACE Block Comments & Description Parsing

Implement inline descriptions for Aider-style SEARCH/REPLACE blocks. Parse them safely and display them on the UI Diff Preview instead of the default generic message.

## User Review Required
No breaking changes are introduced. The design ensures full backward compatibility (if no description is present, the parser falls back to default descriptions).

## Proposed Changes

### Domain Prompt

#### [MODIFY] [opx_instruction.py](file:///d:/share_vm/Synapse-Desktop/domain/prompt/opx_instruction.py)
- Update the system prompt `XML_FORMATTING_INSTRUCTIONS` to guide the LLM to output inline descriptions using the format: `<<<<<<< SEARCH path/to/file.ext - <Brief description of changes>`
- Update the examples inside the prompt to demonstrate this comment formatting.

#### [MODIFY] [opx_parser.py](file:///d:/share_vm/Synapse-Desktop/domain/prompt/opx_parser.py)
- Modify `_SR_BLOCK_RE` regex to optionally capture the description:
  ```python
  _SR_BLOCK_RE = re.compile(
      r"^<{7}\s+SEARCH\s+(\S+)(?:\s+-\s+([^\n]+))?[^\n]*\n(.*?)^={7}\s*\n(.*?)^>{7}\s+REPLACE[^\n]*$",
      re.MULTILINE | re.DOTALL,
  )
  ```
- Update the parsing logic in `parse_search_replace_response` to extract this description and assign it to `ChangeBlock.description`, with fallback to `"Search/Replace patch"` (or `"Create file"` for new files).

---

### Tests

#### [NEW] [test_search_replace_comments.py](file:///d:/share_vm/Synapse-Desktop/tests/test_search_replace_comments.py)
- Create new test cases verifying that:
  - Blocks with comments are parsed correctly and the description is set to the comment text.
  - Blocks without comments are parsed correctly (backward compatibility).
  - Special characters in comments do not break parsing.

---

## Verification Plan

### Automated Tests
- Run ruff format, lint, type-check, and pytest to ensure everything works correctly.
  ```powershell
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff format .
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff check --fix .
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_search_replace_comments.py -v
  ```

### Manual Verification
- Paste a sample search-replace block with a comment on the left panel.
- Click **Preview** and check if the card in the right panel displays the description correctly.
