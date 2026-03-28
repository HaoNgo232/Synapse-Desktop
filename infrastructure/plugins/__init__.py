"""Infrastructure plugin adapters/loaders package."""

from infrastructure.plugins.workflow_plugin_loader import (
    discover_and_register_workflow_plugins,
)

__all__ = ["discover_and_register_workflow_plugins"]
