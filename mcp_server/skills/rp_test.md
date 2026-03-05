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
### Step 5: Test Strategy & Coverage Gap Analysis

#### 5a. Comprehensive Coverage Analysis
Compare source symbols with test symbols to identify gaps:

```python
# Get all functions/classes in source
get_symbols(file_path="src/service.py")
# Get all test functions
get_symbols(file_path="tests/test_service.py")

# Manual analysis: Which source functions have NO corresponding test?
# Prioritize by risk: critical business logic > utility functions > getters/setters
```

**Coverage Gap Prioritization:**
1. **Critical (must test)**: Business logic, security functions, data validation
2. **Important (should test)**: API endpoints, error handling, edge cases
3. **Nice-to-have**: Simple getters, utility functions, logging

#### 5b. Test Plan Creation (BEFORE writing tests)
Produce a Test Plan that includes:

**Test Framework Analysis:**
- Which framework is used? (pytest, jest, vitest, etc.)
- What patterns to follow? (fixtures, mocks, parametrize)
- How to run tests? (command, CI integration)

**Coverage Strategy:**
- **Unit tests**: Test individual functions in isolation
- **Integration tests**: Test module interactions
- **Edge case tests**: Boundary conditions, error paths

**Test Data Strategy:**
- What fixtures/mocks are needed?
- How to handle database/API dependencies?
- Test data cleanup requirements

#### 5c. Task Decomposition for Large Test Suites

**Single Module (≤10 functions):**
```python
build_prompt(
    file_paths=["src/service.py", "tests/test_service.py"],
    instructions="Test Plan: <your plan>. Write tests for priority functions: func_a, func_b, func_c",
    output_file="context_tests.xml"
)
```

**Multiple Modules (3+ modules or >100 functions):**
```python
# Per-module test contexts
build_prompt(
    file_paths=["src/auth/service.py", "tests/auth/test_service.py"],
    instructions="Test Plan Phase 1: Write comprehensive tests for auth module",
    output_file="context_tests_auth.xml"
)

build_prompt(
    file_paths=["src/api/routes.py", "tests/api/test_routes.py"],
    instructions="Test Plan Phase 2: Write API endpoint tests with error handling",
    output_file="context_tests_api.xml"
)

build_prompt(
    file_paths=["src/db/models.py", "tests/db/test_models.py"],
    instructions="Test Plan Phase 3: Write database model tests with edge cases",
    output_file="context_tests_db.xml"
)
```

#### 5d. Strategic Delegation
1. **Check sub-agent availability**: Verify you have a tool for spawning sub-agents.
2. **If NO sub-agent tool exists**: STOP and provide Test Plan + context files to user.
3. **If available**:
   - **Single module**: Spawn 1 sub-agent with Test Plan + context
   - **Multiple modules**: Spawn N sub-agents in parallel (each handles one module)

**Sub-agent verification protocol**: Each sub-agent must:
- Write tests according to Test Plan
- Run tests to ensure they pass
- Measure coverage improvement
- Report test results and coverage metrics

**Sub-agent definition**: A separate AI agent instance that can write code, execute test commands, and measure coverage.

## Key Principles
- **Test Plan before test code.** Always understand the testing strategy first.
- **Match existing patterns.** New tests should be consistent with team conventions.
- **Parallel testing for independent modules.** Don't wait for auth tests to finish before starting API tests.
- **Coverage verification mandatory.** Each sub-agent must report coverage metrics.
- **Use get_symbols** on both source and test files to precisely identify gaps.
- **Always estimate_tokens** before build_prompt to avoid context overflow. If user provides a `max_tokens` limit, treat it as a hard ceiling, not a target. Lower is always better.