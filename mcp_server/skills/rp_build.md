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

### Step 5: Implementation Plan & Task Decomposition (CRITICAL)
**Act as an Architect/Orchestrator.** Before coding, determine if this is a simple or complex task:

**Simple Task Criteria:**
- Affects ≤10 files in 1-2 related modules
- Estimated tokens <80,000
- Can be implemented in one logical phase

**Complex Task Criteria:**
- Affects 3+ independent modules (e.g., DB + API + UI)
- Estimated tokens >80,000
- Requires sequential implementation (Phase A must complete before Phase B)

**For Complex Tasks - Mandatory Decomposition:**
```python
# Example: "Add authentication to API"
# Phase 1: Database schema changes
build_prompt(
    file_paths=["src/models/user.py", "migrations/add_auth.sql"],
    instructions="Phase 1: Add user authentication tables and models",
    output_file="context_phase1_db.xml"
)

# Phase 2: Authentication logic (depends on Phase 1)
build_prompt(
    file_paths=["src/auth/service.py", "src/auth/middleware.py"],
    instructions="Phase 2: Implement JWT auth service and middleware",
    output_file="context_phase2_auth.xml"
)

# Phase 3: API integration (depends on Phase 2)
build_prompt(
    file_paths=["src/api/routes.py", "src/api/decorators.py"],
    instructions="Phase 3: Add auth decorators to API endpoints",
    output_file="context_phase3_api.xml"
)
```

### Step 6: Strategic Delegation
1. **Check sub-agent availability**: Verify you have a tool for spawning sub-agents.
2. **If NO sub-agent tool exists**: STOP and provide Implementation Plan + context files to user.
3. **If available**:
   - **Simple tasks**: Spawn 1 sub-agent with single context file
   - **Complex tasks**: Spawn sub-agents sequentially (Phase 1 → verify → Phase 2 → verify → Phase 3)

**Sub-agent definition**: A separate AI agent instance (via tool delegation) that can:
- Read generated context files
- Write and modify code
- Run tests to verify changes
- Report success/failure back to orchestrator

### Step 7: Verification Protocol
For each completed phase:
```python
# Orchestrator checks phase completion
verify_phase_completion(
    phase="Phase 1: DB changes",
    success_criteria=["migrations run successfully", "models import without errors"],
    context_file="context_phase1_db.xml"
)
```

## Key Principles
- **Be the Architect.** Don't just gather files; design the implementation sequence.
- **Split complex tasks.** 15 files in one prompt = confusion. 5 files in 3 prompts = precision.
- **Sequential execution.** Each phase must be verified before proceeding to the next.
- **Always estimate_tokens** before build_prompt to avoid context overflow.
- **Use batch_codemap** for module-level scanning, not get_codemap per file.
