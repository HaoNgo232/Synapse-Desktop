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
# Doc doan code xung quanh loi: dung built-in read_file voi offset/limit
# Vi du: read_file("src/module.py", offset=39, limit=31)  # dong 40-70

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
    profile="bugfix",
    output_file="context.xml"
)
```

### Step 6: Write Root Cause Analysis (BEFORE fixing)
Before writing any fix, produce a Root Cause Analysis (RCA) that includes:
- **What happened**: Describe the observed bug/error behavior.
- **Why it happened**: Explain the root cause at code level.
- **Which code paths are affected**: List functions/files involved.
- **Proposed fix**: Describe the fix approach and expected outcome.

This prevents the agent from applying superficial patches that mask
the real issue. Only proceed to code changes after the RCA is clear.

### Step 7: Root Cause Analysis & Task Decomposition

#### 7a. Write Comprehensive RCA (MANDATORY)
Before any fixing, produce a Root Cause Analysis:

**What Happened:**
- Exact error behavior observed
- When/where the error occurs
- Affected user scenarios

**Why It Happened:**
- Root cause at code level
- Contributing factors (race conditions, edge cases, etc.)
- How the bug was introduced

**Impact Analysis:**
- Which code paths are affected
- Data corruption risks
- User experience impact

**Proposed Fix Strategy:**
- Specific code changes needed
- Testing approach
- Rollback plan if fix fails

#### 7b. Task Decomposition for Complex Bugs
**Single Bug (affects 1-2 files):**
```python
build_prompt(
    use_selection=True,
    instructions="RCA: <your analysis>. Implement the proposed fix strategy.",
    output_file="context_bugfix.xml"
)
```

**Multi-Component Bug (affects 3+ modules):**
```python
# Fix database layer first
build_prompt(
    file_paths=["src/db/connection.py", "tests/test_db.py"],
    instructions="Bug Fix Phase 1: Fix connection pool leak in database layer. RCA: <analysis>",
    output_file="context_bugfix_db.xml"
)

# Then fix API layer (depends on DB fix)
build_prompt(
    file_paths=["src/api/handlers.py", "tests/test_api.py"],
    instructions="Bug Fix Phase 2: Fix timeout handling in API layer. RCA: <analysis>",
    output_file="context_bugfix_api.xml"
)
```

**Multiple Independent Bugs:**
```python
# Bug 1: Auth timeout
build_prompt(
    file_paths=["src/auth/login.py"],
    instructions="Bug 1 Fix: Login timeout after 30s. RCA: <analysis>",
    output_file="context_bug1_auth.xml"
)

# Bug 2: Memory leak (independent)
build_prompt(
    file_paths=["src/cache/redis.py"],
    instructions="Bug 2 Fix: Memory leak in Redis client. RCA: <analysis>",
    output_file="context_bug2_cache.xml"
)
```

#### 7c. Strategic Delegation
1. **Check sub-agent availability**: Verify you have a tool for spawning sub-agents.
2. **If NO sub-agent tool exists**: STOP and provide RCA + context files to user.
3. **If available**:
   - **Single bug**: Spawn 1 sub-agent with RCA + context
   - **Multi-component bug**: Spawn sub-agents sequentially (fix DB → verify → fix API)
   - **Multiple bugs**: Spawn sub-agents in parallel (each fixes one bug independently)

**Sub-agent verification protocol**: Each sub-agent must:
- Apply the fix according to RCA
- Run tests to verify bug is resolved
- Report success/failure with test results

## Key Principles
- **RCA before fixing.** Never patch without understanding root cause.
- **Sequential fixes for dependent bugs.** Parallel fixes for independent bugs.
- **Test verification mandatory.** Each fix must be verified before next phase.
- **Use manage_selection** to accumulate suspect files as you trace.
- **Always estimate_tokens** before build_prompt to avoid context overflow. If user provides a `max_tokens` limit, treat it as a hard ceiling, not a target. Lower is always better.
