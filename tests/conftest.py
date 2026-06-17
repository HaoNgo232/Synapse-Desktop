import pathspec
import pytest
from pathlib import Path
from typing import Any, Optional, List, Dict, Callable
from domain.ports.registry import DomainRegistry
from domain.ports.cache_registry_port import ICacheRegistry
from domain.ports.directory_scanner import IDirectoryScanner
from domain.workflow.interfaces.git_port import IGitService
from domain.workflow.interfaces.ast_parser_port import IAstParser
from domain.smart_context.tree_item import TreeItem
from domain.ports.settings_service_port import ISettingsService
from domain.ports.file_watcher_port import IFileWatcherService
from domain.ports.ignore_engine_port import IIgnoreEngine
from domain.ports.tokenization_port import ITokenizationService
from domain.config.app_settings import AppSettings
from domain.ports.clipboard_port import IClipboardService
from domain.ports.history_port import IHistoryService, HistoryEntry
from domain.ports.file_actions_port import IFileActionsService
from domain.ports.action_result import ActionResult
from domain.prompt.opx_parser import FileAction
from domain.ports.mcp_installer_port import IMCPInstaller
from domain.ports.repo_manager_port import IRepoManager, CachedRepo, RemoteRepoInfo
from domain.ports.preset_store_port import IPresetStore, IPresetStoreFactory, PresetEntry
from domain.ports.memory_port import IMemoryMonitor, MemoryStats
from domain.ports.recent_folders_port import IRecentFoldersService





class DummyDirectoryScanner(IDirectoryScanner):
    def scan_directory(self, root_path: Path) -> TreeItem:
        return TreeItem(label="root", path=str(root_path), is_dir=True)

    def scan_directory_shallow(
        self,
        root_path: Path,
        ignore_engine: Any,
        depth: int = 1,
        excluded_patterns: Optional[List[str]] = None,
    ) -> TreeItem:
        return TreeItem(label="root", path=str(root_path), is_dir=True)

    def load_folder_children(
        self,
        node: TreeItem,
        ignore_engine: Any,
        excluded_patterns: Optional[List[str]] = None,
        use_gitignore: bool = True,
        workspace_root: Optional[Path] = None,
    ) -> None:
        pass


class DummyGitService(IGitService):
    def get_diffs(self, root_path, base_ref=None):
        return None

    def get_logs(self, root_path, max_commits=10):
        return None

    def get_diff_only(
        self,
        root_path,
        num_commits=0,
        include_staged=True,
        include_unstaged=True,
    ):
        from shared.types.git_types import DiffOnlyResult

        return DiffOnlyResult(
            diff_content="",
            files_changed=0,
            insertions=0,
            deletions=0,
            commits_included=0,
        )

    def filter_diff_by_files(self, diff_content, files):
        return ""

    def extract_changed_files_from_diff(self, diff_content):
        return []

    def build_diff_prompt(
        self,
        diff_result,
        instructions,
        include_changed_content,
        include_tree_structure,
        workspace_root=None,
        use_relative_paths=False,
        include_related_files=False,
        related_depth=1,
        related_max_files=20,
        output_format="xml",
    ) -> str:
        return ""


class DummyFileWatcher(IFileWatcherService):
    def start(self, path, on_change=None, callbacks=None, debounce_seconds=0.5):
        pass

    def stop(self):
        pass

    def is_running(self):
        return False

    @property
    def current_path(self):
        return None


class DummyIgnoreEngine(IIgnoreEngine):
    def should_ignore(self, path: str) -> bool:
        return False

    def build_ignore_patterns(
        self,
        root_path,
        use_default_ignores=True,
        excluded_patterns=None,
        use_gitignore=True,
    ):
        return []

    def read_gitignore(self, folder_path):
        return []

    def find_git_root(self, path):
        return None

    def build_pathspec(
        self,
        folder_path,
        use_default_ignores: bool = True,
        excluded_patterns=None,
        use_gitignore: bool = True,
    ) -> pathspec.PathSpec:
        return pathspec.PathSpec([])

    def clear_cache(self):
        pass


class DummyTokenizationService(ITokenizationService):
    def count_tokens(self, text: str) -> int:
        return 0

    def estimate_tokens(self, text: str) -> int:
        return 0

    def count_tokens_for_file(self, file_path: Path) -> int:
        return 0

    def is_binary_file(self, file_path: Path) -> bool:
        return False

    def get_model_name(self) -> str:
        return "gpt-4"

    def set_model_config(self, model_name: Optional[str] = None) -> None:
        pass

    def reset_encoder(self) -> None:
        pass

    def count_tokens_batch_parallel(
        self,
        file_paths: List[Path],
        max_workers: int = 2,
        update_cache: bool = True,
    ) -> Dict[str, int]:
        return {}

    def clear_cache(self) -> None:
        pass

    def clear_file_from_cache(self, path: str) -> None:
        pass


class DummyAstParser(IAstParser):
    def parse_file(self, file_path):
        return {"symbols": []}

    def generate_repo_map(self, file_paths, workspace_root=None, max_files=500):
        return ""


class DummyClipboardService(IClipboardService):
    def copy_to_clipboard(self, text: str) -> tuple[bool, str]:
        return True, ""


class DummyHistoryService(IHistoryService):
    def add_history_entry(
        self,
        workspace_path: str,
        opx_content: str,
        action_results: List[dict],
    ) -> Optional[HistoryEntry]:
        return None

    def get_history_entries(self, limit: int = 50) -> List[HistoryEntry]:
        return []

    def get_entry_by_id(self, entry_id: str) -> Optional[HistoryEntry]:
        return None

    def delete_entry(self, entry_id: str) -> bool:
        return True

    def clear_history(self) -> bool:
        return True

    def get_history_stats(self) -> dict:
        return {}


class DummyFileActionsService(IFileActionsService):
    def apply_file_actions(
        self,
        file_actions: List[FileAction],
        workspace_roots: Optional[List[Path]] = None,
        dry_run: bool = False,
    ) -> List[ActionResult]:
        return []

    def apply_search_replace_to_content(
        self,
        content: str,
        search: str,
        replace: str,
        occurrence: Any,
    ) -> tuple[bool, str, str]:
        return True, "", ""

    def normalize_eol(self, text: str, eol: str) -> str:
        return text


class DummySettingsService(ISettingsService):
    def load_settings(self) -> AppSettings:
        return AppSettings()

    def update_setting(self, key: str, value: Any) -> None:
        pass

    def add_instruction_history(self, instruction: str) -> None:
        pass


class DummyCacheRegistry(ICacheRegistry):
    def get_stats(self) -> Dict[str, int]:
        return {}

    def get_registered_names(self) -> List[str]:
        return []

    def invalidate_for_workspace(self) -> None:
        pass

    def invalidate_for_path(self, path: str) -> None:
        pass


class DummyMCPInstaller(IMCPInstaller):
    def get_mcp_targets(self) -> dict:
        return {}

    def check_installed(
        self, target_name: str, workspace_path: Optional[str] = None
    ) -> bool:
        return False

    def get_mcp_command(self) -> list[str]:
        return []

    def get_config_path(
        self, target_name: str, workspace_path: Optional[str] = None
    ) -> str:
        return ""

    def preview_json(
        self, target_name: str, workspace_path: Optional[str] = None
    ) -> str:
        return ""

    def install_config(
        self, target_name: str, workspace_path: Optional[str] = None
    ) -> tuple[bool, str]:
        return True, ""


class DummyRepoManager(IRepoManager):
    def clone_repo(
        self,
        url: str,
        on_progress: Optional[Any] = None,
        timeout: Optional[int] = None,
        force_reclone: bool = False,
    ) -> Path:
        return Path()

    def get_cached_repos(self) -> List[CachedRepo]:
        return []

    def delete_repo(self, repo_name: str) -> bool:
        return True

    def clear_cache(self) -> int:
        return 0

    def get_cache_size(self) -> int:
        return 0

    def format_size(self, size_bytes: int) -> str:
        return "0 B"

    def is_dirty(self, repo_path: Path) -> bool:
        return False

    def stash_changes(self, repo_path: Path) -> bool:
        return True

    def discard_changes(self, repo_path: Path) -> bool:
        return True


class DummyPresetStore(IPresetStore):
    def list_presets(self) -> List[PresetEntry]:
        return []

    def get_preset(self, preset_id: str) -> Optional[PresetEntry]:
        return None

    def create_preset(
        self,
        name: str,
        selected_paths: List[str],
        instructions: str = "",
        output_format: str = "",
    ) -> PresetEntry:
        return PresetEntry("", "", [])

    def update_preset(
        self,
        preset_id: str,
        name: Optional[str] = None,
        selected_paths: Optional[List[str]] = None,
        instructions: Optional[str] = None,
        output_format: Optional[str] = None,
    ) -> Optional[PresetEntry]:
        return None

    def delete_preset(self, preset_id: str) -> bool:
        return True

    def rename_preset(self, preset_id: str, new_name: str) -> Optional[PresetEntry]:
        return None

    def to_absolute_paths(self, relative_paths: List[str]) -> List[str]:
        return []


class DummyPresetStoreFactory(IPresetStoreFactory):
    def create_preset_store(self, workspace_root: Path) -> IPresetStore:
        return DummyPresetStore()


class DummyMemoryMonitor(IMemoryMonitor):
    def __init__(self):
        self._on_update = None

    @property
    def on_update(self) -> Optional[Callable[[MemoryStats], None]]:
        return self._on_update

    @on_update.setter
    def on_update(self, callback: Optional[Callable[[MemoryStats], None]]) -> None:
        self._on_update = callback

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def set_token_cache_count(self, count: int) -> None:
        pass

    def set_file_count(self, count: int) -> None:
        pass

    def get_current_stats(self) -> MemoryStats:
        return MemoryStats(rss_mb=0.0)


class DummyRecentFolders(IRecentFoldersService):
    def load_recent_folders(self) -> List[str]:
        return []

    def save_recent_folders(self, folders: List[str]) -> None:
        pass

    def clear_recent_folders(self) -> None:
        pass

    def add_recent_folder(self, folder_path: str) -> bool:
        return True

    def get_folder_display_name(self, folder_path: str) -> str:
        return ""


@pytest.fixture(autouse=True, scope="session")
def setup_dummy_domain_ports():
    try:
        DomainRegistry.clipboard_service()
    except RuntimeError:
        DomainRegistry.register_clipboard_service(DummyClipboardService())

    try:
        DomainRegistry.history_service()
    except RuntimeError:
        DomainRegistry.register_history_service(DummyHistoryService())

    try:
        DomainRegistry.file_actions_service()
    except RuntimeError:
        DomainRegistry.register_file_actions_service(DummyFileActionsService())
    # Only register if not already registered to avoid overwriting production container setup
    try:
        DomainRegistry.directory_scanner()
    except RuntimeError:
        DomainRegistry.register_directory_scanner(DummyDirectoryScanner())

    try:
        DomainRegistry.git_service()
    except RuntimeError:
        DomainRegistry.register_git_service(DummyGitService())

    try:
        DomainRegistry.ast_parser()
    except RuntimeError:
        DomainRegistry.register_ast_parser(DummyAstParser())

    try:
        DomainRegistry.settings_service()
    except RuntimeError:
        DomainRegistry.register_settings_service(DummySettingsService())

    try:
        DomainRegistry.file_watcher_service()
    except RuntimeError:
        DomainRegistry.register_file_watcher_service(DummyFileWatcher())

    try:
        DomainRegistry.ignore_engine()
    except RuntimeError:
        DomainRegistry.register_ignore_engine(DummyIgnoreEngine())

    try:
        DomainRegistry.tokenization_service()
    except RuntimeError:
        DomainRegistry.register_tokenization_service(DummyTokenizationService())

    try:
        DomainRegistry.cache_registry()
    except RuntimeError:
        DomainRegistry.register_cache_registry(DummyCacheRegistry())

    try:
        DomainRegistry.workspace_scanner()
    except RuntimeError:
        from application.services.workspace_index import WorkspaceScanner
        DomainRegistry.register_workspace_scanner(WorkspaceScanner())

    try:
        DomainRegistry.mcp_installer()
    except RuntimeError:
        DomainRegistry.register_mcp_installer(DummyMCPInstaller())

    try:
        DomainRegistry.repo_manager()
    except RuntimeError:
        DomainRegistry.register_repo_manager(DummyRepoManager())

    try:
        DomainRegistry.preset_store_factory()
    except RuntimeError:
        DomainRegistry.register_preset_store_factory(DummyPresetStoreFactory())

    try:
        DomainRegistry.memory_monitor()
    except RuntimeError:
        DomainRegistry.register_memory_monitor(DummyMemoryMonitor())

    try:
        DomainRegistry.recent_folders()
    except RuntimeError:
        DomainRegistry.register_recent_folders(DummyRecentFolders())

    # Register default settings provider returning standard AppSettings
    try:
        DomainRegistry.settings()
    except RuntimeError:
        pass
    # Always register settings provider for tests to ensure a default exists
    DomainRegistry.register_settings_provider(lambda: AppSettings())



