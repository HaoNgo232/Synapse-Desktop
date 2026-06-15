# Design Spec: Remaining Architecture Refactoring & God Services Split

**Date**: 2026-06-15  
**Topic**: Remaining Architecture Refactoring  
**Goal**: Resolve the remaining 59 import violations, 3 God Services, and 28 Layer Cycles in Synapse Desktop to achieve a strictly clean Onion/Hexagonal Architecture.

---

## 1. Problem Description & Context

After Phase 1 of the architecture refactoring, we successfully resolved domain-to-infrastructure config violations. However, the codebase still contains several historical architectural issues:
1.  **Domain imports outer layers**: Domain prompt and workflow modules directly import `TokenizationService`, `DependencyResolver`, and `collect_files_from_disk` from the `application` layer, as well as `TreeItem` and `LLMMessage` from the `infrastructure` layer.
2.  **Layer Cycles**: Bidirectional dependency loops exist between layers (e.g., `application -> domain -> application`), caused by the forbidden imports.
3.  **God Services**: Three service files exceed the 450-line maximum governance limit:
    *   `application/services/dependency_resolver.py` (955 lines)
    *   `application/services/error_context.py` (593 lines)
    *   `application/services/tokenization_service.py` (540 lines)

---

## 2. Proposed Changes

We propose **Domain-Driven Radical Isolation** to completely decouple the Domain layer from outer layers and split the God Services into smaller, focused components.

### Component 1: Domain Ports & Registry Setup

To decouple `domain` from concrete services and file systems, we will introduce interfaces (Ports) and a static service locator registry in the Domain layer.

#### [NEW] [tokenization_port.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/ports/tokenization_port.py)
*   **Action**: Move `ITokenizationService` abstract class from `application/interfaces/tokenization_port.py`.
*   **Rationale**: Allows the domain layer to count tokens via an interface without importing the application layer.

#### [NEW] [workspace_scanner.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/ports/workspace_scanner.py)
*   **Action**: Create `IWorkspaceScanner` interface.
    ```python
    import abc
    from pathlib import Path
    from typing import List

    class IWorkspaceScanner(abc.ABC):
        @abc.abstractmethod
        def collect_files(self, folder: Path) -> List[str]:
            """Scan a folder recursively and return path strings of non-ignored files."""
            pass
    ```

#### [NEW] [registry.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/ports/registry.py)
*   **Action**: Implement `DomainRegistry` to store and resolve runtime concrete instances of `ITokenizationService` and `IWorkspaceScanner`.
*   **Rationale**: Since Python domain modules contain pure functions that cannot easily use constructor injection, they will resolve dependencies dynamically via this registry.

---

### Component 2: Splitting & Relocating DependencyResolver

`DependencyResolver` contains core domain logic for resolving code dependencies, but currently lives in `application` and is excessively large. We will relocate it to the `domain` layer and break it down.

#### [NEW] [dependency_resolver package](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/codemap/dependency_resolver/)
Create a package folder `domain/codemap/dependency_resolver/` containing:
*   `__init__.py`: Export the main `DependencyResolver` class for backward compatibility.
*   `resolver.py`: The main coordinator class (under 300 lines) that accepts `IWorkspaceScanner` for filesystem scans.
*   `js_resolver.py`: Handles TS/JS import resolution and loading `tsconfig.json`/`jsconfig.json`.
*   `python_resolver.py`: Handles Python standard and relative import resolutions.

#### [DELETE] [dependency_resolver.py](file:///home/hao/Desktop/labs/Synapse-Desktop/application/services/dependency_resolver.py)
*   Delete the old monolithic file.

---

### Component 3: Moving Types and Shared Utilities to Domain/Shared

#### [NEW] [tree_item.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/smart_context/tree_item.py)
*   **Action**: Relocate `TreeItem` dataclass from `infrastructure/filesystem/file_utils.py` to `domain/smart_context/tree_item.py`.
*   **Rationale**: Cập nhật các import tương ứng trong toàn bộ codebase. `TreeItem` is a domain-wide representation of a file structure.

#### [NEW] [llm_types.py](file:///home/hao/Desktop/labs/Synapse-Desktop/shared/types/llm_types.py)
*   **Action**: Relocate `LLMMessage` dataclass from `infrastructure/ai/base_provider.py` to `shared/types/llm_types.py`.
*   **Rationale**: Decouples prompt builders in `domain` from `infrastructure/ai`.

---

### Component 4: Splitting TokenizationService & ErrorContext

#### [NEW] [parallel_counter.py](file:///home/hao/Desktop/labs/Synapse-Desktop/application/services/tokenization/parallel_counter.py)
*   **Action**: Extract parallel batch token counting functions (`_count_tokens_parallel_standard`, `_count_tokens_batch_hf`, `_count_tokens_batch_sequential`, `_count_tokens_for_file_no_cache`, `_read_file_mmap`) from `tokenization_service.py` to this new helper module.
*   **Rationale**: Reduces the main `TokenizationService` file to under 250 lines.

#### [NEW] [formatters.py](file:///home/hao/Desktop/labs/Synapse-Desktop/application/services/error_context/formatters.py)
*   **Action**: Move formatting functions (`_build_focused_error_context`, `_build_success_section`, `_build_failed_section`, `_build_change_block_details`, `_build_fix_instructions`, `_read_current_file_content`, `_find_preview_row`) from `error_context.py` to this helper module.
*   **Rationale**: Reduces the main `error_context.py` coordinator file to under 150 lines.

---

### Component 5: Fixing Presentation Imports and Composition Root Exclusion

To strictly enforce that the `presentation` layer cannot import from `infrastructure`:
1.  **Modify** `presentation/views/context/copy_action_controller.py` to:
    *   Import `is_binary_file` from `shared/utils/file_utils.py` instead of `infrastructure`.
    *   Import `load_app_settings` from `application/services/workspace_config` instead of `infrastructure.persistence.settings_manager`.
    *   Introduce `WorkspaceScanService` in `application/services/workspace_index.py` to wrap `scan_directory` so that controllers do not import it from `infrastructure` directly.
2.  **Modify** `tools/architecture/check_architecture.py` to exclude `presentation/service_container.py` (Composition Root) from import checking, as composition roots must structurally wire up concrete infrastructure/domain modules.

---

## 3. Step-by-Step Refactoring Strategy

To guarantee zero regressions, we will perform the changes incrementally and run verification at each step:

1.  **Step 1**: Move `TreeItem` to `domain/smart_context/tree_item.py`, `LLMMessage` to `shared/types/llm_types.py`, and `ITokenizationService` to `domain/ports/tokenization_port.py`. Update all imports. Run pytest.
2.  **Step 2**: Create `DomainRegistry`. Register services in `service_container.py`. Replace concrete imports in `domain/prompt/` and `domain/workflow/` with registry lookups. Run pytest.
3.  **Step 3**: Split and relocate `DependencyResolver` to `domain/codemap/dependency_resolver/`. Update all callers. Run pytest.
4.  **Step 4**: Split `tokenization_service.py` and `error_context.py` into their respective submodules. Run pytest.
5.  **Step 5**: Exclude `presentation/service_container.py` in `check_architecture.py`. Fix presentation direct imports of infrastructure utilities. Run check_architecture. Run pytest.
6.  **Step 6**: Clean up and update `tools/architecture/baseline.json`. Ensure `check_architecture.py --strict` returns 0.

---

## 4. Verification Plan

### Automated Tests
*   Run unit tests:
    ```bash
    env -u PYTHONPATH=.venv/bin/pytest tests/ -v
    ```
*   Run type check:
    ```bash
    env -u PYTHONPATH=.venv/bin/pyrefly check
    ```
*   Run architectural check:
    ```bash
    .venv/bin/python tools/architecture/check_architecture.py --strict
    ```
*   Format check:
    ```bash
    env -u PYTHONPATH=.venv/bin/ruff check --fix .
    env -u PYTHONPATH=.venv/bin/ruff format .
    ```

### Manual Verification
*   Launch application via `./start.sh`.
*   Perform folder scan and check file tree display.
*   Run token count comparison for various file types.
*   Generate prompt with custom template and copy context to clipboard.
