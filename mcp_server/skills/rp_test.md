---
name: rp_test
description: >-
  Test generation workflow using Synapse MCP tools.
  Use when user wants to write tests, find coverage gaps,
  or improve test coverage for existing code.
---
# Test Generation Workflow

Find test coverage gaps and prepare context for writing high-quality tests.

## When to Use

- Building unit/integration tests for untested code
- Fixing or improving existing test files
- Want to focus on covering untested methods
- User asks to "write tests" or "improve coverage"

## Step-by-Step Workflow

### Step 0: Initialize Session (MANDATORY)
```python
# Auto-discover: project structure + directory tree + technical debt
start_session()
```

### Step 1: Identify Source Files
```python
# Scan toan bo module can test (thay vi tung file)
batch_codemap(directory="src/services", max_files=20)
# -> Hien thi toan bo functions/classes can duoc test
```

### Step 2: Find Existing Tests
```python
# Tim test file tuong ung (neu co)
get_related_tests(file_paths=["src/service.py"])

# Doc test hien tai de hieu pattern dang dung
get_codemap(file_paths=["tests/test_service.py"])
```

### Step 3: Identify Coverage Gaps
So sanh danh sach functions trong source file voi danh sach
test functions. Nhung ham nao chua co test?

```python
# Doc symbols cua source file
get_symbols(file_path="src/service.py")

# Doc symbols cua test file
get_symbols(file_path="tests/test_service.py")

# So sanh 2 danh sach de xac dinh gaps
```

### Step 4: Validate Token Budget
```python
# Check size truoc khi build prompt
estimate_tokens(file_paths=["src/service.py", "tests/test_service.py"])
```

### Step 5: Package Test Context
```python
build_prompt(
    file_paths=["src/service.py", "tests/test_service.py"],
    instructions="Write tests for untested functions: func_a, func_b",
    auto_expand_dependencies=True
)
```

## Key Principles
- **Read existing tests first to match the team's patterns.**
  New tests should be consistent with the existing test style,
  fixtures, and naming conventions.
- **Use get_symbols** on both source and test files to precisely identify gaps.
- **Always estimate_tokens** before build_prompt to avoid context overflow.
