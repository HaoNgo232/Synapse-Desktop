# Onion Architecture Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor Synapse-Desktop to establish a strict Onion Architecture: `domain <- application <- infrastructure <- presentation`.

**Architecture:** We decouple domain from infrastructure using Ports (interfaces) and runtime injection via `DomainRegistry` (Composition Root). We update the architecture checker rules to allow the presentation layer to import from the domain layer (since outer-to-inner dependency is valid). We also clean up unused cross-layer imports and relocate presentation-only thread/GUI utilities.

**Tech Stack:** Python 3.12, PySide6, Pytest, Ruff, Pyrefly.

---

### Task 1: Update Governance Checker Rules

**Files:**
- Modify: `tools/architecture/check_architecture.py`

- [ ] **Step 1: Modify FORBIDDEN_IMPORTS in check_architecture.py**

Modify `tools/architecture/check_architecture.py` around line 37:
```python
    "presentation": {"infrastructure"},
```

- [ ] **Step 2: Run strict check to verify no new violations are introduced**

Run:
```bash
.venv/bin/python tools/architecture/check_architecture.py --strict
```
Expected output:
```
Strict check passed: no new architecture violations.
```

- [ ] **Step 3: Commit**

Run:
```bash
git add tools/architecture/check_architecture.py
git commit -m "refactor: allow presentation layer to import domain"
```

---

### Task 2: Create IDirectoryScanner Port & Update DomainRegistry

**Files:**
- Create: `domain/ports/directory_scanner.py`
- Modify: `domain/ports/registry.py`
- Modify: `presentation/service_container.py`
- Create: `tests/domain/test_registry.py`

- [ ] **Step 1: Write failing test for new DomainRegistry ports**

Create `tests/domain/test_registry.py`:
```python
import pytest
from domain.ports.registry import DomainRegistry
from domain.ports.directory_scanner import IDirectoryScanner
from domain.workflow.interfaces.git_port import IGitService
from domain.workflow.interfaces.ast_parser_port import IAstParser
from domain.config.app_settings import AppSettings
from domain.smart_context.tree_item import TreeItem
from pathlib import Path

class DummyDirectoryScanner(IDirectoryScanner):
    def scan_directory(self, root_path: Path) -> TreeItem:
        return TreeItem(label="root", path=str(root_path), is_dir=True)

class DummyGitService(IGitService):
    def get_diffs(self, root_path, base_ref=None):
        return None
    def get_logs(self, root_path, max_commits=10):
        return None

class DummyAstParser(IAstParser):
    def parse_file(self, file_path):
        return {"symbols": []}

def test_registry_new_ports():
    # 1. Directory scanner
    scanner = DummyDirectoryScanner()
    DomainRegistry.register_directory_scanner(scanner)
    assert DomainRegistry.directory_scanner() == scanner

    # 2. Git service
    git = DummyGitService()
    DomainRegistry.register_git_service(git)
    assert DomainRegistry.git_service() == git

    # 3. AST parser
    parser = DummyAstParser()
    DomainRegistry.register_ast_parser(parser)
    assert DomainRegistry.ast_parser() == parser

    # 4. Settings Provider
    DomainRegistry.register_settings_provider(lambda: AppSettings(output_language="Japanese"))
    assert DomainRegistry.settings().output_language == "Japanese"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/domain/test_registry.py -v
```
Expected output:
```
E   ImportError: cannot import name 'IDirectoryScanner' from 'domain.ports.directory_scanner'
```

- [ ] **Step 3: Implement IDirectoryScanner port**

Create `domain/ports/directory_scanner.py`:
```python
import abc
from pathlib import Path
from domain.smart_context.tree_item import TreeItem


class IDirectoryScanner(abc.ABC):
    """
    Interface cho directory scanning o Domain layer.
    """

    @abc.abstractmethod
    def scan_directory(self, root_path: Path) -> TreeItem:
        """Scan a directory recursively and build its TreeItem structure, respecting ignore rules."""
        pass
```

- [ ] **Step 4: Update DomainRegistry class**

Modify `domain/ports/registry.py`:
```python
from typing import Callable, Optional
from domain.ports.tokenization_port import ITokenizationService
from domain.ports.workspace_scanner import IWorkspaceScanner
from domain.ports.directory_scanner import IDirectoryScanner
from domain.workflow.interfaces.git_port import IGitService
from domain.workflow.interfaces.ast_parser_port import IAstParser
from domain.config.app_settings import AppSettings


class DomainRegistry:
    """
    Registry tinh (Service Locator) o Domain layer.
    """

    _tokenization_service: Optional[ITokenizationService] = None
    _workspace_scanner: Optional[IWorkspaceScanner] = None
    _directory_scanner: Optional[IDirectoryScanner] = None
    _git_service: Optional[IGitService] = None
    _ast_parser: Optional[IAstParser] = None
    _settings_provider: Optional[Callable[[], AppSettings]] = None

    @classmethod
    def register_tokenization_service(cls, service: ITokenizationService) -> None:
        cls._tokenization_service = service

    @classmethod
    def tokenization_service(cls) -> ITokenizationService:
        if cls._tokenization_service is None:
            raise RuntimeError(
                "ITokenizationService is not registered in DomainRegistry"
            )
        return cls._tokenization_service

    @classmethod
    def register_workspace_scanner(cls, scanner: IWorkspaceScanner) -> None:
        cls._workspace_scanner = scanner

    @classmethod
    def workspace_scanner(cls) -> IWorkspaceScanner:
        if cls._workspace_scanner is None:
            raise RuntimeError("IWorkspaceScanner is not registered in DomainRegistry")
        return cls._workspace_scanner

    @classmethod
    def register_directory_scanner(cls, scanner: IDirectoryScanner) -> None:
        cls._directory_scanner = scanner

    @classmethod
    def directory_scanner(cls) -> IDirectoryScanner:
        if cls._directory_scanner is None:
            raise RuntimeError("IDirectoryScanner is not registered in DomainRegistry")
        return cls._directory_scanner

    @classmethod
    def register_git_service(cls, service: IGitService) -> None:
        cls._git_service = service

    @classmethod
    def git_service(cls) -> IGitService:
        if cls._git_service is None:
            raise RuntimeError("IGitService is not registered in DomainRegistry")
        return cls._git_service

    @classmethod
    def register_ast_parser(cls, parser: IAstParser) -> None:
        cls._ast_parser = parser

    @classmethod
    def ast_parser(cls) -> IAstParser:
        if cls._ast_parser is None:
            raise RuntimeError("IAstParser is not registered in DomainRegistry")
        return cls._ast_parser

    @classmethod
    def register_settings_provider(cls, provider: Callable[[], AppSettings]) -> None:
        cls._settings_provider = provider

    @classmethod
    def settings(cls) -> AppSettings:
        if cls._settings_provider is None:
            return AppSettings()
        return cls._settings_provider()
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/domain/test_registry.py -v
```
Expected output:
```
tests/domain/test_registry.py::test_registry_new_ports PASSED
```

- [ ] **Step 6: Update ServiceContainer to register the ports**

Modify `presentation/service_container.py`:
Add imports:
```python
from infrastructure.filesystem.file_utils import ConcreteDirectoryScanner
from infrastructure.git.git_utils import GitService
from infrastructure.adapters.ast_parser import AstParser
from infrastructure.persistence.settings_manager import load_app_settings
```
At the end of `__init__`:
```python
        DomainRegistry.register_tokenization_service(self._tokenization_service)
        DomainRegistry.register_workspace_scanner(WorkspaceScanner())
        DomainRegistry.register_directory_scanner(ConcreteDirectoryScanner(self.ignore_engine))
        DomainRegistry.register_git_service(GitService())
        DomainRegistry.register_ast_parser(AstParser())
        DomainRegistry.register_settings_provider(load_app_settings)
```

And in `infrastructure/filesystem/file_utils.py`, add `ConcreteDirectoryScanner` implementing `IDirectoryScanner`:
```python
from domain.ports.directory_scanner import IDirectoryScanner

class ConcreteDirectoryScanner(IDirectoryScanner):
    def __init__(self, ignore_engine: IgnoreEngine):
        self.ignore_engine = ignore_engine

    def scan_directory(self, root_path: Path) -> TreeItem:
        return scan_directory(root_path, self.ignore_engine)
```

- [ ] **Step 7: Commit**

Run:
```bash
git add domain/ports/directory_scanner.py domain/ports/registry.py presentation/service_container.py infrastructure/filesystem/file_utils.py tests/domain/test_registry.py
git commit -m "refactor: add directory scanner, git, ast ports and registry bindings"
```

---

### Task 3: Refactor Domain Workflow Files (Decoupling Infrastructure)

**Files:**
- Modify: `domain/workflow/context_builder.py`
- Modify: `domain/workflow/design_planner.py`
- Modify: `domain/workflow/test_builder.py`
- Modify: `domain/workflow/code_reviewer.py`
- Modify: `domain/workflow/shared/scope_detector.py`
- Modify: `domain/workflow/shared/hybrid_investigation_graph.py`

- [ ] **Step 1: Write test case in conftest.py to register registry dependencies before workflow tests run**

Modify `tests/conftest.py` (or create if not exists) to configure dummy registry bindings for workflow tests:
```python
import pytest
from domain.ports.registry import DomainRegistry
from domain.ports.directory_scanner import IDirectoryScanner
from domain.workflow.interfaces.git_port import IGitService
from domain.workflow.interfaces.ast_parser_port import IAstParser
from domain.smart_context.tree_item import TreeItem
from pathlib import Path

class TestDirScanner(IDirectoryScanner):
    def scan_directory(self, root_path: Path) -> TreeItem:
        from infrastructure.filesystem.file_utils import scan_directory
        from infrastructure.filesystem.ignore_engine import IgnoreEngine
        return scan_directory(root_path, IgnoreEngine())

class TestGit(IGitService):
    def get_diffs(self, root_path, base_ref=None):
        from infrastructure.git.git_utils import get_git_diffs
        return get_git_diffs(root_path, base_ref=base_ref)
    def get_logs(self, root_path, max_commits=10):
        from infrastructure.git.git_utils import get_git_logs
        return get_git_logs(root_path, max_commits=max_commits)

class TestAst(IAstParser):
    def parse_file(self, file_path):
        from infrastructure.adapters.ast_parser import AstParser
        return AstParser().parse_file(file_path)

@pytest.fixture(autouse=True)
def setup_test_registry():
    DomainRegistry.register_directory_scanner(TestDirScanner())
    DomainRegistry.register_git_service(TestGit())
    DomainRegistry.register_ast_parser(TestAst())
```

- [ ] **Step 2: Decouple domain/workflow/context_builder.py**

Modify `domain/workflow/context_builder.py`:
- Remove: `from infrastructure.filesystem.file_utils import scan_directory`
- Remove: `from infrastructure.filesystem.ignore_engine import IgnoreEngine`
- Replace line 121-124:
```python
    from domain.ports.registry import DomainRegistry

    tree = DomainRegistry.directory_scanner().scan_directory(ws)
```
- Replace line 142:
```python
            from domain.ports.registry import DomainRegistry

            git_diff_result = DomainRegistry.git_service().get_diffs(ws)
```
- Modify signature parameter to set default `git_service = None`, and retrieve from registry if None:
```python
    if git_service is None:
        from domain.ports.registry import DomainRegistry
        try:
            git_service = DomainRegistry.git_service()
        except RuntimeError:
            pass
```

- [ ] **Step 3: Decouple domain/workflow/design_planner.py**

Modify `domain/workflow/design_planner.py`:
- Remove: `from infrastructure.filesystem.file_utils import scan_directory`
- Replace line 261-264:
```python
    from domain.ports.registry import DomainRegistry

    tree = DomainRegistry.directory_scanner().scan_directory(ws)
```

- [ ] **Step 4: Decouple domain/workflow/test_builder.py**

Modify `domain/workflow/test_builder.py`:
- Remove: `from infrastructure.filesystem.file_utils import scan_directory`
- Replace line 175-178:
```python
    from domain.ports.registry import DomainRegistry

    tree = DomainRegistry.directory_scanner().scan_directory(ws)
```

- [ ] **Step 5: Decouple domain/workflow/code_reviewer.py**

Modify `domain/workflow/code_reviewer.py`:
- Replace line 123-125:
```python
            from domain.ports.registry import DomainRegistry

            diff_result = DomainRegistry.git_service().get_diffs(ws, base_ref=base_ref)
```
- Modify signature parameter:
```python
    if git_service is None:
        from domain.ports.registry import DomainRegistry
        try:
            git_service = DomainRegistry.git_service()
        except RuntimeError:
            pass
```

- [ ] **Step 6: Decouple domain/workflow/shared/scope_detector.py**

Modify `domain/workflow/shared/scope_detector.py`:
- Replace line 120-122:
```python
            from domain.ports.registry import DomainRegistry

            diff_result = DomainRegistry.git_service().get_diffs(workspace_path)
```

- [ ] **Step 7: Decouple domain/workflow/shared/hybrid_investigation_graph.py**

Modify `domain/workflow/shared/hybrid_investigation_graph.py`:
- Replace line 175-177:
```python
            from domain.ports.registry import DomainRegistry

            logs = DomainRegistry.git_service().get_logs(workspace_root, max_commits=10)
```

- [ ] **Step 8: Run pytest to ensure workflows function perfectly**

Run:
```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_workflows/ -v
```
Expected output:
```
All workflow tests PASSED
```

- [ ] **Step 9: Commit**

Run:
```bash
git add domain/workflow/ tests/conftest.py
git commit -m "refactor: decouple workflow files from direct infrastructure dependencies"
```

---

### Task 4: Refactor remaining Domain files

**Files:**
- Modify: `domain/codemap/canonical_structure.py`
- Modify: `domain/prompt/file_collector.py`
- Modify: `domain/prompt/template_manager.py`
- Modify: `domain/prompt/assembler.py`

- [ ] **Step 1: Decouple domain/codemap/canonical_structure.py**

Modify `domain/codemap/canonical_structure.py`:
- Replace line 148-154:
```python
                from domain.ports.registry import DomainRegistry

                ast_parser = DomainRegistry.ast_parser()
                repo_map = _generate_repo_map_with_parser(
                    ast_parser,
                    source_files,
                    workspace_root=workspace_root,
                    max_files=max_repo_map_files,
                )
```

- [ ] **Step 2: Decouple domain/prompt/file_collector.py**

Modify `domain/prompt/file_collector.py` line 16:
```python
from shared.utils.file_utils import is_binary_file
```

- [ ] **Step 3: Decouple domain/prompt/template_manager.py**

Modify `domain/prompt/template_manager.py` line 298:
```python
        from domain.ports.registry import DomainRegistry

        return DomainRegistry.settings().output_language
```

- [ ] **Step 4: Decouple domain/prompt/assembler.py**

Modify `domain/prompt/assembler.py` line 21:
```python
from shared.types.git_types import GitDiffResult, GitLogResult
```

- [ ] **Step 5: Run tests**

Run:
```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v
```
Expected: All tests pass.

- [ ] **Step 6: Commit**

Run:
```bash
git add domain/codemap/canonical_structure.py domain/prompt/file_collector.py domain/prompt/template_manager.py domain/prompt/assembler.py
git commit -m "refactor: resolve remaining domain-to-infrastructure violations"
```

---

### Task 5: Clean up Application Layer Unused Methods

**Files:**
- Modify: `application/services/preview_analyzer.py`
- Modify: `application/services/error_context/__init__.py`

- [ ] **Step 1: Clean up preview_analyzer.py**

Modify `application/services/preview_analyzer.py`:
- Delete `get_change_color` function (lines 285-300).
- Remove unused import of `ThemeColors` on line 292.

- [ ] **Step 2: Clean up error_context/__init__.py**

Modify `application/services/error_context/__init__.py`:
- Delete `copy_error_to_clipboard` function (lines 225-233).
- Remove unused import `from infrastructure.adapters.clipboard_utils import copy_to_clipboard` on line 23.

- [ ] **Step 3: Run pytest and check architecture violations**

Run:
```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v
.venv/bin/python tools/architecture/check_architecture.py
```
Expected: Current violations count is reduced.

- [ ] **Step 4: Commit**

Run:
```bash
git add application/services/preview_analyzer.py application/services/error_context/__init__.py
git commit -m "refactor: clean up unused functions and presentation/infra imports in application"
```

---

### Task 6: Relocate qt_utils.py to Presentation Layer

**Files:**
- Create: `presentation/utils/qt_utils.py` (move from `infrastructure/adapters/qt_utils.py`)
- Modify: Update all files importing `qt_utils` to point to `presentation.utils.qt_utils`.

- [ ] **Step 1: Move qt_utils.py**

Run:
```bash
mkdir -p presentation/utils
git mv infrastructure/adapters/qt_utils.py presentation/utils/qt_utils.py
```

- [ ] **Step 2: Update imports of qt_utils in views, dialogs, and tests**

Find and replace all `infrastructure.adapters.qt_utils` with `presentation.utils.qt_utils` in the workspace.
Files to modify:
- `presentation/components/dialogs/dialogs_qt.py`
- `presentation/views/apply/apply_view_qt.py`
- `presentation/views/context/tree_management_controller.py`
- `presentation/views/context/context_view_qt.py`
- `presentation/main_window.py`
- `tests/...` (all tests referencing it)

- [ ] **Step 3: Run pytest to verify no regression**

Run:
```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v
```

- [ ] **Step 4: Commit**

Run:
```bash
git add presentation/ infrastructure/adapters/ tests/
git commit -m "refactor: relocate qt_utils to presentation layer"
```

---

### Task 7: Update Baseline & Enforce Strict Architecture Check

**Files:**
- Modify: `tools/architecture/baseline.json`

- [ ] **Step 1: Write new baseline**

Run:
```bash
.venv/bin/python tools/architecture/check_architecture.py --write-baseline
```

- [ ] **Step 2: Run strict check to verify success**

Run:
```bash
.venv/bin/python tools/architecture/check_architecture.py --strict
```
Expected: `Strict check passed: no new architecture violations.` (violations count should be significantly lower/zero!).

- [ ] **Step 3: Run final checks (ruff, pyrefly, pytest)**

Run:
```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff check --fix .
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff format .
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pyrefly check
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v
```
Expected: All pass with 0 errors.

- [ ] **Step 4: Commit**

Run:
```bash
git add tools/architecture/baseline.json
git commit -m "refactor: update architecture baseline"
```
