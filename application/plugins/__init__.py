"""Plugin layer package cho workflow extensibility."""

from application.plugins.contracts import (
    IWorkflowPlugin,
    WorkflowPluginMetadata,
    WorkflowPluginRequest,
    WorkflowPluginResult,
)
from application.plugins.registry import (
    WorkflowPluginRegistry,
    workflow_plugin_registry,
)

__all__ = [
    "IWorkflowPlugin",
    "WorkflowPluginMetadata",
    "WorkflowPluginRequest",
    "WorkflowPluginResult",
    "WorkflowPluginRegistry",
    "workflow_plugin_registry",
]
