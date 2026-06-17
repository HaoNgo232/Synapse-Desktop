# AGENTS.md - Synapse Desktop Development Guide

Guidelines and commands for agentic coding agents working on Synapse Desktop - a lightweight AI-assisted code editing tool built with Python and PySide6.

## 1. Build, Lint, and Test Commands

This workflow automates the execution of code formatting, linting, type checking, and unit testing to ensure the codebase remains clean and bug-free.

// turbo-all

1. Format code with Ruff

```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff format .
```

2. Lint code and auto-fix with Ruff

```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff check --fix .
```

3. Type-check with Pyrefly

```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pyrefly check
```

4. Run unit tests with Pytest

```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v
```

### Environment Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running the Application

```bash
# Standard run
python main_window.py
# Or use script
./start.sh

# With debug logging
SYNAPSE_DEBUG=1 python main_window.py
```

### Testing Commands (Pytest)

```bash
# Run ALL tests
pytest tests/ -v

# **Run single test file** (highly recommended for focused iterative changes)
pytest tests/test_token_counter.py -v

# **Run single test class**
pytest tests/test_diff_viewer.py::TestGenerateDiffLines -v

# **Run single test method**
pytest tests/test_token_counter.py::TestCountTokens::test_simple_text -v

# Run with coverage
pytest tests/ --cov=domain --cov=application --cov=presentation -v
```

### Linting & Type Checking

We use `pyrefly` for strict type checking and `ruff` for linting/formatting.

```bash
# Type checking (Strict mode enabled)
pyrefly check

# Check unused imports/variables with ruff
ruff check --select F401,F841 --exclude tests/,stubs/,.agent/ .

# Auto-fix issues & format
ruff check --select F401,F841 --exclude tests/,stubs/,.agent/ --fix .
ruff format .
```

### Building

```bash
# Build AppImage (Linux)
./build-appimage.sh                # Normal build (with license check)
./build-appimage.sh --no-license   # Build without license check
```

```powershell
# Build Windows .exe (PowerShell)
# 1. Standard build (enforces license check) - single EXE + clean cache
.\build-windows.ps1

# 2. Personal build (bypasses license check) - single EXE + clean cache
.\build-windows.ps1 -NoLicense
```

## 2. Code Style Guidelines

### Architecture & Design Patterns

- **Domain-Driven Design (DDD)** is the core architectural pattern.
  - **`domain/`**: Business logic, models, core rules (tokenization, prompt, drift).
  - **`application/`**: Use cases, application services (state, settings).
  - **`infrastructure/`**: External integrations (MCP server, git, filesystem, persistence).
  - **`presentation/`**: UI components (views, components, config, `main_window.py`).
  - **`shared/`**: Common utilities, types, constants.
- **SOLID Principles**: Code must strictly adhere to SOLID design principles (Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion).

### Imports

- **Always use absolute imports** (e.g., `from domain.tokenization...`) instead of relative imports.
- Group imports separated by blank lines: 1. Stdlib, 2. Third-party, 3. Local application.

### Naming Conventions

- **Classes**: `PascalCase` (e.g., `ContextView`)
- **Functions/variables**: `snake_case` (e.g., `scan_directory`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_SETTINGS`)
- **Private methods/vars**: Prefix with underscore (e.g., `_on_folder_picked`)

### Type Hints

- Pyright is configured in `strict` mode.
- **Always use type hints** for function parameters and return values.
- Use `Optional[T]` for nullable values.
- Example: `def load_settings(path: str) -> Dict[str, Any]:`

### Error Handling

- Use `try-except` blocks for I/O, file operations, and external calls.
- Log errors appropriately rather than failing silently.
- Return meaningful error messages to users.
- Use specific exception types when possible (e.g., `OSError`, `json.JSONDecodeError`).

## 3. UI, Performance & Best Practices

### PySide6 UI Threading

- **Thread Safety**: Never update the UI directly from a background thread! Use PySide6 signal/slot mechanism.
- Use `run_on_main_thread()` or `schedule_background()` from `qt_utils` for async operations.

### File Operations & Features

- Always check file existence before operating on it.
- Use context managers (`with open(...)`) for file handling.
- Respect `.gitignore` and exclusion patterns during scans.
- Validate paths to prevent directory traversal.

### Performance

- Offload expensive computations (token counts, file scans) to background threads.
- Implement debounced UI updates for rapid/large operations to prevent freezing.
- Cache token counts and file system reads where possible.

## 4. IDE Context Rules

_(Note: There are no specific standalone `.cursorrules` or Copilot instruction files inside `.cursor/` or `.github/` required as all operational constraints and rules are explicitly defined in this document. Agents must refer directly to this file.)_

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **Synapse-Desktop** (9016 symbols, 18008 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "master"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/Synapse-Desktop/context` | Codebase overview, check index freshness |
| `gitnexus://repo/Synapse-Desktop/clusters` | All functional areas |
| `gitnexus://repo/Synapse-Desktop/processes` | All execution flows |
| `gitnexus://repo/Synapse-Desktop/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
