import os
import sys
import importlib
from unittest.mock import patch, MagicMock
import pytest

# Pre-import GUI modules to ensure they bind real PySide6 classes 
# before any global mocks are applied during tests.
from presentation.views.settings.settings_view_qt import SettingsViewQt
from presentation.components.tag_chips_widget import TagChipsWidget

from domain.ports.registry import DomainRegistry
from domain.config.app_settings import AppSettings

class DummySettingsService:
    def __init__(self) -> None:
        self._settings = AppSettings(
            model_id="gpt-5.1",
            use_gitignore=True,
            ai_api_key="old-key",
            ai_base_url="https://api.openai.com/v1",
            ai_model_id="gpt-5.1",
            output_language="Vietnamese",
            excluded_folders="node_modules\ndist",
        )

    def load_settings(self) -> AppSettings:
        return self._settings

    def update_setting(self, key: str, value: str) -> None:
        setattr(self._settings, key, value)


class DummySessionState:
    def __init__(self) -> None:
        pass
    def clear_session_state(self) -> None:
        pass


class DummyMCPInstaller:
    def get_mcp_targets(self) -> dict:
        return {
            "Cursor": {"workspace_only": False},
            "Copilot": {"workspace_only": True},
        }

    def check_installed(self, target_name: str, workspace_path: str = None) -> bool:
        return target_name == "Cursor"

    def get_config_path(self, target_name: str, workspace_path: str = None) -> str:
        return f"/mock/path/{target_name}"

    def preview_json(self, target_name: str, workspace_path: str = None) -> str:
        return '{"name": "synapse"}'

    def install_config(
        self, target_name: str, workspace_path: str = None
    ) -> tuple[bool, str]:
        return True, "Success"

    def get_mcp_command(self) -> list[str]:
        return ["python", "main.py", "--run-mcp"]


class DummyAIProvider:
    def __init__(self) -> None:
        self.api_key = ""
        self.base_url = ""

    def configure(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url

    def fetch_available_models(self) -> list:
        return ["model-a", "model-b"]


@pytest.fixture
def setup_registry_dependencies():
    # Save original values
    orig_settings_service = None
    orig_settings_provider = None
    orig_session_state = None
    orig_mcp_installer = None
    orig_ai_factory = None
    orig_license_service = None

    try:
        orig_settings_service = DomainRegistry.settings_service()
    except RuntimeError:
        pass
    try:
        orig_settings_provider = DomainRegistry._settings_provider
    except AttributeError:
        pass
    try:
        orig_session_state = DomainRegistry.session_state()
    except RuntimeError:
        pass
    try:
        orig_mcp_installer = DomainRegistry.mcp_installer()
    except RuntimeError:
        pass
    try:
        orig_ai_factory = DomainRegistry.ai_provider_factory()
    except RuntimeError:
        pass
    try:
        orig_license_service = DomainRegistry.license_service()
    except AttributeError:
        pass

    # Setup dummies
    settings_service = DummySettingsService()
    DomainRegistry.register_settings_service(settings_service)
    DomainRegistry.register_settings_provider(lambda: settings_service.load_settings())

    session_state = DummySessionState()
    DomainRegistry.register_session_state(session_state)

    mcp_installer = DummyMCPInstaller()
    DomainRegistry.register_mcp_installer(mcp_installer)

    ai_provider = DummyAIProvider()
    DomainRegistry.register_ai_provider_factory(lambda: ai_provider)

    mock_license_service = MagicMock()
    mock_lic_info = MagicMock()
    mock_lic_info.is_valid = True
    mock_license_service.verify_license_key.return_value = mock_lic_info
    DomainRegistry.register_license_service(mock_license_service)

    yield settings_service, session_state, mcp_installer, ai_provider

    # Restore originals
    if orig_settings_service is not None:
        DomainRegistry.register_settings_service(orig_settings_service)
    DomainRegistry._settings_provider = orig_settings_provider
    if orig_session_state is not None:
        DomainRegistry.register_session_state(orig_session_state)
    if orig_mcp_installer is not None:
        DomainRegistry.register_mcp_installer(orig_mcp_installer)
    if orig_ai_factory is not None:
        DomainRegistry.register_ai_provider_factory(orig_ai_factory)
    if orig_license_service is not None:
        DomainRegistry.register_license_service(orig_license_service)


def test_runtime_hook_sets_env_var(monkeypatch):
    monkeypatch.delenv("SYNAPSE_LICENSE_CHECK", raising=False)
    
    # Import/execute the runtime hook
    import runtime_hook_license
    importlib.reload(runtime_hook_license)
    
    assert os.environ.get("SYNAPSE_LICENSE_CHECK") == "1"


def test_main_boot_bypasses_license_check_when_flag_off(monkeypatch):
    monkeypatch.setenv("SYNAPSE_LICENSE_CHECK", "0")
    
    import main
    with (
        patch("PySide6.QtWidgets.QApplication"),
        patch("PySide6.QtGui.QIcon"),
        patch("presentation.config.theme.apply_theme"),
        patch("presentation.utils.qt_utils.get_signal_bridge"),
        patch("presentation.main_window.SynapseMainWindow"),
        patch("presentation.service_container.ServiceContainer"),
        patch("infrastructure.adapters.encoder_registry.initialize_encoder"),
        patch("shared.config.paths.ensure_app_directories"),
        patch("infrastructure.adapters.windows_utils.set_app_user_model_id"),
        patch("domain.ports.registry.DomainRegistry.license_service") as mock_license_service
    ):
        importlib.reload(main)
        try:
            main.main()
        except SystemExit:
            pass
        mock_license_service.assert_not_called()


def test_main_boot_bypasses_license_check_with_no_license_arg(monkeypatch):
    monkeypatch.setenv("SYNAPSE_LICENSE_CHECK", "1")
    
    import main
    with (
        patch("sys.argv", ["main.py", "--no-license"]),
        patch("PySide6.QtWidgets.QApplication"),
        patch("PySide6.QtGui.QIcon"),
        patch("presentation.config.theme.apply_theme"),
        patch("presentation.utils.qt_utils.get_signal_bridge"),
        patch("presentation.main_window.SynapseMainWindow"),
        patch("presentation.service_container.ServiceContainer"),
        patch("infrastructure.adapters.encoder_registry.initialize_encoder"),
        patch("shared.config.paths.ensure_app_directories"),
        patch("infrastructure.adapters.windows_utils.set_app_user_model_id"),
        patch("domain.ports.registry.DomainRegistry.license_service") as mock_license_service
    ):
        importlib.reload(main)
        try:
            main.main()
        except SystemExit:
            pass
        mock_license_service.assert_not_called()


def test_main_boot_enforces_license_check_when_flag_on(monkeypatch):
    monkeypatch.setenv("SYNAPSE_LICENSE_CHECK", "1")
    
    import main
    with (
        patch("sys.argv", ["main.py"]),
        patch("PySide6.QtWidgets.QApplication"),
        patch("PySide6.QtGui.QIcon"),
        patch("presentation.config.theme.apply_theme"),
        patch("presentation.utils.qt_utils.get_signal_bridge"),
        patch("presentation.main_window.SynapseMainWindow"),
        patch("presentation.service_container.ServiceContainer"),
        patch("infrastructure.adapters.encoder_registry.initialize_encoder"),
        patch("shared.config.paths.ensure_app_directories"),
        patch("infrastructure.adapters.windows_utils.set_app_user_model_id"),
        patch("infrastructure.persistence.settings_manager.load_app_settings") as mock_load_settings,
        patch("domain.ports.registry.DomainRegistry.license_service") as mock_license_service
    ):
        # Setup mocks
        mock_settings = MagicMock()
        mock_settings.license_key = "dummy"
        mock_load_settings.return_value = mock_settings
        
        mock_lic_info = MagicMock()
        mock_lic_info.is_valid = True
        mock_license_service.return_value.verify_license_key.return_value = mock_lic_info
        
        importlib.reload(main)
        try:
            main.main()
        except SystemExit:
            pass # Ignore exits for mock setups if any
            
        mock_license_service.assert_called_once()
        mock_license_service.return_value.verify_license_key.assert_called_once_with("dummy")


def test_settings_view_hides_licensing_when_flag_off(qtbot, setup_registry_dependencies, monkeypatch):
    monkeypatch.setenv("SYNAPSE_LICENSE_CHECK", "0")
    
    view = SettingsViewQt()
    qtbot.addWidget(view)
    
    # Assert _deactivate_btn is not created (since build_license_section is not called)
    assert not hasattr(view, "_deactivate_btn")


def test_settings_view_hides_licensing_with_no_license_arg(qtbot, setup_registry_dependencies, monkeypatch):
    monkeypatch.setenv("SYNAPSE_LICENSE_CHECK", "1")
    with patch("sys.argv", ["main.py", "--no-license"]):
        view = SettingsViewQt()
        qtbot.addWidget(view)
        assert not hasattr(view, "_deactivate_btn")


def test_settings_view_shows_licensing_when_flag_on(qtbot, setup_registry_dependencies, monkeypatch):
    monkeypatch.setenv("SYNAPSE_LICENSE_CHECK", "1")
    with patch("sys.argv", ["main.py"]):
        view = SettingsViewQt()
        qtbot.addWidget(view)
        # Assert _deactivate_btn is created and available
        assert hasattr(view, "_deactivate_btn")
