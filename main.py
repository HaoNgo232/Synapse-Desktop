import logging
import os
import sys
import multiprocessing
from pathlib import Path

# Suppress Hugging Face warnings before imports
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402

from presentation.config.theme import apply_theme  # noqa: E402
from presentation.utils.qt_utils import get_signal_bridge  # noqa: E402
from presentation.main_window import SynapseMainWindow  # noqa: E402
from presentation.service_container import ServiceContainer  # noqa: E402


def main() -> None:
    """Entry point for Synapse Desktop."""
    # CRITICAL for Windows EXE: Prevent fork bomb when using multiprocessing.
    multiprocessing.freeze_support()

    # ===== MCP Server Mode =====
    if "--run-mcp" in sys.argv:
        idx = sys.argv.index("--run-mcp")
        workspace = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        from infrastructure.mcp.server import run_mcp_server

        run_mcp_server(workspace)
        return

    # CRITICAL for Windows taskbar icon: Set AppUserModelID TRƯỚC KHI tạo QApplication
    from infrastructure.adapters.windows_utils import (
        set_app_user_model_id,
        get_default_app_user_model_id,
    )

    set_app_user_model_id(get_default_app_user_model_id())

    from shared.config.paths import ensure_app_directories
    from infrastructure.adapters.encoder_registry import initialize_encoder

    ensure_app_directories()

    # Khởi tạo encoder config
    initialize_encoder()

    # Register all cache adapters into CacheRegistry
    from infrastructure.adapters.cache_adapters import register_all_caches

    _boot_container = ServiceContainer()
    register_all_caches(
        ignore_engine=_boot_container.ignore_engine,
        tokenization_service=_boot_container.tokenization,
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Synapse Desktop")
    app.setOrganizationName("Synapse Desktop")

    # Store boot container on app instance for reuse
    app._service_container = _boot_container  # type: ignore[attr-defined]

    # Set application icon
    base_path = Path(__file__).parent
    if hasattr(sys, "_MEIPASS"):
        assets_dir = Path(sys._MEIPASS) / "assets"
    else:
        assets_dir = base_path / "assets"

    icon_path = None
    if (assets_dir / "icon.ico").exists():
        icon_path = assets_dir / "icon.ico"
    elif (assets_dir / "icon.png").exists():
        icon_path = assets_dir / "icon.png"

    if icon_path:
        app.setWindowIcon(QIcon(str(icon_path)))

    # Apply global dark stylesheet
    apply_theme(app)

    # Initialize global signal bridge on main thread
    get_signal_bridge()

    window = SynapseMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
