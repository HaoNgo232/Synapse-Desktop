---
name: rp_review
description: >-
  Code review workflow using Synapse MCP tools.
  Use when user wants to review code changes, check a PR,
  or understand impact of recent modifications.
---
# Code Review Workflow

Perform deep code review by understanding git changes, finding impacted
callers and tests, then packaging everything for analysis.

## When to Use

- Before merging a PR or pushing changes
- Need to understand impact of recent changes
- Want to detect side effects and breaking changes
- User asks to "review code" or "check my changes"

## Step-by-Step Workflow

### Step 0: Initialize Session (MANDATORY)
```python
# Auto-discover: project structure + directory tree + technical debt
start_session()
```

### Step 1: See What Changed
```python
# Tong quan nhanh: file nao duoc add/modify/delete
diff_summary(target="HEAD")
```

### Step 2: Understand the Changed Code
```python
# Xem symbols (functions/classes) trong file bi thay doi
get_symbols(file_path="src/changed_file.py")

# Danh gia do phuc tap cua file
get_file_metrics(file_path="src/changed_file.py")

# Doc chi tiet 1 doan code cu the neu can
read_file_range(relative_path="src/changed_file.py", start_line=50, end_line=80)
```

### Step 3: Find Blast Radius
```python
# Hieu kien truc module chua code bi thay doi
explain_architecture(focus_directory="src/changed_module")

# Tim xem ai goi cac ham da thay doi
get_callers(symbol_name="changed_function_name")

# Tim test files tuong ung
get_related_tests(file_paths=["src/changed_file.py"])
```

### Step 4: Validate Token Budget
```python
# Check size truoc khi build prompt
estimate_tokens(file_paths=["src/changed_file.py", "tests/test_changed.py"])
```

### Step 5: Package Review Context
```python
build_prompt(
    file_paths=["src/changed_file.py", "tests/test_changed.py"],
    instructions="Review these changes for correctness, security, and performance",
    include_git_changes=True,
    profile="review"
)
```

### Step 6: Review Analysis (BEFORE delegation)
Before delegating, produce a comprehensive Review Analysis:

**Security Analysis:**
- SQL injection vulnerabilities
- XSS attack vectors
- Authentication/authorization bypasses
- Secrets or credentials in code

**Performance Analysis:**
- N+1 query patterns
- Blocking I/O operations
- Memory leaks or resource leaks
- Inefficient algorithms

**Breaking Change Analysis:**
- Public API signature changes
- Removed or renamed functions
- Changed behavior that affects callers
- Database schema changes

**Test Coverage Analysis:**
- Are existing tests sufficient?
- What edge cases need new tests?
- Do integration tests cover the changes?

### Step 7: Strategic Delegation
**For Small PRs (≤20 files, <100k tokens):**
```python
build_prompt(
    file_paths=changed_files,
    instructions="Review Analysis: <your analysis>. Focus on security and breaking changes.",
    include_git_changes=True,
    output_file="context_review.xml"
)
```

**For Large PRs (>20 files or >100k tokens) - Mandatory Split:**
```python
# Split by concern
build_prompt(
    file_paths=core_logic_files,
    instructions="Review Analysis Phase 1: Focus on core logic changes and security",
    output_file="context_review_core.xml"
)

build_prompt(
    file_paths=test_files,
    instructions="Review Analysis Phase 2: Focus on test coverage and edge cases",
    output_file="context_review_tests.xml"
)

build_prompt(
    file_paths=api_files,
    instructions="Review Analysis Phase 3: Focus on API changes and breaking changes",
    output_file="context_review_api.xml"
)
```

**Delegation Protocol:**
1. **Check sub-agent availability**: Verify you have a tool for spawning sub-agents.
2. **If NO sub-agent tool exists**: STOP and provide Review Analysis + context files to user.
3. **If available**: Spawn sub-agents with specific focus areas (security reviewer, performance reviewer, etc.)

**Sub-agent definition**: A separate AI agent instance that can read code, analyze patterns, and identify issues.

## Key Principles
- **Split large reviews.** Don't overwhelm one agent with 50 files.
- **Focus-specific delegation.** Security agent ≠ Performance agent ≠ Test coverage agent.
- **Analysis before action.** Always produce Review Analysis before delegating.
- **Always estimate_tokens** before build_prompt to avoid context overflow.
