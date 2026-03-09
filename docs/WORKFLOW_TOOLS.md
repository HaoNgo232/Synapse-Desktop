# Workflow Tools Documentation

## Overview

Synapse Desktop provides 6 advanced workflow tools designed for AI agent handoff and complex coding tasks. These tools automate context gathering, scope detection, and prompt generation.

## Tools

### 1. `rp_build` — Context Builder

**Purpose:** Automatically prepare optimized context for implementing a new feature or task.

**What it does:**
- Detects relevant files from task description
- Traces dependencies automatically
- Slices large files to include only relevant sections
- Optimizes content to fit token budget
- Generates structured handoff prompt
- Decomposes complex tasks into sequential phases (e.g., DB → Auth → API)
- Supports strategic delegation to sub-agents with verification protocol

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
- Performs comprehensive Review Analysis (Security, Performance, Breaking Changes, Test Coverage)
- Packages everything into comprehensive review prompt
- Splits large PRs (>20 files) into focused review phases

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
- Enforces "No Big Bang" rule: breaks refactor into atomic, reversible phases
- Ensures backward compatibility
- Suggests migration steps if needed
- Generates rollback instructions for each phase

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
- Enforces comprehensive Root Cause Analysis (RCA) before any fixes
- Handles multi-component bugs via sequential fix phases (DB → API → UI)
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

### 5. `rp_test` — Test Generation Workflow

**Purpose:** Automate writing tests by finding coverage gaps and preparing the optimal prompt.

**What it does:**
- Finds all source files and their corresponding test files
- Extracts functions/methods/classes dynamically
- Maps tested code to test functions (via fuzzy heuristics)
- Identifies missing coverage directly from static analysis
- Recommends which untested targets to prioritize (HIGH/MEDIUM/LOW)
- Auto-detects testing frameworks (pytest, jest, vitest)
- Suggests new test file paths if missing
- Creates comprehensive Test Plan (Framework Analysis, Coverage Strategy, Test Data Strategy) before code generation
- Formats analysis into an AI agent-ready plan

**Usage:**
```python
# To generate tests for new changes
rp_test(
    workspace_path="/path/to/project",
    task_description="Implement tests for the new login functionality",
    file_paths=["auth/login.py"],
    max_tokens=60_000
)

# Using Git Diff (staged/unstaged) context
rp_test(
    workspace_path="/path/to/project",
    task_description="Cover changes in the recent PR",
    include_git_changes=True
)
```

**When to use:**
- Building unit/integration tests for untested code
- Fixing or improving existing test files
- Want AI to focus exclusively on covering untested methods

---

### 6. `rp_design` — Architectural Design Planner

**Purpose:** Produce an architectural design and implementation plan based on task requirements, identifying scope, dependencies, impact, and a step-by-step rollout strategy.

**What it does:**
- Analyzes existing conventions, anti-patterns, and project structure (via Contract Pack)
- Extracts APIs and current architectural references
- Assesses the blast radius of proposed changes
- Identifies migration needs and rollout steps
- Defines a comprehensive plan including a "do-not-touch" list to prevent drift
- Packages all guidelines and constraints into learning material for building the architecture

**Usage:**
```python
rp_design(
    workspace_path="/path/to/project",
    task_description="Migrate local SQLite memory storage to a remote Redis implementation",
    max_tokens=80_000
)
```

**When to use:**
- Starting a brand new subsystem or feature that impacts multiple domains
- Deciding between architectural choices before making code changes
- Establishing API contracts and planning large-scale application structural updates

---

## Agent Skills vs MCP Workflow Tools

**Important Distinction:**

**MCP Workflow Tools (6 tools):** These are the core workflow tools exposed via MCP server (`infrastructure/mcp/handlers/workflow_handler.py`):
- `rp_build`, `rp_design`, `rp_review`, `rp_refactor`, `rp_investigate`, `rp_test`
- Called directly by AI clients via MCP protocol
- Implemented as Python functions in the MCP server

**Agent Skills (7 skills):** These are workflow templates installed to IDE skill directories:
- Stored as Markdown files in `infrastructure/mcp/skills/*.md`
- Include all 6 MCP tools above PLUS `rp_export_context`
- `rp_export_context` is NOT a separate MCP tool—it's a workflow that uses the existing `build_prompt` tool
- Installed via Settings → Skills System → Install to [IDE]

**Key Point:** `rp_export_context` appears in skill lists but is actually a wrapper workflow around `build_prompt`, designed specifically for manual handoff to external LLMs (ChatGPT, Claude Web).

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

All 6 workflow tools are exposed via MCP server (`infrastructure/mcp/server.py`).

AI clients (Cursor, GitHub Copilot, Claude Code, Antigravity, Kiro CLI, OpenCode) can call them directly:

```bash
# Start MCP server
python main_window.py --run-mcp /path/to/workspace
```

Tools appear in AI client's tool list as:
- `rp_build`
- `rp_design`
- `rp_review`
- `rp_refactor`
- `rp_investigate`
- `rp_test`

---

## Performance

**Typical token usage:**

| Tool | Output Size | Token Estimate |
|------|-------------|----------------|
| `rp_build` | File map + sliced contents + relationships | 30K-80K |
| `rp_design` | Contract pack + codemaps + constraints | 30K-70K |
| `rp_review` | Diff + changed files + context | 40K-100K |
| `rp_refactor` (discover) | Codemap + dependency graph | 20K-60K |
| `rp_refactor` (plan) | Discovery + full files | 40K-70K |
| `rp_investigate` | Trace steps + sliced files | 30K-80K |
| `rp_test` | Coverage result + source/test context | 20K-80K |

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
- [x] Test coverage analysis integration
- [x] Task decomposition and strategic delegation
- [x] Root Cause Analysis (RCA) enforcement
- [x] Agent Skills system integration
- [x] Oracle export workflow for external LLM handoff
