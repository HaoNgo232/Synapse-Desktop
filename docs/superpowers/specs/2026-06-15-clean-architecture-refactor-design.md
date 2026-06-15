# Design Spec: Clean Architecture Refactoring (Cross-Layer Dependency Violations)

**Date**: 2026-06-15  
**Topic**: Clean Architecture Refactoring  
**Goal**: Resolve cross-layer dependency violations in Synapse Desktop by aligning configuration placement, applying Dependency Inversion (Ports & Adapters) for the Domain layer, and relocating the Composition Root (Service Container) to the outer layer.

---

## 1. Problem Description & Context

During an architectural audit of the Synapse Desktop codebase, we identified a large number of dependency rule violations where inner layers directly imported concrete modules from outer layers:
*   **Domain Layer** (innermost) directly imports `infrastructure` (e.g., `file_utils`, `git_utils`, `encoders`, `ast_parser`) and `presentation` configurations.
*   **Application Layer** directly imports `infrastructure` and `presentation`.
*   **Infrastructure Layer** directly imports `presentation` configurations.
*   **Shared Layer** directly imports `presentation` configurations.

### Root Causes
1.  **Misplaced Configurations**: Non-UI configuration files (such as `paths.py`, `app_settings.py`, `model_config.py`, `output_format.py`, and `prompt_profiles.py`) were placed inside the `presentation/config/` package. Because lower layers require these configurations, they were forced to import from the `presentation` layer.
2.  **Missing Abstractions (Ports & Adapters)**: Domain workflows (e.g., `design_planner.py`, `code_reviewer.py`, `context_builder.py`) directly import utility/adapter files from `infrastructure/` to execute Git operations, parse ASTs, or check file types.
3.  **Composition Root in Application Layer**: `service_container.py` is located under `application/services/`, but it acts as a Composition Root (creating and wiring up all concrete implementations from all layers). As a result, it had to import from `infrastructure` and `presentation`.

---

## 2. Proposed Changes

We will perform the refactoring in three logical phases to ensure that tests remain green and the application behaves correctly throughout.

### Component 1: Config Relocation

We will move all non-UI config files out of `presentation/config/` into appropriate layers based on their business nature.

#### [NEW] [paths.py](file:///home/hao/Desktop/labs/Synapse-Desktop/shared/config/paths.py)
*   **Action**: Move from `presentation/config/paths.py`.
*   **Rationale**: General paths like `APP_DIR`, `LOG_DIR`, `SETTINGS_FILE` are shared across all layers. Placing them in `shared/config/` is safe and does not violate Clean Architecture.

#### [NEW] [app_settings.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/config/app_settings.py)
*   **Action**: Move from `presentation/config/app_settings.py`.
*   **Rationale**: `AppSettings` contains business rules governing LLM configurations, prompt parameters, and folder exclusion lists, making it part of the core domain configurations.

#### [NEW] [model_config.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/config/model_config.py)
*   **Action**: Move from `presentation/config/model_config.py`.
*   **Rationale**: Defines the supported models and their attributes, which is domain-level configuration.

#### [NEW] [output_format.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/config/output_format.py)
*   **Action**: Move from `presentation/config/output_format.py`.
*   **Rationale**: Defines output structures (XML, Plain Text) used directly by prompt generation and assembling in the domain layer.

#### [NEW] [prompt_profiles.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/config/prompt_profiles.py)
*   **Action**: Move from `presentation/config/prompt_profiles.py`.

#### [DELETE] [presentation/config files](file:///home/hao/Desktop/labs/Synapse-Desktop/presentation/config/)
*   Delete the moved files under `presentation/config/` and clean up `presentation/config/__init__.py`.

---

### Component 2: Dependency Inversion for Domain Layer (Ports & Adapters)

#### [NEW] [file_utils.py](file:///home/hao/Desktop/labs/Synapse-Desktop/shared/utils/file_utils.py)
*   **Action**: Relocate non-I/O pure helper functions (like `is_binary_file`) from `infrastructure/filesystem/file_utils.py` to `shared/utils/file_utils.py`.
*   **Rationale**: Allows `domain/tokenization/counter.py` to check for binary files without importing the filesystem-bound `infrastructure` layer.

#### [NEW] [git_port.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/workflow/interfaces/git_port.py)
*   **Action**: Define the `IGitService` abstract class containing abstract methods for running Git diffs, getting commit logs, etc.
*   **Rationale**: Formulates a clear interface (Port) that the Domain layer expects.

#### [NEW] [ast_parser_port.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/workflow/interfaces/ast_parser_port.py)
*   **Action**: Define `IAstParser` abstract class.

#### [MODIFY] [domain/workflow files](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/workflow/)
*   Update `design_planner.py`, `code_reviewer.py`, `context_builder.py`, `test_builder.py`, and `refactor_workflow.py` to accept implementations of `IGitService` and `IAstParser` via their constructors rather than importing concrete helpers directly.

#### [MODIFY] [infrastructure/adapters](file:///home/hao/Desktop/labs/Synapse-Desktop/infrastructure/)
*   Make `infrastructure/git/git_utils.py` (or a dedicated wrapper class) implement `IGitService`.
*   Make `infrastructure/adapters/ast_parser.py` implement `IAstParser`.

---

### Component 3: Relocate Composition Root (Service Container)

#### [NEW] [service_container.py](file:///home/hao/Desktop/labs/Synapse-Desktop/presentation/service_container.py)
*   **Action**: Move `service_container.py` from `application/services/service_container.py` to `presentation/service_container.py`.
*   **Rationale**: As a Composition Root, it needs to import concrete adapters from `infrastructure` to resolve dependencies. Moving it to the outermost layer (`presentation`) makes these imports structurally sound.

---

## 3. Verification Plan

We will perform automated and manual verification to guarantee that no functionality is broken by the refactoring.

### Automated Tests
1.  **Run All Tests**:
    ```bash
    env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v
    ```
2.  **Strict Type Checking**:
    ```bash
    env -u PYTHONHOME -u PYTHONPATH .venv/bin/pyrefly check
    ```
3.  **Linter & Code Format**:
    ```bash
    env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff check --fix .
    env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff format .
    ```

### Manual Verification
*   Launch the application: `./start.sh` or `python main_window.py`.
*   Test key features (scanning folders, token counting, adding custom templates, copy-to-clipboard, applying AI code edits) to ensure correct runtime operation.
