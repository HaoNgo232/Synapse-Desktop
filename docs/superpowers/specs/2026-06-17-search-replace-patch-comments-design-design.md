# Spec Design: SEARCH/REPLACE Block Comments & Description Parsing

## 1. Goal Description
Ensure that SEARCH/REPLACE (Aider-style) blocks can carry descriptive comments (metadata) describing the changes, which will then be parsed and visualized on the UI Diff Preview (instead of showing generic messages like "Search/Replace patch").

---

## 2. Proposed Format
We will instruct the LLM to output the description inline with the SEARCH marker:
```text
<<<<<<< SEARCH path/to/file.ext - <Brief description of the changes>
```
If the description is omitted, the parser will fall back to `"Search/Replace patch"` (or `"Create file"` for empty search blocks) to ensure full backward compatibility.

---

## 3. Architecture & Components

### A. System Prompt Instruction (`domain/prompt/opx_instruction.py`)
Modify the `XML_FORMATTING_INSTRUCTIONS` text block to:
- Guide the LLM to write a concise description on the same line as `<<<<<<< SEARCH` using the format `<<<<<<< SEARCH path/to/file.ext - <Brief description of changes>`.
- Update the examples to reflect this new capability.

### B. Parser Update (`domain/prompt/opx_parser.py`)
Update the `_SR_BLOCK_RE` regex pattern to optionally capture the description:
```python
# Old pattern:
# _SR_BLOCK_RE = re.compile(
#     r"^<{7}\s+SEARCH\s+(\S+)[^\n]*\n(.*?)^={7}\s*\n(.*?)^>{7}\s+REPLACE[^\n]*$",
#     re.MULTILINE | re.DOTALL,
# )

# New pattern (with capture group 2 for optional description):
_SR_BLOCK_RE = re.compile(
    r"^<{7}\s+SEARCH\s+(\S+)(?:\s+-\s+([^\n]+))?[^\n]*\n(.*?)^={7}\s*\n(.*?)^>{7}\s+REPLACE[^\n]*$",
    re.MULTILINE | re.DOTALL,
)
```
In the parsing loop of `parse_search_replace_response`:
- Retrieve `match.group(2)` as the parsed comment description.
- Strip any trailing/leading whitespace from the description.
- Use it to populate `ChangeBlock.description`. Fall back to `"Search/Replace patch"` or `"Create file"` if empty.

### C. Verification (Tests)
Write unit tests in `tests/test_opx_parser.py` (or similar test file) to verify:
- Parsing of SEARCH/REPLACE blocks with comments.
- Parsing of SEARCH/REPLACE blocks without comments (backward compatibility).

---

## 4. Verification Plan

### Automated Tests
- Run pytest: `pytest tests/test_opx_parser.py` (or write new tests in `tests/test_search_replace_comments.py`).
- Run ruff check & format.

### Manual Verification
- Paste a mock Search/Replace text with comments into the UI text area.
- Click **Preview** and check if the card description correctly renders the comments.
