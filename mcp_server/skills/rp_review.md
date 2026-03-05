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

## Key Principles
- **Understand the blast radius BEFORE reviewing.** A change to a utility
  function used in 20 places needs deeper review than a leaf function.
- **Use get_file_metrics** to assess complexity of changed files.
- **Always estimate_tokens** before build_prompt to avoid context overflow.
