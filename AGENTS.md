# AGENTS.md - Synapse Desktop Development Guide

This document provides guidelines and commands for agentic coding agents working on the Synapse Desktop project.

## Project Overview

Synapse Desktop is a lightweight AI-assisted code editing tool built with Python and PySide6. It provides file context management for LLMs with features like smart context extraction, OPX apply operations, and comprehensive security scanning.

## Build & Development Commands

### Environment Setup
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Virtual Environment Check

**CRITICAL**: Always verify and activate the virtual environment before running any commands!

```bash
# Check if virtual environment exists and activate
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

# Verify activation (should show path to .venv)
echo $VIRTUAL_ENV
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
# Run ALL tests (activate venv first)
source .venv/bin/activate && pytest tests/ -v

# Run all tests with output
source .venv/bin/activate && pytest tests/ -v -s

# Run single test file
pytest tests/test_opx_parser.py -v

# Run single test class
pytest tests/test_diff_viewer.py::TestGenerateDiffLines -v

# Run single test method
pytest tests/test_token_counter.py::TestCountTokens::test_simple_text -v

# Run tests with coverage
pytest tests/ --cov=core --cov=services --cov=components -v

# Type checking
pyrefly check
```

### Performance Testing Commands

```bash
# Run ALL performance tests (activate venv first)
source .venv/bin/activate && pytest tests/test_ui_performance.py tests/test_real_user_behavior.py tests/test_scan_bottleneck.py tests/test_token_counting_fix.py -v -s

# Test UI rendering performance (all scenarios)
pytest tests/test_ui_performance.py -v -s

# Test real user behavior (giả lập expand/select/copy)
pytest tests/test_real_user_behavior.py -v -s

# Test specific user workflow with large project
pytest tests/test_real_user_behavior.py::TestRealUserBehavior::test_user_workflow_paas_k3s -v -s

# Test scan directory bottleneck
pytest tests/test_scan_bottleneck.py -v -s

# Test token counting fix
pytest tests/test_token_counting_fix.py -v -s

# Test rapid user interaction (spam clicks)
pytest tests/test_real_user_behavior.py::TestRealUserBehavior::test_rapid_interaction -v -s

# Test with timeout (for long-running tests)
timeout 60 pytest tests/test_scan_bottleneck.py -v -s
```

**Performance Test Options:**
- `-v`: Verbose output (show test names)
- `-s`: Show print statements (performance metrics)
- `--tb=short`: Short traceback on failures
- `-x`: Stop on first failure
- `-k "pattern"`: Run tests matching pattern

**Performance Test Files:**
- `test_ui_performance.py` - UI rendering benchmarks (render, expand, select, search)
- `test_real_user_behavior.py` - Real user workflow simulation (expand/select/copy)
- `test_scan_bottleneck.py` - Scan directory analysis (shallow vs full scan)
- `test_token_counting_fix.py` - Token counting coverage verification

**Key Findings:**
- UI render: 0.6ms for 2844 files ✅
- Expand/select: ~400ms (bottleneck - needs lazy expand fix) ⚠️
- Scan directory: 941ms (can optimize with shallow scan) ⚠️
- Token counting: 100% coverage after fix ✅

See `BOTTLENECK_FOUND.md` and `PERFORMANCE_REPORT.md` for details.

### Linting & Formatting

```bash
# Type checking with pyrefly
pyrefly check

# Check specific file
pyrefly check main.py

# Show pyrefly configuration
pyrefly show
```

### Building
```bash
# Build AppImage (Linux only)
./build-appimage.sh
```

## Code Style Guidelines

### Import Style
- **Always use absolute imports** instead of relative imports
- Group imports in this order:
  1. Standard library imports
  2. Third-party imports
  3. Local application imports
- Use blank lines between import groups

```python
# Example import style
import os
import json
from pathlib import Path
from typing import Optional, Dict, List

from PySide6 import QtWidgets as qw
import pytest

from views.context_view_qt import ContextViewQt
from core.utils.file_utils import scan_directory, TreeItem
```

### File Structure & Naming
- **Services**: `services/` - Background services and utilities
- **Core**: `core/` - Business logic and main functionality
- **Views**: `views/` - UI components and screens
- **Components**: `components/` - Reusable UI widgets
- **Config**: `config/` - Configuration and constants

**Naming conventions**:
- Classes: `PascalCase` (e.g., `ContextView`, `FileTreeComponent`)
- Functions/variables: `snake_case` (e.g., `scan_directory`, `workspace_path`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_SETTINGS`, `BINARY_EXTENSIONS`)
- Private methods: Prefix with underscore (e.g., `_on_folder_picked`)

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

### Type Hints
- **Always use type hints** for function parameters and return values
- Use `Optional[T]` for nullable values
- Use `Dict[str, Any]` for JSON-like data structures
- Import from `typing` module when needed

```python
def load_settings() -> Dict[str, Any]:
def _get_workspace_path(self) -> Optional[Path]:
def generate_prompt(
    self,
    selected_paths: Set[str],
    instructions: str,
    output_style: OutputStyle,
) -> str:
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

### UI Development (PySide6)
- Use PySide6 signal/slot mechanism for thread safety
- Follow the existing theme structure (`ThemeColors`)
- Use `run_on_main_thread()` or `schedule_background()` from `qt_utils` for async operations
- Implement proper error handling for UI operations

```python
self.page.theme = ft.Theme(
    color_scheme_seed=ThemeColors.PRIMARY,
    color_scheme=ft.ColorScheme(
        primary=ThemeColors.PRIMARY,
        on_primary="#FFFFFF",
        # ... other theme colors
    ),
)
```

### Testing Guidelines
- Use `pytest` for unit tests
- Test both success and failure cases
- Use descriptive test method names
- Include setup and teardown for test isolation
- Test security features thoroughly

```python
class TestGenerateDiffLines:
    """Test generate_diff_lines() function"""

    def test_simple_modification(self):
        """Test diff cho mot thay doi don gian"""
        # Test implementation
```

## Project Architecture

### Core Components
- **File Tree**: `components/file_tree.py` - Hierarchical file navigation
- **Token Counter**: `core/token_counter.py` - Token counting with tiktoken
- **Smart Context**: `core/smart_context/` - Tree-sitter based code analysis
- **Security**: `core/security_check.py` - Secret detection with detect-secrets
- **OPX System**: `core/opx_parser.py` - Apply operations in OPX format

### Services
- **Settings**: `services/settings_manager.py` - Application settings persistence
- **Session**: `services/session_state.py` - Workspace and UI state management
- **File Watcher**: `services/file_watcher.py` - Auto-refresh on file changes
- **History**: `services/history_service.py` - Operation history tracking

## Security Considerations

- Always validate file paths to prevent directory traversal
- Use dry-run mode for destructive operations
- Scan for secrets before copying code context
- Implement proper access controls for file operations

## Performance Guidelines

- Use async operations for file scanning and token counting
- Implement debounced UI updates for large operations
- Cache expensive computations (token counts, file scans)
- Monitor memory usage and implement cleanup mechanisms

## Debugging & Logging

- Use `SYNAPSE_DEBUG=1` environment variable for verbose logging
- Check `~/.synapse-desktop/logs/app.log` for application logs
- Use the Logs tab in the UI for real-time logging
- Implement proper error context for debugging

## Common Patterns

### Thread Safety
- Use `safe_page_update()` for UI updates from background threads
- Implement proper shutdown procedures for background services
- Use thread-safe data structures when needed

### File Operations
- Always check file existence before operations
- Use context managers for file handling
- Implement proper error handling for I/O operations
- Respect `.gitignore` and exclusion patterns

### Memory Management
- Clear token caches when workspace changes
- Implement garbage collection for large operations
- Monitor memory usage and provide user feedback
- Use streaming for large file operations when possible

## Development Workflow

1. **Setup**: Create virtual environment and install dependencies
2. **Development**: Use hot reload for UI changes
3. **Testing**: Run tests for new functionality
4. **Type Checking**: Use pyrefly for type validation
5. **Building**: Test AppImage build if making changes to packaging
6. **Documentation**: Update this file with new patterns or commands

## Notes for Agents

- This is a desktop application using PySide6 for the UI
- The project uses tree-sitter for smart code context extraction
- Security scanning is a core feature using detect-secrets
- Token counting is essential for LLM context management
- The application follows a service-oriented architecture
- Vietnamese comments are used for business logic and user-facing text