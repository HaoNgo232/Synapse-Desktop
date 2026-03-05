---
name: rp_refactor
description: >-
  Two-pass refactoring workflow using Synapse MCP tools.
  Use when user wants to refactor code safely with
  analysis-first approach.
---
# Refactoring Workflow

Safe refactoring with analysis-first approach: discover dependencies
and risks before making any changes.

## When to Use

- Large refactoring that affects multiple files
- Need to ensure backward compatibility
- Want to understand risks before making changes
- User asks to "refactor" or "restructure" code

## Step-by-Step Workflow

### Step 0: Initialize Session (MANDATORY)
```python
# Auto-discover: project structure + directory tree + technical debt
start_session()
```

### Phase 1: Discovery (DO NOT SKIP)

#### 1a. Locate the Target
```python
# Tim module/function can refactor
find_references(symbol_name="LegacyService")

# Scan toan bo module lien quan
batch_codemap(directory="src/legacy", max_files=20)
```

#### 1b. Map Dependencies
```python
# Ai import file nay?
get_imports_graph(file_paths=["src/legacy_service.py"], max_depth=2)

# Ai goi cac ham trong file nay?
get_callers(symbol_name="LegacyService.process")

# Tim test hien tai
get_related_tests(file_paths=["src/legacy_service.py"])
```

#### 1c. Assess Risk
```python
# Danh gia do phuc tap
get_file_metrics(file_path="src/legacy_service.py")
```

Document your findings: number of callers, test coverage, coupling points.

#### 1d. Accumulate Files (Stateful)
```python
# Tich luy file dan dan thay vi nho list thu cong
manage_selection(action="clear")
manage_selection(action="add", paths=["src/legacy_service.py"])
manage_selection(action="add", paths=["src/caller_a.py", "src/caller_b.py"])
manage_selection(action="add", paths=["tests/test_legacy.py"])

# Kiem tra danh sach hien tai
manage_selection(action="get")
```

### Phase 2: Refactoring Strategy & Task Decomposition

#### 2a. Apply "No Big Bang" Rule
**CRITICAL**: Never refactor everything at once. Break into atomic phases:

**Example Decomposition:**
```python
# Phase 1: Extract new module (non-breaking)
build_prompt(
    file_paths=["src/legacy_service.py"],
    instructions="Phase 1: Extract validation logic to new ValidationService module. Keep LegacyService working.",
    output_file="context_refactor_phase1.xml"
)

# Phase 2: Update callers one by one (after Phase 1 verified)
build_prompt(
    file_paths=["src/caller_a.py", "tests/test_caller_a.py"],
    instructions="Phase 2: Update caller_a to use ValidationService. Maintain backward compatibility.",
    output_file="context_refactor_phase2a.xml"
)

build_prompt(
    file_paths=["src/caller_b.py", "tests/test_caller_b.py"],
    instructions="Phase 2: Update caller_b to use ValidationService. Maintain backward compatibility.",
    output_file="context_refactor_phase2b.xml"
)

# Phase 3: Remove deprecated methods (after all callers updated)
build_prompt(
    file_paths=["src/legacy_service.py"],
    instructions="Phase 3: Remove deprecated validation methods from LegacyService",
    output_file="context_refactor_phase3.xml"
)
```

#### 2b. Strategic Delegation
1. **Check sub-agent availability**: Verify you have a tool for spawning sub-agents.
2. **If NO sub-agent tool exists**: STOP and provide Refactoring Plan + phase contexts to user.
3. **If available**: Execute phases sequentially with verification:
   - Phase 1 → run tests → Phase 2a → run tests → Phase 2b → run tests → Phase 3

**Sub-agent instructions**: Each phase must:
- Complete its changes
- Run all tests to ensure no breakage
- Report success before next phase can begin

#### 2c. Rollback Strategy
For each phase, prepare rollback instructions:
```python
# Include in each context file
rollback_instructions = """
If tests fail after this phase:
1. Git revert the changes
2. Report which specific test failed
3. Do NOT proceed to next phase
"""
```

## Key Principles
- **"No Big Bang" refactoring.** Always break into atomic, reversible phases.
- **Test after each phase.** Never accumulate untested changes.
- **One caller at a time.** Don't update multiple callers simultaneously.
- **Always estimate_tokens** before build_prompt to avoid context overflow.
- **Use manage_selection** to accumulate files across multiple exploration steps.
