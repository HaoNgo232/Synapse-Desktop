---
trigger: glob
---

# AGENTS.md - Synapse Desktop Development Guide

Guidelines and commands for agentic coding agents working on Synapse Desktop - a lightweight AI-assisted code editing tool built with Python and PySide6.

## Build & Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Standard run
python main_window.py
# OR
./start.sh

# With debug logging
SYNAPSE_DEBUG=1 python main_window.py
```

### Testing Commands
```bash
# Run ALL tests
pytest tests/ -v

# Run single test file
pytest tests/test_token_counter.py -v

# Run single test class
pytest tests/test_diff_viewer.py::TestGenerateDiffLines -v

# Run single test method
pytest tests/test_token_counter.py::TestCountTokens::test_simple_text -v

# Run with coverage
pytest tests/ --cov=core --cov=services --cov=components -v
```

### Linting & Type Checking
```bash
# Type checking with pyrefly
pyrefly check

# Check unused imports/variables with ruff
ruff check --select F401,F841 --exclude tests/,stubs/,.agent/ .

# Auto-fix issues
ruff check --select F401,F841 --exclude tests/,stubs/,.agent/ --fix .

# Full ruff check (all rules)
ruff check .

# Format code with ruff
ruff format .
```

### Building
```bash
# Build AppImage (Linux only)
./build-appimage.sh
```

## Code Style Guidelines

### Import Style
- **Always use absolute imports** instead of relative imports
- Group imports in this order with blank lines between:
  1. Standard library imports
  2. Third-party imports
  3. Local application imports

```python
# Good example
import os
import json
from pathlib import Path
from typing import Optional, Dict, List

from PySide6 import QtWidgets as qw
import pytest

from views.context_view_qt import ContextViewQt
from core.utils.file_utils import scan_directory, TreeItem
```

### Naming Conventions
- **Classes**: `PascalCase` (e.g., `ContextView`, `FileTreeComponent`)
- **Functions/variables**: `snake_case` (e.g., `scan_directory`, `workspace_path`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_SETTINGS`, `BINARY_EXTENSIONS`)
- **Private methods**: Prefix with underscore (e.g., `_on_folder_picked`)

### File Structure
- **Services**: `services/` - Background services and utilities
- **Core**: `core/` - Business logic and main functionality
- **Views**: `views/` - UI components and screens
- **Components**: `components/` - Reusable UI widgets
- **Config**: `config/` - Configuration and constants

### Type Hints
- **Always use type hints** for function parameters and return values
- Use `Optional[T]` for nullable values
- Use `Dict[str, Any]` for JSON-like data structures

```python
def load_settings() -> Dict[str, Any]:
def _get_workspace_path(self) -> Optional[Path]:
def generate_prompt(
    self,
    selected_paths: Set[str],
    instructions: str,
) -> str:
```

### Documentation Style
- **Vietnamese comments** for business logic and user-facing text
- **English comments** for technical implementation details
- Use triple quotes for docstrings
- Include parameter and return type information in docstrings

```python
# Vietnamese for business logic
"""
Context View - Tab de chon files va copy context
"""

# English for technical details
def _on_folder_picked(self, e: ft.FilePickerResultEvent):
    """Xu ly khi user chon folder"""
```

### Error Handling
- Use try-except blocks for file operations and external calls
- Log errors appropriately using the logging system
- Return meaningful error messages to users
- Use specific exception types when possible

```python
def load_settings() -> Dict[str, Any]:
    try:
        if SETTINGS_FILE.exists():
            content = SETTINGS_FILE.read_text(encoding="utf-8")
            saved = json.loads(content)
            return {**DEFAULT_SETTINGS, **saved}
    except (OSError, json.JSONDecodeError):
        pass
    return DEFAULT_SETTINGS.copy()
```

## Project Architecture

### Core Components
- **File Tree**: `components/file_tree.py` - Hierarchical file navigation
- **Token Counter**: `core/token_counter.py` - Token counting with tiktoken/rs-bpe
- **Smart Context**: `core/smart_context/` - Tree-sitter based code analysis
- **Security**: `core/security_check.py` - Secret detection with detect-secrets
- **OPX System**: `core/opx_parser.py` - Apply operations in OPX format

### Services
- **Settings**: `services/settings_manager.py` - Application settings persistence
- **Session**: `services/session_state.py` - Workspace and UI state management
- **File Watcher**: `services/file_watcher.py` - Auto-refresh on file changes
- **History**: `services/history_service.py` - Operation history tracking

## Best Practices

### Thread Safety (PySide6)
- Use PySide6 signal/slot mechanism for thread safety
- Use `run_on_main_thread()` or `schedule_background()` from `qt_utils` for async operations
- Follow the existing theme structure (`ThemeColors`)

### File Operations
- Always check file existence before operations
- Use context managers for file handling
- Implement proper error handling for I/O operations
- Respect `.gitignore` and exclusion patterns

### Security
- Always validate file paths to prevent directory traversal
- Use dry-run mode for destructive operations
- Scan for secrets before copying code context

### Performance
- Use async operations for file scanning and token counting
- Implement debounced UI updates for large operations
- Cache expensive computations (token counts, file scans)
- Clear token caches when workspace changes

### Testing
- Use `pytest` for unit tests
- Test both success and failure cases
- Use descriptive test method names
- Include setup and teardown for test isolation
- Test security features thoroughly

## Debugging & Logging
- Use `SYNAPSE_DEBUG=1` environment variable for verbose logging
- Check `~/.synapse-desktop/logs/app.log` for application logs
- Use the Logs tab in the UI for real-time logging

## Notes for Agents
- This is a desktop application using PySide6 for the UI
- The project uses tree-sitter for smart code context extraction
- Security scanning is a core feature using detect-secrets
- Token counting is essential for LLM context management
- Vietnamese comments are used for business logic and user-facing text
