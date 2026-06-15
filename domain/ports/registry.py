from typing import Callable, Optional
from domain.ports.tokenization_port import ITokenizationService
from domain.ports.workspace_scanner import IWorkspaceScanner
from domain.ports.directory_scanner import IDirectoryScanner
from domain.workflow.interfaces.git_port import IGitService
from domain.workflow.interfaces.ast_parser_port import IAstParser
from domain.config.app_settings import AppSettings
from domain.ports.ai_port import IAIProvider

from domain.ports.repo_manager_port import IRepoManager
from domain.ports.settings_service_port import ISettingsService
from domain.ports.ignore_engine_port import IIgnoreEngine
from domain.ports.cache_registry_port import ICacheRegistry
from domain.ports.file_actions_port import IFileActionsService
from domain.ports.recent_folders_port import IRecentFoldersService
from domain.ports.session_state_port import ISessionStateService
from domain.ports.security_scanner_port import ISecurityScanner
from domain.ports.file_watcher_port import IFileWatcherService
from domain.ports.clipboard_port import IClipboardService
from domain.ports.mcp_installer_port import IMCPInstaller
from domain.ports.preset_store_port import IPresetStoreFactory
from domain.ports.history_port import IHistoryService
from domain.ports.lifecycle_port import IAppLifecycleService
from domain.ports.memory_port import IMemoryMonitor


class DomainRegistry:
    """
    Registry tinh (Service Locator) o Domain layer.

    Cung cap diem truy cap den cac implementation thuc te (TokenizationService,
    WorkspaceScanner) ma khong lam domain bi phu thuoc nguoc vao cac layer ngoai.
    """

    _tokenization_service: Optional[ITokenizationService] = None
    _workspace_scanner: Optional[IWorkspaceScanner] = None
    _directory_scanner: Optional[IDirectoryScanner] = None
    _git_service: Optional[IGitService] = None
    _ast_parser: Optional[IAstParser] = None
    _settings_provider: Optional[Callable[[], AppSettings]] = None

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
    _ai_provider_factory: Optional[Callable[[], IAIProvider]] = None
    _mcp_installer: Optional[IMCPInstaller] = None
    _preset_store_factory: Optional[IPresetStoreFactory] = None
    _history_service: Optional[IHistoryService] = None
    _app_lifecycle: Optional[IAppLifecycleService] = None
    _memory_monitor: Optional[IMemoryMonitor] = None

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

    @classmethod
    def register_ai_provider_factory(cls, factory: Callable[[], IAIProvider]) -> None:
        cls._ai_provider_factory = factory

    @classmethod
    def ai_provider_factory(cls) -> Callable[[], IAIProvider]:
        if cls._ai_provider_factory is None:
            raise RuntimeError(
                "IAIProvider factory is not registered in DomainRegistry"
            )
        return cls._ai_provider_factory

    @classmethod
    def register_mcp_installer(cls, installer: IMCPInstaller) -> None:
        cls._mcp_installer = installer

    @classmethod
    def mcp_installer(cls) -> IMCPInstaller:
        if cls._mcp_installer is None:
            raise RuntimeError("IMCPInstaller is not registered")
        return cls._mcp_installer

    @classmethod
    def register_preset_store_factory(cls, factory: IPresetStoreFactory) -> None:
        cls._preset_store_factory = factory

    @classmethod
    def preset_store_factory(cls) -> IPresetStoreFactory:
        if cls._preset_store_factory is None:
            raise RuntimeError("IPresetStoreFactory is not registered")
        return cls._preset_store_factory

    @classmethod
    def register_history_service(cls, service: IHistoryService) -> None:
        cls._history_service = service

    @classmethod
    def history_service(cls) -> IHistoryService:
        if cls._history_service is None:
            raise RuntimeError("IHistoryService is not registered")
        return cls._history_service

    @classmethod
    def register_app_lifecycle(cls, service: IAppLifecycleService) -> None:
        cls._app_lifecycle = service

    @classmethod
    def app_lifecycle(cls) -> IAppLifecycleService:
        if cls._app_lifecycle is None:
            raise RuntimeError("IAppLifecycleService is not registered")
        return cls._app_lifecycle

    @classmethod
    def register_memory_monitor(cls, monitor: IMemoryMonitor) -> None:
        cls._memory_monitor = monitor

    @classmethod
    def memory_monitor(cls) -> IMemoryMonitor:
        if cls._memory_monitor is None:
            raise RuntimeError("IMemoryMonitor is not registered")
        return cls._memory_monitor
