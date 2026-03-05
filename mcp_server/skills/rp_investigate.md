---
name: rp_investigate
description: >-
  Bug investigation workflow using Synapse MCP tools.
  Use when user reports a bug, has an error trace,
  or needs to trace execution path to find root cause.
---
# Bug Investigation Workflow

Systematic bug investigation by tracing execution paths through the
codebase to find the root cause.

## When to Use

- Debugging complex issues spanning multiple files
- Have an error trace but don't know where to start
- Need to understand execution flow
- User reports a bug or error

## Step-by-Step Workflow

### Step 0: Initialize Session (MANDATORY)
```python
# Auto-discover: project structure + directory tree + technical debt
start_session()
```

### Step 1: Parse the Error
If user gave an error trace, identify the file and line number
where the error originates. If no trace, search for the bug:
```python
# Tim function/class lien quan den bug
find_references(symbol_name="suspected_function")
```

### Step 2: Read Code at Error Points
```python
# Doc doan code xung quanh loi
read_file_range(
    relative_path="src/module.py",
    start_line=40,
    end_line=70
)

# Xem structure cua file: functions/classes va line ranges
get_symbols(file_path="src/module.py")
```

### Step 3: Trace the Call Chain
```python
# Ai goi ham bi loi? Trace nguoc len
get_callers(symbol_name="broken_function")

# Xem dependency graph
get_imports_graph(file_paths=["src/module.py"], max_depth=2)
```

### Step 4: Accumulate Suspect Files (Stateful)
```python
# Tich luy file nghi van dan dan khi trace
manage_selection(action="clear")
manage_selection(action="add", paths=["src/module.py"])  # crash point
manage_selection(action="add", paths=["src/caller.py"])  # caller
manage_selection(action="add", paths=["tests/test_module.py"])  # related test

# Kiem tra danh sach
manage_selection(action="get")
```

### Step 5: Validate and Package Investigation Context
```python
# Check token budget truoc
estimate_tokens(file_paths=["src/module.py", "src/caller.py", "tests/test_module.py"])

build_prompt(
    use_selection=True,
    instructions="Investigate: <bug description>. Root cause analysis needed.",
    auto_expand_dependencies=True,
    profile="bugfix"
)
```

## Key Principles
- **Trace from the error outward.** Start at the crash point,
  then follow the call chain upward to find where the data went wrong.
- **Use manage_selection** to accumulate suspect files as you trace.
- **Always estimate_tokens** before build_prompt to avoid context overflow.
