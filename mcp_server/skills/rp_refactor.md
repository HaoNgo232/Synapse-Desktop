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

### Phase 2: Plan and Execute

```python
# Validate token budget
estimate_tokens(file_paths=["src/legacy_service.py", "src/caller_a.py", "tests/test_legacy.py"])

# Goi cac file can refactor + dependencies vao 1 prompt
build_prompt(
    use_selection=True,  # dung danh sach da tich luy o Phase 1d
    instructions="Refactor LegacyService: extract validation into separate module",
    auto_expand_dependencies=True,
    profile="refactor"
)
```

## Key Principles
- **NEVER refactor without knowing the blast radius first.**
  Always run Phase 1 discovery to find all callers and dependents.
- **Use manage_selection** to accumulate files across multiple exploration steps.
- **Always estimate_tokens** before build_prompt to avoid context overflow.
