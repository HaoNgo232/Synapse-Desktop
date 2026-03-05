---
name: rp_build
description: >-
  Implementation context builder workflow using Synapse MCP tools.
  Use when user wants to start a new feature, build implementation context,
  or prepare a handoff prompt for another agent.
---
# Context Builder Workflow

Build optimized implementation context by exploring the codebase first,
then packaging the relevant files into a structured prompt.

## When to Use

- Starting a new feature implementation
- Need to understand code structure before making changes
- Want to hand off context to another AI agent
- User asks to "build context" or "prepare implementation"

## Step-by-Step Workflow

### Step 0: Initialize Session (MANDATORY)
```python
# Auto-discover: project structure + directory tree + technical debt (TODO/FIXME)
start_session()

# Hieu kien truc tong the: entry points, module boundaries, coupling
explain_architecture(focus_directory="src")
```

### Step 1: Module-level Exploration
```python
# Scan toan bo module mot lan thay vi tung file (tiet kiem round-trips)
batch_codemap(directory="src/auth", max_files=20)

# Tim noi mot symbol duoc su dung trong project
find_references(symbol_name="UserService")
```

### Step 2: Trace Dependencies
```python
# Xem file nao import file nao
get_imports_graph(file_paths=["src/auth/login.py"], max_depth=2)

# Tim xem ai goi ham nay - de hieu blast radius
get_callers(symbol_name="validate_token")
```

### Step 3: Validate Token Budget
```python
# LUON check size truoc khi build prompt de tranh crash context window
estimate_tokens(file_paths=["src/auth/login.py", "src/api/routes.py", "src/models/user.py"])
# Neu > 80k tokens -> loai bot file hoac dung output_format="smart"
```

### Step 4: Build the Context Prompt
Once you have identified the exact files (2-10 files), package them:
```python
build_prompt(
    file_paths=["src/auth/login.py", "src/api/routes.py", "src/models/user.py"],
    instructions="Implement rate limiting for login endpoint",
    output_format="xml",  # "xml" = full source, "smart" = codemap + key sections
    auto_expand_dependencies=True,
    output_file="context.xml"  # optional: save for cross-agent handoff
)
```

## Key Principles
- **YOU explore first, THEN package.** Never blindly select all files.
- **Pick only 2-10 files** that are directly relevant to the task.
- **Always estimate_tokens** before build_prompt to avoid context overflow.
- **Use batch_codemap** for module-level scanning, not get_codemap per file.
