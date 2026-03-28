"""
Workflow Plugin Loader - Discovery va registration cho plugin runtime.

Plugin discovery strategy:
- Workspace-local: <workspace>/.synapse/plugins/*.py
- User-global: ~/.config/synapse-desktop/plugins/*.py

Moi plugin module phai expose factory:
    def create_plugin() -> IWorkflowPlugin
"""

import importlib.util
import logging
import threading
from pathlib import Path
from types import ModuleType
from typing import List

from application.plugins.registry import workflow_plugin_registry
from application.plugins.contracts import IWorkflowPlugin

logger = logging.getLogger(__name__)

_LOADED_WORKSPACES: set[str] = set()
_LOADER_LOCK = threading.RLock()


def _get_plugin_dirs(workspace_root: Path) -> List[Path]:
    """Lay danh sach thu muc plugin theo uu tien local -> global."""
    return [
        workspace_root / ".synapse" / "plugins",
        Path.home() / ".config" / "synapse-desktop" / "plugins",
    ]


def _load_module_from_file(module_name: str, file_path: Path) -> ModuleType:
    """Load mot python module tu file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create spec for plugin module: {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def discover_and_register_workflow_plugins(workspace_root: Path) -> List[str]:
    """Discover va register workflow plugins cho workspace.

    Tra ve list plugin_id vua duoc load moi.
    """
    ws = workspace_root.resolve()

    with _LOADER_LOCK:
        ws_key = str(ws)
        if ws_key in _LOADED_WORKSPACES:
            return []

        loaded_ids: List[str] = []

        for plugin_dir in _get_plugin_dirs(ws):
            if not plugin_dir.exists() or not plugin_dir.is_dir():
                continue

            for plugin_file in sorted(plugin_dir.glob("*.py")):
                if plugin_file.name.startswith("_"):
                    continue

                module_name = (
                    f"synapse_plugin_{plugin_file.stem}_{abs(hash(str(plugin_file)))}"
                )
                try:
                    module = _load_module_from_file(module_name, plugin_file)
                except Exception as exc:
                    logger.warning(
                        "Failed to load plugin module %s: %s",
                        plugin_file,
                        exc,
                    )
                    continue

                factory = getattr(module, "create_plugin", None)
                if not callable(factory):
                    logger.warning(
                        "Plugin module %s missing create_plugin() factory",
                        plugin_file,
                    )
                    continue

                try:
                    plugin = factory()
                except Exception as exc:
                    logger.warning(
                        "create_plugin() failed for %s: %s",
                        plugin_file,
                        exc,
                    )
                    continue

                if not isinstance(plugin, IWorkflowPlugin):
                    logger.warning(
                        "Plugin from %s does not satisfy IWorkflowPlugin contract",
                        plugin_file,
                    )
                    continue

                try:
                    plugin.initialize()
                    workflow_plugin_registry.register(plugin, allow_override=True)
                    loaded_ids.append(plugin.metadata.plugin_id)
                except Exception as exc:
                    logger.warning(
                        "Failed to register plugin %s from %s: %s",
                        plugin.metadata.plugin_id,
                        plugin_file,
                        exc,
                    )

        _LOADED_WORKSPACES.add(ws_key)
        return loaded_ids
