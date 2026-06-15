# Remaining Architecture Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up the remaining 59 import violations, 3 God Services, and 28 Layer Cycles by introducing domain ports, setting up a static service locator registry, relocating/splitting the DependencyResolver into the domain layer, and splitting the other two God services into focused submodules.

**Architecture:** Onion/Hexagonal Architecture. Decouple Domain layer from outer layers using Dependency Inversion Principle (DIP) and Domain Registry. Split services by logical sub-responsibility.

**Tech Stack:** Python 3.12, PySide6, pytest, ruff, pyrefly, AST parsing, tree-sitter.

---

## File Structure Map

### New Files:
- `domain/ports/tokenization_port.py`: `ITokenizationService` abstract base class.
- `domain/ports/workspace_scanner.py`: `IWorkspaceScanner` abstract base class.
- `domain/ports/registry.py`: `DomainRegistry` service locator.
- `domain/smart_context/tree_item.py`: `TreeItem` dataclass relocated from infrastructure.
- `shared/types/llm_types.py`: `LLMMessage` dataclass relocated from infrastructure.
- `domain/codemap/dependency_resolver/__init__.py`: Package init exporting `DependencyResolver`.
- `domain/codemap/dependency_resolver/resolver.py`: Cleaned `DependencyResolver` coordinator.
- `domain/codemap/dependency_resolver/js_resolver.py`: TypeScript/JS import resolver.
- `domain/codemap/dependency_resolver/python_resolver.py`: Python import resolver.
- `application/services/tokenization/parallel_counter.py`: Parallel and batch token counter methods.
- `application/services/error_context/formatters.py`: Prompts and formatting helpers for error context.

### Modified Files:
- `infrastructure/filesystem/file_utils.py`: Remove `TreeItem`, import from `domain.smart_context.tree_item`.
- `infrastructure/ai/base_provider.py`: Remove `LLMMessage`, import from `shared.types.llm_types`.
- `presentation/service_container.py`: Register dependencies to `DomainRegistry`.
- `application/services/tokenization_service.py`: Split out helper functions.
- `application/services/error_context.py`: Split out formatting helpers.
- `tools/architecture/check_architecture.py`: Exclude `presentation/service_container.py`.
- `presentation/views/context/copy_action_controller.py`: Clean direct imports of infrastructure.

---

## Tasks

### Task 1: Setup Ports and Move Base Dataclasses

**Files:**
- Create: [tokenization_port.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/ports/tokenization_port.py)
- Create: [workspace_scanner.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/ports/workspace_scanner.py)
- Create: [tree_item.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/smart_context/tree_item.py)
- Create: [llm_types.py](file:///home/hao/Desktop/labs/Synapse-Desktop/shared/types/llm_types.py)
- Modify: [file_utils.py](file:///home/hao/Desktop/labs/Synapse-Desktop/infrastructure/filesystem/file_utils.py)
- Modify: [base_provider.py](file:///home/hao/Desktop/labs/Synapse-Desktop/infrastructure/ai/base_provider.py)

- [ ] **Step 1: Move TreeItem to domain**
  Create `domain/smart_context/tree_item.py`:
  ```python
  from dataclasses import dataclass, field

  @dataclass
  class TreeItem:
      label: str  # Ten hien thi (filename/dirname)
      path: str  # Duong dan tuyet doi
      is_dir: bool = False
      children: list["TreeItem"] = field(default_factory=list)
      is_loaded: bool = True  # True = đã scan, False = chưa scan (lazy)
  ```

- [ ] **Step 2: Move ITokenizationService to domain**
  Create `domain/ports/tokenization_port.py`:
  ```python
  from abc import ABC, abstractmethod
  from pathlib import Path
  from typing import Dict, List, Optional

  class ITokenizationService(ABC):
      @abstractmethod
      def count_tokens(self, text: str) -> int:
          pass

      @abstractmethod
      def count_tokens_for_file(self, file_path: Path) -> int:
          pass

      @abstractmethod
      def count_tokens_batch_parallel(
          self,
          file_paths: List[Path],
          max_workers: int = 2,
          update_cache: bool = True,
      ) -> Dict[str, int]:
          pass

      @abstractmethod
      def set_model_config(self, tokenizer_repo: Optional[str] = None) -> None:
          pass

      @abstractmethod
      def reset_encoder(self) -> None:
          pass

      @abstractmethod
      def clear_cache(self) -> None:
          pass

      @abstractmethod
      def clear_file_from_cache(self, path: str) -> None:
          pass
  ```

- [ ] **Step 3: Create Workspace Scanner interface**
  Create `domain/ports/workspace_scanner.py`:
  ```python
  import abc
  from pathlib import Path
  from typing import List

  class IWorkspaceScanner(abc.ABC):
      @abc.abstractmethod
      def collect_files(self, folder: Path) -> List[str]:
          """Scan folder recursively and return paths of non-ignored files."""
          pass
  ```

- [ ] **Step 4: Move LLMMessage to shared**
  Create `shared/types/llm_types.py`:
  ```python
  from dataclasses import dataclass

  @dataclass
  class LLMMessage:
      role: str  # "system" | "user" | "assistant"
      content: str
  ```

- [ ] **Step 5: Modify old files to import moved components**
  Modify `infrastructure/filesystem/file_utils.py`:
  Replace old `TreeItem` definition (lines 84-98) with:
  ```python
  from domain.smart_context.tree_item import TreeItem
  ```
  Modify `infrastructure/ai/base_provider.py`:
  Replace old `LLMMessage` definition (lines 24-35) with:
  ```python
  from shared.types.llm_types import LLMMessage
  ```
  Modify `application/interfaces/tokenization_port.py`:
  Replace old content with:
  ```python
  from domain.ports.tokenization_port import ITokenizationService
  ```

- [ ] **Step 6: Update all files importing old TreeItem / LLMMessage**
  Using a search and replace or editing target files to ensure they import from `domain.smart_context.tree_item` and `shared.types.llm_types`.
  Specifically modify:
  - `domain/codemap/canonical_structure.py`
  - `domain/codemap/graph_builder.py`
  - `domain/codemap/tree_map_generator.py`
  - `domain/prompt/generator.py`
  - `domain/tokenization/comparison_service.py`
  - `domain/prompt/context_builder_prompts.py`
  - `application/services/dependency_resolver.py`
  - `presentation/views/context/copy_action_controller.py`
  - `presentation/components/file_tree/file_tree_model.py`

- [ ] **Step 7: Run pytest to ensure baseline tests pass**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v`
  Expected: All 592 tests PASS.

- [ ] **Step 8: Commit changes**
  Run: `git add . && git commit -m "refactor: relocate TreeItem, ITokenizationService, and LLMMessage to domain/shared"`


### Task 2: Implement DomainRegistry & Hook Up Container

**Files:**
- Create: [registry.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/ports/registry.py)
- Modify: [service_container.py](file:///home/hao/Desktop/labs/Synapse-Desktop/presentation/service_container.py)
- Modify: [workspace_index.py](file:///home/hao/Desktop/labs/Synapse-Desktop/application/services/workspace_index.py)

- [ ] **Step 1: Create DomainRegistry**
  Create `domain/ports/registry.py`:
  ```python
  from typing import Optional
  from domain.ports.tokenization_port import ITokenizationService
  from domain.ports.workspace_scanner import IWorkspaceScanner

  class DomainRegistry:
      _tokenization_service: Optional[ITokenizationService] = None
      _workspace_scanner: Optional[IWorkspaceScanner] = None

      @classmethod
      def register_tokenization_service(cls, service: ITokenizationService) -> None:
          cls._tokenization_service = service

          # Backward compatibility for old encoder_registry wrapper
          try:
              from infrastructure.adapters import encoder_registry
              encoder_registry._tokenization_service = service
          except ImportError:
              pass

      @classmethod
      def tokenization_service(cls) -> ITokenizationService:
          if cls._tokenization_service is None:
              raise RuntimeError("ITokenizationService not registered in DomainRegistry")
          return cls._tokenization_service

      @classmethod
      def register_workspace_scanner(cls, scanner: IWorkspaceScanner) -> None:
          cls._workspace_scanner = scanner

      @classmethod
      def workspace_scanner(cls) -> IWorkspaceScanner:
          if cls._workspace_scanner is None:
              raise RuntimeError("IWorkspaceScanner not registered in DomainRegistry")
          return cls._workspace_scanner
  ```

- [ ] **Step 2: Create scanner adapter class in application layer**
  Modify `application/services/workspace_index.py`:
  Add the implementation at the bottom of the file:
  ```python
  from domain.ports.workspace_scanner import IWorkspaceScanner

  class WorkspaceScanner(IWorkspaceScanner):
      def collect_files(self, folder: Path) -> List[str]:
          return collect_files_from_disk(folder, workspace_path=folder)
  ```

- [ ] **Step 3: Register instances in ServiceContainer**
  Modify `presentation/service_container.py`:
  At the end of `__init__` (line 76), add:
  ```python
  from domain.ports.registry import DomainRegistry
  from application.services.workspace_index import WorkspaceScanner

  DomainRegistry.register_tokenization_service(self._tokenization_service)
  DomainRegistry.register_workspace_scanner(WorkspaceScanner())
  ```

- [ ] **Step 4: Run tests to verify setup**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v`
  Expected: PASS

- [ ] **Step 5: Commit changes**
  Run: `git add . && git commit -m "refactor: introduce DomainRegistry and register services in Composition Root"`


### Task 3: Decouple Domain from Application Services

**Files:**
- Modify: `domain/tokenization/counter.py`
- Modify: `domain/tokenization/comparison_service.py`
- Modify: `domain/prompt/generator.py`
- Modify: `domain/prompt/context_trimmer.py`
- Modify: `domain/workflow/` workflow files

- [ ] **Step 1: Fix counter.py importing infrastructure.adapters.encoders**
  Modify `domain/tokenization/counter.py`:
  Remove `from infrastructure.adapters.encoders import _estimate_tokens` (line 24).
  Define `_estimate_tokens` locally:
  ```python
  def _estimate_tokens(text: str) -> int:
      if not text:
          return 0
      return max(1, len(text) // 4)
  ```

- [ ] **Step 2: Fix context_trimmer.py and token_budget_manager.py**
  Modify `domain/prompt/context_trimmer.py` and `domain/workflow/shared/token_budget_manager.py`:
  Update `ITokenizationService` imports to `domain/ports/tokenization_port`.

- [ ] **Step 3: Update domain workflows to use DomainRegistry**
  Replace imports of `TokenizationService` or `ITokenizationService` from `application` layer with `DomainRegistry.tokenization_service()`.
  Specifically modify:
  - `domain/workflow/context_builder.py`
  - `domain/workflow/test_builder.py`
  - `domain/workflow/refactor_workflow.py`
  - `domain/workflow/bug_investigator.py`
  - `domain/workflow/code_reviewer.py`
  - `domain/workflow/design_planner.py`
  - `domain/workflow/shared/risk_engine.py`

- [ ] **Step 4: Update workflows to resolve files via DomainRegistry scanner**
  Replace direct imports of `collect_files_from_disk` in the workflows with calls to `DomainRegistry.workspace_scanner().collect_files(folder)`.
  Modify:
  - `domain/workflow/code_reviewer.py`
  - `domain/workflow/shared/risk_engine.py`
  - `domain/workflow/shared/scope_detector.py`
  - `domain/workflow/shared/hybrid_investigation_graph.py`

- [ ] **Step 5: Run pytest**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v`
  Expected: PASS

- [ ] **Step 6: Commit changes**
  Run: `git add . && git commit -m "refactor: decouple domain workflows and prompts from application services via registry"`


### Task 4: Relocate and Split DependencyResolver

**Files:**
- Create: `domain/codemap/dependency_resolver/js_resolver.py`
- Create: `domain/codemap/dependency_resolver/python_resolver.py`
- Create: `domain/codemap/dependency_resolver/resolver.py`
- Create: `domain/codemap/dependency_resolver/__init__.py`
- Delete: `application/services/dependency_resolver.py`

- [ ] **Step 1: Implement JS/TS resolver**
  Create `domain/codemap/dependency_resolver/js_resolver.py` as defined in the spec.

- [ ] **Step 2: Implement Python resolver**
  Create `domain/codemap/dependency_resolver/python_resolver.py` as defined in the spec.

- [ ] **Step 3: Implement main DependencyResolver**
  Create `domain/codemap/dependency_resolver/resolver.py` as defined in the spec.

- [ ] **Step 4: Expose class in init**
  Create `domain/codemap/dependency_resolver/__init__.py`:
  ```python
  from domain.codemap.dependency_resolver.resolver import DependencyResolver

  __all__ = ["DependencyResolver"]
  ```

- [ ] **Step 5: Delete application service and redirect imports**
  Delete `application/services/dependency_resolver.py`.
  Update imports of `DependencyResolver` in all files to:
  ```python
  from domain.codemap.dependency_resolver import DependencyResolver
  ```
  Check files:
  - `domain/workflow/design_planner.py`
  - `domain/workflow/shared/handoff_formatter.py`
  - `domain/workflow/shared/usage_aware_test_matcher.py`
  - `domain/workflow/shared/hybrid_investigation_graph.py`
  - `domain/workflow/shared/scope_detector.py`
  - `domain/workflow/shared/risk_engine.py`
  - `presentation/views/context/related_files_controller.py`

- [ ] **Step 6: Run tests to verify DependencyResolver relocation**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v`
  Expected: PASS

- [ ] **Step 7: Commit changes**
  Run: `git add . && git commit -m "refactor: split and relocate DependencyResolver to domain/codemap/"`


### Task 5: Split TokenizationService

**Files:**
- Create: `application/services/tokenization/parallel_counter.py`
- Modify: `application/services/tokenization_service.py`

- [ ] **Step 1: Move parallel processing methods to parallel_counter.py**
  Create `application/services/tokenization/parallel_counter.py`:
  Include functions: `_count_tokens_parallel_standard`, `_count_tokens_batch_hf`, `_count_tokens_batch_sequential`, `_count_tokens_for_file_no_cache`, `_read_file_mmap` extracted from `tokenization_service.py`.

- [ ] **Step 2: Clean TokenizationService in application/services/tokenization_service.py**
  Modify `application/services/tokenization_service.py`:
  Import functions from `application.services.tokenization.parallel_counter` and delegate the parallel batch work to them in `count_tokens_batch_parallel`.
  Ensure `TokenizationService` file is under 250 lines.

- [ ] **Step 3: Run pytest**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v`
  Expected: PASS

- [ ] **Step 4: Commit changes**
  Run: `git add . && git commit -m "refactor: split parallel counting logic out of TokenizationService"`


### Task 6: Split ErrorContext

**Files:**
- Create: `application/services/error_context/formatters.py`
- Modify: `application/services/error_context.py`

- [ ] **Step 1: Move prompts formatting to formatters.py**
  Create `application/services/error_context/formatters.py`:
  Extract all internal formatting helpers: `_build_focused_error_context`, `_build_success_section`, `_build_failed_section`, `_build_change_block_details`, `_build_fix_instructions`, `_read_current_file_content`, `_find_preview_row` from `error_context.py`.

- [ ] **Step 2: Clean error_context.py**
  Modify `application/services/error_context.py`:
  Import formatting helpers from `application.services.error_context.formatters` and delegate `build_error_context_for_ai` and `build_general_error_context`.
  Ensure `error_context.py` is under 150 lines.

- [ ] **Step 3: Run pytest**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v`
  Expected: PASS

- [ ] **Step 4: Commit changes**
  Run: `git add . && git commit -m "refactor: split formatting prompt logic out of error_context.py"`


### Task 7: Fix Presentation Layer Imports and Exclude Composition Root

**Files:**
- Modify: `presentation/views/context/copy_action_controller.py`
- Modify: `tools/architecture/check_architecture.py`

- [ ] **Step 1: Clean copy_action_controller.py direct imports**
  Modify `presentation/views/context/copy_action_controller.py`:
  - Replace `from infrastructure.filesystem.file_utils import scan_directory` with an application layer wrapper.
  - Define `scan_directory_wrapper` in `application/services/workspace_index.py` (which just delegates to `infrastructure.filesystem.file_utils.scan_directory`).
  - Import `is_binary_file` from `shared.utils.file_utils` instead of `infrastructure.filesystem.file_utils`.
  - Import `load_app_settings` from `application/services/workspace_config` instead of `infrastructure.persistence.settings_manager`.

- [ ] **Step 2: Add Composition Root exclusion in check_architecture.py**
  Modify `tools/architecture/check_architecture.py`:
  Exclude `presentation/service_container.py` inside `_iter_python_files()`:
  ```python
  if str(py_file).replace("\\", "/").endswith("presentation/service_container.py"):
      continue
  ```

- [ ] **Step 3: Run check_architecture to verify remaining violations**
  Run: `.venv/bin/python tools/architecture/check_architecture.py`
  Expected: No violations outside the baseline, or significantly reduced violations.

- [ ] **Step 4: Update baseline.json**
  Run: `.venv/bin/python tools/architecture/check_architecture.py --write-baseline`
  Expected: Baseline updated successfully. The count of violations should decrease.

- [ ] **Step 5: Run tests to verify all integrations**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v`
  Expected: PASS

- [ ] **Step 6: Commit changes**
  Run: `git add . && git commit -m "refactor: resolve presentation import violations and exclude composition root"`
