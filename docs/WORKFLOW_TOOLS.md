# Workflow Tools Documentation

## Overview

Synapse Desktop provides 4 advanced workflow tools designed for AI agent handoff and complex coding tasks. These tools automate context gathering, scope detection, and prompt generation.

## Tools

### 1. `rp_build` — Context Builder

**Purpose:** Automatically prepare optimized context for implementing a new feature or task.

**What it does:**
- Detects relevant files from task description
- Traces dependencies automatically
- Slices large files to include only relevant sections
- Optimizes content to fit token budget
- Generates structured handoff prompt

**Usage:**
```python
# Via MCP
rp_build(
    workspace_path="/path/to/project",
    task_description="Add rate limiting to login endpoint",
    file_paths=["auth/login.py", "middleware/rate_limit.py"],  # Optional
    max_tokens=100_000,
    output_file="context.xml"  # Optional: write to file for cross-agent handoff
)
```

**When to use:**
- Starting a new feature implementation
- Need to understand code structure before making changes
- Want to hand off context to another AI agent

---

### 2. `rp_review` — Code Review Workflow

**Purpose:** Deep code review with full surrounding context.

**What it does:**
- Pulls git diff (staged + unstaged changes)
- Identifies changed functions/classes (not just lines)
- Finds surrounding context: imports, callers, tests
- Packages everything into comprehensive review prompt

**Usage:**
```python
# Via MCP
rp_review(
    workspace_path="/path/to/project",
    review_focus="security",  # Optional: "security", "performance", "correctness"
    include_tests=True,
    include_callers=True,
    max_tokens=120_000
)
```

**When to use:**
- Before merging a PR
- Need to understand impact of changes
- Want AI to detect side effects and breaking changes

---

### 3. `rp_refactor` — Two-Pass Refactor Workflow

**Purpose:** Safe refactoring with analysis-first approach.

**What it does:**

**Phase 1 (discover):**
- Analyzes code structure WITHOUT making changes
- Finds all dependencies and coupling points
- Identifies risk areas and backward compatibility concerns
- Outputs discovery report

**Phase 2 (plan):**
- Takes discovery report as input
- Generates concrete refactoring plan
- Ensures backward compatibility
- Suggests migration steps if needed

**Usage:**
```python
# Step 1: Discovery
rp_refactor(
    workspace_path="/path/to/project",
    refactor_scope="Extract authentication logic into separate service",
    phase="discover"
)

# Step 2: Review discovery report, then plan
rp_refactor(
    workspace_path="/path/to/project",
    refactor_scope="Extract authentication logic into separate service",
    phase="plan",
    discovery_report="<paste discovery output here>"
)
```

**When to use:**
- Large refactoring that affects multiple files
- Need to ensure backward compatibility
- Want to understand risks before making changes

---

### 4. `rp_investigate` — Bug Investigation Workflow

**Purpose:** Automated bug investigation by tracing execution path.

**What it does:**
- Parses error traces (Python traceback, JS stack traces)
- Reads code at each trace point
- Follows function calls (callers and callees) via BFS
- Slices large files to show only relevant sections
- Packages everything into investigation prompt

**Usage:**
```python
# With error trace
rp_investigate(
    workspace_path="/path/to/project",
    bug_description="Division by zero error in calculate function",
    error_trace="""
Traceback (most recent call last):
  File "main.py", line 10, in main
    result = calculate(10, 0)
  File "utils.py", line 25, in calculate
    return a / b
ZeroDivisionError: division by zero
""",
    max_depth=4
)

# Without error trace (manual entry points)
rp_investigate(
    workspace_path="/path/to/project",
    bug_description="Login fails silently",
    entry_files=["auth/login.py"],
    max_depth=3
)
```

**When to use:**
- Debugging complex issues spanning multiple files
- Need to understand execution flow
- Have error trace but don't know where to start

---

## Architecture

### Shared Infrastructure

All workflow tools use these shared modules:

**`file_slicer.py`**
- Slices large files intelligently (by symbol or line range)
- Saves 60-80% tokens for large files

**`scope_detector.py`**
- Detects relevant files from task description
- Traces dependencies automatically
- Supports detection from: file paths, git diff, symbol names

**`token_budget_manager.py`**
- Ensures output always fits token budget
- Iterative optimization: full content → smart context → slicing → truncation

**`handoff_formatter.py`**
- Formats output as structured XML prompt
- Includes file map, relationships, action instructions

### Token Budget Optimization Strategy

1. **Try full content** for all files
2. **If over budget:** Convert dependency files to Smart Context (signatures only)
3. **If still over:** Slice primary files by relevant symbols
4. **If still over:** Truncate largest files

---

## Testing

Run workflow tests:
```bash
pytest tests/test_workflows/ -v
```

Test coverage:
- `test_file_slicer.py` — File slicing strategies
- `test_scope_detector.py` — Scope detection accuracy
- `test_context_builder.py` — Tool 1 orchestration
- `test_bug_investigator.py` — Tool 4 tracing logic

---

## Integration with MCP

All 4 tools are exposed via MCP server (`mcp_server/server.py`).

AI clients (Cursor, Copilot, Claude Code) can call them directly:

```bash
# Start MCP server
python main_window.py --run-mcp /path/to/workspace
```

Tools appear in AI client's tool list as:
- `rp_build`
- `rp_review`
- `rp_refactor`
- `rp_investigate`

---

## Performance

**Typical token usage:**

| Tool | Output Size | Token Estimate |
|------|-------------|----------------|
| `rp_build` | File map + sliced contents + relationships | 30K-80K |
| `rp_review` | Diff + changed files + context | 40K-100K |
| `rp_refactor` (discover) | Codemap + dependency graph | 20K-60K |
| `rp_refactor` (plan) | Discovery + full files | 40K-70K |
| `rp_investigate` | Trace steps + sliced files | 30K-80K |

**Optimization applied:**
- Smart Context reduces tokens by 70-80% for dependency files
- File slicing reduces tokens by 60-80% for large files
- Caching prevents re-parsing same files

---

## Future Enhancements

- [ ] NLP-based scope detection (extract file paths from natural language)
- [ ] Cross-language call graph (Python → JS via REST API)
- [ ] Incremental context updates (only send changed files)
- [ ] Visual diff rendering in XML output
- [ ] Test coverage analysis integration
