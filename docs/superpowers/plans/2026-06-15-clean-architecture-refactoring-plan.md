# Clean Architecture Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the codebase to eliminate all 17 Import Violations and 2 Layer Cycles recorded in baseline.json by applying strict Dependency Inversion and Service Locator patterns.

**Architecture:** We will define Clean Architecture Ports (Interfaces) and DTOs in the Domain Layer. The Application and Presentation layers will interact with Infrastructure via these Ports using DomainRegistry as a Service Locator, decoupled from the concrete implementations.

**Tech Stack:** Python 3.12, PySide6, ast, pathspec, pytest, ruff, pyrefly

---

### Task 1: Create Ports (Interfaces) and Domain Models

We will create all necessary interfaces (ports) and data structures in the domain layer.

**Files:**
- Create: `domain/ports/action_result.py`
- Create: `domain/ports/ai_port.py`
- Create: `domain/ports/repo_manager_port.py`
- Create: `domain/ports/settings_service_port.py`
- Create: `domain/ports/ignore_engine_port.py`
- Create: `domain/ports/cache_registry_port.py`
- Create: `domain/ports/file_actions_port.py`
- Create: `domain/ports/recent_folders_port.py`
- Create: `domain/ports/session_state_port.py`
- Create: `domain/ports/security_scanner_port.py`

- [ ] **Step 1: Create domain/ports/action_result.py**
  Write the `ActionResult` dataclass:
  ```python
  from dataclasses import dataclass
  from typing import Optional

  @dataclass
  class ActionResult:
      """Result of a file action execution."""
      path: str
      action: str
      success: bool
      message: str
      new_path: Optional[str] = None
  ```

- [ ] **Step 2: Create domain/ports/ai_port.py**
  Write `LLMMessage`, `LLMResponse` and `IAIProvider` interface:
  ```python
  from dataclasses import dataclass
  from typing import List, Protocol

  @dataclass
  class LLMMessage:
      role: str
      content: str

  @dataclass
  class LLMResponse:
      content: str
      token_count: int

  class IAIProvider(Protocol):
      def generate(self, messages: List[LLMMessage]) -> LLMResponse:
          ...
  ```

- [ ] **Step 3: Create domain/ports/repo_manager_port.py**
  Write `RemoteRepoInfo`, `CloneProgress`, `CachedRepo` and `IRepoManager` interface:
  ```python
  from dataclasses import dataclass
  from typing import Optional, List, Callable, Protocol
  from pathlib import Path
  from datetime import datetime

  @dataclass
  class RemoteRepoInfo:
      owner: str
      repo: str
      ref: Optional[str] = None
      original_url: str = ""

  @dataclass
  class CloneProgress:
      status: str
      percentage: Optional[int] = None

  @dataclass
  class CachedRepo:
      name: str
      path: Path
      size_bytes: int = 0
      last_modified: Optional[datetime] = None
      repo_info: Optional[RemoteRepoInfo] = None

  ProgressCallback = Callable[[CloneProgress], None]

  class IRepoManager(Protocol):
      def clone_repo(
          self,
          url: str,
          on_progress: Optional[ProgressCallback] = None,
          timeout: Optional[int] = None,
          force_reclone: bool = False,
      ) -> Path:
          ...
      def get_cached_repos(self) -> List[CachedRepo]:
          ...
      def delete_repo(self, repo_name: str) -> bool:
          ...
      def clear_cache(self) -> int:
          ...
      def get_cache_size(self) -> int:
          ...
      def format_size(self, size_bytes: int) -> str:
          ...
      def is_dirty(self, repo_path: Path) -> bool:
          ...
      def stash_changes(self, repo_path: Path) -> bool:
          ...
      def discard_changes(self, repo_path: Path) -> bool:
          ...
  ```

- [ ] **Step 4: Create domain/ports/settings_service_port.py**
  Write `ISettingsService` interface:
  ```python
  from typing import Protocol, Any
  from domain.config.app_settings import AppSettings

  class ISettingsService(Protocol):
      def load_settings(self) -> AppSettings:
          ...
      def update_setting(self, key: str, value: Any) -> None:
          ...
      def add_instruction_history(self, instruction: str) -> None:
          ...
  ```

- [ ] **Step 5: Create domain/ports/ignore_engine_port.py**
  Write `IIgnoreEngine` interface:
  ```python
  from typing import Protocol, Optional, List
  from pathlib import Path
  import pathspec

  class IIgnoreEngine(Protocol):
      def build_pathspec(
          self,
          root_path: Path,
          use_default_ignores: bool = True,
          excluded_patterns: Optional[List[str]] = None,
          use_gitignore: bool = True,
      ) -> pathspec.PathSpec:
          ...
      def read_gitignore(self, path: Path) -> List[str]:
          ...
      def find_git_root(self, path: Path) -> Optional[Path]:
          ...
      def clear_cache(self) -> None:
          ...
  ```

- [ ] **Step 6: Create domain/ports/cache_registry_port.py**
  Write `ICacheRegistry` interface:
  ```python
  from typing import Protocol, List, Dict, Any

  class ICacheRegistry(Protocol):
      def get_stats(self) -> Dict[str, int]:
          ...
      def get_registered_names(self) -> List[str]:
          ...
      def invalidate_for_workspace(self) -> None:
          ...
  ```

- [ ] **Step 7: Create domain/ports/file_actions_port.py**
  Write `IFileActionsService` interface:
  ```python
  from typing import Protocol, Optional, List
  from pathlib import Path
  from domain.prompt.opx_parser import FileAction
  from domain.ports.action_result import ActionResult

  class IFileActionsService(Protocol):
      def apply_file_actions(
          self,
          file_actions: List[FileAction],
          workspace_roots: Optional[List[Path]] = None,
          dry_run: bool = False,
      ) -> List[ActionResult]:
          ...
  ```

- [ ] **Step 8: Create domain/ports/recent_folders_port.py**
  Write `IRecentFoldersService` interface:
  ```python
  from typing import Protocol, List

  class IRecentFoldersService(Protocol):
      def load_recent_folders(self) -> List[str]:
          ...
      def save_recent_folders(self, folders: List[str]) -> None:
          ...
      def clear_recent_folders(self) -> None:
          ...
  ```

- [ ] **Step 9: Create domain/ports/session_state_port.py**
  Write `ISessionStateService` interface:
  ```python
  from typing import Protocol, Dict, Any

  class ISessionStateService(Protocol):
      def load_session_state(self) -> Dict[str, Any]:
          ...
      def save_session_state(self, state: Dict[str, Any]) -> None:
          ...
      def clear_session_state(self) -> None:
          ...
  ```

- [ ] **Step 10: Create domain/ports/security_scanner_port.py**
  Write `SecretMatch` and `ISecurityScanner` interface:
  ```python
  from dataclasses import dataclass
  from typing import Optional, List, Set, Protocol

  @dataclass
  class SecretMatch:
      secret_type: str
      line_number: int
      redacted_preview: str
      file_path: Optional[str] = None

  class ISecurityScanner(Protocol):
      def scan_secrets_in_files_cached(
          self, file_paths: Set[str], max_file_size: int = 1024 * 1024
      ) -> List[SecretMatch]:
          ...
      def format_security_warning(self, matches: List[SecretMatch]) -> str:
          ...
  ```

- [ ] **Step 11: Commit**
  Run: `git add domain/ports/`
  Run: `git commit -m "feat: add Clean Architecture ports and domain models"`

---

### Task 2: Update DomainRegistry

We will add registry and retrieval methods for all new ports in DomainRegistry.

**Files:**
- Modify: `domain/ports/registry.py`

- [ ] **Step 1: Modify domain/ports/registry.py**
  Add class variables and methods for all new interfaces:
  ```python
  # Add imports at top
  from domain.ports.action_result import ActionResult
  from domain.ports.ai_port import IAIProvider
  from domain.ports.repo_manager_port import IRepoManager
  from domain.ports.settings_service_port import ISettingsService
  from domain.ports.ignore_engine_port import IIgnoreEngine
  from domain.ports.cache_registry_port import ICacheRegistry
  from domain.ports.file_actions_port import IFileActionsService
  from domain.ports.recent_folders_port import IRecentFoldersService
  from domain.ports.session_state_port import ISessionStateService
  from domain.ports.security_scanner_port import ISecurityScanner
  from application.interfaces.file_watcher_port import IFileWatcherService
  from application.services.service_interfaces import IClipboardService

  # Inside DomainRegistry class, add:
  _security_scanner: Optional[ISecurityScanner] = None
  _repo_manager: Optional[IRepoManager] = None
  _settings_service: Optional[ISettingsService] = None
  _recent_folders: Optional[IRecentFoldersService] = None
  _session_state: Optional[ISessionStateService] = None
  _cache_registry: Optional[ICacheRegistry] = None
  _file_actions_service: Optional[IFileActionsService] = None
  _file_watcher_service: Optional[IFileWatcherService] = None
  _clipboard_service: Optional[IClipboardService] = None
  _ignore_engine: Optional[IIgnoreEngine] = None

  @classmethod
  def register_security_scanner(cls, scanner: ISecurityScanner) -> None:
      cls._security_scanner = scanner

  @classmethod
  def security_scanner(cls) -> ISecurityScanner:
      if cls._security_scanner is None:
          raise RuntimeError("ISecurityScanner is not registered")
      return cls._security_scanner

  @classmethod
  def register_repo_manager(cls, manager: IRepoManager) -> None:
      cls._repo_manager = manager

  @classmethod
  def repo_manager(cls) -> IRepoManager:
      if cls._repo_manager is None:
          raise RuntimeError("IRepoManager is not registered")
      return cls._repo_manager

  @classmethod
  def register_settings_service(cls, service: ISettingsService) -> None:
      cls._settings_service = service

  @classmethod
  def settings_service(cls) -> ISettingsService:
      if cls._settings_service is None:
          raise RuntimeError("ISettingsService is not registered")
      return cls._settings_service

  @classmethod
  def register_recent_folders(cls, service: IRecentFoldersService) -> None:
      cls._recent_folders = service

  @classmethod
  def recent_folders(cls) -> IRecentFoldersService:
      if cls._recent_folders is None:
          raise RuntimeError("IRecentFoldersService is not registered")
      return cls._recent_folders

  @classmethod
  def register_session_state(cls, service: ISessionStateService) -> None:
      cls._session_state = service

  @classmethod
  def session_state(cls) -> ISessionStateService:
      if cls._session_state is None:
          raise RuntimeError("ISessionStateService is not registered")
      return cls._session_state

  @classmethod
  def register_cache_registry(cls, registry: ICacheRegistry) -> None:
      cls._cache_registry = registry

  @classmethod
  def cache_registry(cls) -> ICacheRegistry:
      if cls._cache_registry is None:
          raise RuntimeError("ICacheRegistry is not registered")
      return cls._cache_registry

  @classmethod
  def register_file_actions_service(cls, service: IFileActionsService) -> None:
      cls._file_actions_service = service

  @classmethod
  def file_actions_service(cls) -> IFileActionsService:
      if cls._file_actions_service is None:
          raise RuntimeError("IFileActionsService is not registered")
      return cls._file_actions_service

  @classmethod
  def register_file_watcher_service(cls, service: IFileWatcherService) -> None:
      cls._file_watcher_service = service

  @classmethod
  def file_watcher_service(cls) -> IFileWatcherService:
      if cls._file_watcher_service is None:
          raise RuntimeError("IFileWatcherService is not registered")
      return cls._file_watcher_service

  @classmethod
  def register_clipboard_service(cls, service: IClipboardService) -> None:
      cls._clipboard_service = service

  @classmethod
  def clipboard_service(cls) -> IClipboardService:
      if cls._clipboard_service is None:
          raise RuntimeError("IClipboardService is not registered")
      return cls._clipboard_service

  @classmethod
  def register_ignore_engine(cls, engine: IIgnoreEngine) -> None:
      cls._ignore_engine = engine

  @classmethod
  def ignore_engine(cls) -> IIgnoreEngine:
      if cls._ignore_engine is None:
          raise RuntimeError("IIgnoreEngine is not registered")
      return cls._ignore_engine
  ```

- [ ] **Step 2: Commit**
  Run: `git commit -am "feat: extend DomainRegistry with Clean Architecture ports"`

---

### Task 3: Implement Ports in Infrastructure Adapters

We will update all the concrete adapters in `infrastructure/` to inherit from and implement their corresponding interface port classes.

**Files:**
- Modify: `infrastructure/git/repo_manager.py`
- Modify: `infrastructure/git/git_remote_parse.py`
- Modify: `infrastructure/persistence/settings_manager.py`
- Modify: `infrastructure/persistence/recent_folders.py`
- Modify: `infrastructure/persistence/session_state.py`
- Modify: `infrastructure/filesystem/file_actions.py`
- Modify: `infrastructure/adapters/security_check.py`
- Modify: `infrastructure/filesystem/ignore_engine.py`
- Modify: `infrastructure/adapters/cache_registry.py`
- Modify: `infrastructure/filesystem/file_watcher/service.py`

- [ ] **Step 1: Modify infrastructure/git/repo_manager.py**
  Inherit `RepoManager` from `IRepoManager` (import from `domain.ports.repo_manager_port`). Sửa import `RemoteRepoInfo`, `CloneProgress`, `CachedRepo` từ `domain.ports.repo_manager_port`.
  Ensure method signatures match.

- [ ] **Step 2: Modify infrastructure/persistence/settings_manager.py**
  Inherit class `SettingsManager` (or add class if it's functional/add interface wrappers) to implement `ISettingsService`. Since it's helper functions, we can define `class SettingsService(ISettingsService)` and wrap these helpers.

- [ ] **Step 3: Modify infrastructure/persistence/recent_folders.py**
  Wrap functions into `class RecentFoldersService(IRecentFoldersService)` and implement methods.

- [ ] **Step 4: Modify infrastructure/persistence/session_state.py**
  Wrap functions into `class SessionStateService(ISessionStateService)` and implement methods.

- [ ] **Step 5: Modify infrastructure/filesystem/file_actions.py**
  Inherit or wrap functions into `class FileActionsService(IFileActionsService)` and implement methods. Sửa import `ActionResult` từ `domain.ports.action_result`.

- [ ] **Step 6: Modify infrastructure/adapters/security_check.py**
  Wrap functions into `class SecurityScannerAdapter(ISecurityScanner)` and implement. Sửa import `SecretMatch` từ `domain.ports.security_scanner_port`.

- [ ] **Step 7: Modify infrastructure/filesystem/ignore_engine.py**
  Inherit `IgnoreEngine` from `IIgnoreEngine`.

- [ ] **Step 8: Modify infrastructure/adapters/cache_registry.py**
  Inherit `CacheRegistry` from `ICacheRegistry`.

- [ ] **Step 9: Modify infrastructure/filesystem/file_watcher/service.py**
  Inherit `FileWatcher` from `IFileWatcherService`.

- [ ] **Step 10: Commit**
  Run: `git commit -am "feat: implement ports in infrastructure adapters"`

---

### Task 4: Move UI Utilities to Presentation and Setup Composition Root

We will separate UI utilities from infrastructure and set up the ServiceContainer to register adapters at startup.

**Files:**
- Create: `presentation/utils/clipboard.py`
- Modify: `presentation/service_container.py`

- [ ] **Step 1: Create presentation/utils/clipboard.py**
  Write UI utility `copy_to_clipboard` here using PySide6's QGuiApplication:
  ```python
  import logging
  from PySide6.QtGui import QGuiApplication

  logger = logging.getLogger(__name__)

  def copy_to_clipboard(text: str) -> tuple[bool, str]:
      try:
          clipboard = QGuiApplication.clipboard()
          if clipboard is not None:
              clipboard.setText(text)
              return True, ""
          return False, "Clipboard not available"
      except Exception as e:
          logger.exception("Failed to copy to clipboard")
          return False, str(e)
  ```

- [ ] **Step 2: Modify presentation/service_container.py**
  Register all adapters into `DomainRegistry` during `__init__`:
  ```python
  # Add registry imports
  from domain.ports.registry import DomainRegistry
  from infrastructure.git.repo_manager import RepoManager
  from infrastructure.persistence.settings_manager import SettingsService
  from infrastructure.persistence.recent_folders import RecentFoldersService
  from infrastructure.persistence.session_state import SessionStateService
  from infrastructure.filesystem.file_actions import FileActionsService
  from infrastructure.adapters.security_check import SecurityScannerAdapter
  from infrastructure.filesystem.file_watcher.service import FileWatcher

  # Inside __init__:
  DomainRegistry.register_security_scanner(SecurityScannerAdapter())
  DomainRegistry.register_repo_manager(RepoManager())
  DomainRegistry.register_settings_service(SettingsService())
  DomainRegistry.register_recent_folders(RecentFoldersService())
  DomainRegistry.register_session_state(SessionStateService())
  DomainRegistry.register_cache_registry(self.cache_registry)
  DomainRegistry.register_file_actions_service(FileActionsService())
  DomainRegistry.register_file_watcher_service(FileWatcher())
  DomainRegistry.register_clipboard_service(self.clipboard)
  DomainRegistry.register_ignore_engine(self.ignore_engine)
  ```

- [ ] **Step 3: Commit**
  Run: `git add presentation/utils/clipboard.py`
  Run: `git commit -am "feat: setup UI clipboard utility and register adapters in ServiceContainer"`

---

### Task 5: Refactor Imports in Application Layer (Break Layer Cycles)

We will update all files in `application/` to use ports and DomainRegistry instead of importing directly from `infrastructure/`.

**Files:**
- Modify: `application/services/apply_service.py`
- Modify: `application/services/ai_context_worker.py`
- Modify: `application/services/prompt_build_service.py`
- Modify: `application/services/workspace_config.py`
- Modify: `application/services/workspace_index.py`
- Modify: `application/services/tokenization_service.py`
- Modify: `application/services/preview_analyzer.py`
- Modify: `application/services/tokenization/parallel_counter.py`
- Modify: `application/use_cases/workflow_use_cases.py`

- [ ] **Step 1: Modify application/services/apply_service.py**
  Change import of `ActionResult` and `apply_file_actions`:
  ```python
  from domain.ports.action_result import ActionResult
  from domain.ports.registry import DomainRegistry

  # Replace direct apply_file_actions call:
  results = DomainRegistry.file_actions_service().apply_file_actions(...)
  ```

- [ ] **Step 2: Modify application/services/ai_context_worker.py**
  Use `DomainRegistry.ast_parser()` for repo maps and replace OpenAICompatibleProvider imports with dynamic provider retrieval via registry. Use `LLMMessage`, `LLMResponse` from `domain.ports.ai_port`.

- [ ] **Step 3: Modify application/services/prompt_build_service.py**
  Replace `get_git_diffs` / `get_git_logs` with `DomainRegistry.git_service().get_diffs(...)` and `get_logs(...)`.
  Replace `encoder_registry` with `DomainRegistry.tokenization_service()`.
  Use `TreeItem` from `domain.smart_context.tree_item`.

- [ ] **Step 4: Modify application/services/workspace_config.py**
  Use `DomainRegistry.settings_service().load_settings()` instead of `load_app_settings`.

- [ ] **Step 5: Modify application/services/workspace_index.py**
  Inject `IIgnoreEngine` (or use `DomainRegistry.ignore_engine()`) instead of importing concrete `IgnoreEngine`.

- [ ] **Step 6: Modify other application/ services files**
  Refactor all other imports of `infrastructure.filesystem.file_utils.is_binary_file` to use `shared.utils.file_utils.is_binary_file`.

- [ ] **Step 7: Commit**
  Run: `git commit -am "refactor: eliminate infrastructure imports from application layer"`

---

### Task 6: Refactor Imports in Presentation Layer (Fix Import Violations)

We will refactor all import violations in the `presentation` layer.

**Files:**
- Modify all 17 presentation files list in baseline.json

- [ ] **Step 1: Refactor presentation/components/dialogs/dialogs_qt.py**
  Replace `from infrastructure.adapters.clipboard_utils import copy_to_clipboard` with `from presentation.utils.clipboard import copy_to_clipboard`.
  Replace `SecretMatch` import with `from domain.ports.security_scanner_port import SecretMatch`.
  Replace `RepoManager` import with `DomainRegistry.repo_manager()`.

- [ ] **Step 2: Refactor presentation/views/history/... and presentation/views/apply/...**
  Replace `copy_to_clipboard` from infrastructure with local presentation copy utility.
  Replace `history_service` direct calls with settings/history services accessed via `DomainRegistry` or a newly registered `HistoryService` adapter.

- [ ] **Step 3: Refactor presentation/views/settings/settings_view_qt.py**
  Use `DomainRegistry.settings_service()` and `DomainRegistry.session_state()`.

- [ ] **Step 4: Refactor presentation/main_window.py**
  Replace all persistence helpers (session, recent folders) with their registry interfaces.

- [ ] **Step 5: Run static architecture governance check**
  Run: `python tools/architecture/check_architecture.py --strict`
  Expected: Strict check passed (No violations).
  Run: `python tools/architecture/check_architecture.py --write-baseline` to update baseline to empty.

- [ ] **Step 6: Run Pytest suite**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v`
  Expected: All 590+ tests pass.

- [ ] **Step 7: Commit**
  Run: `git commit -am "refactor: eliminate infrastructure imports from presentation layer and clean baseline"`
