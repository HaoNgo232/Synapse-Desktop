"""
Plugin Contracts - Dinh nghia extension boundary cho workflow plugins.

Plugin moi co the duoc nap dong ma khong can sua core workflow handler.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Protocol, runtime_checkable


def _empty_plugin_payload() -> Dict[str, Any]:
    """Tao dict rong co typing ro rang cho dataclass factory."""
    return {}


@dataclass(frozen=True)
class WorkflowPluginMetadata:
    """Metadata cua plugin de expose cho MCP/UI."""

    plugin_id: str
    display_name: str
    version: str
    description: str


@dataclass(frozen=True)
class WorkflowPluginRequest:
    """Input payload truyen vao plugin runtime."""

    workspace_path: Path
    action: str = "run"
    payload: Dict[str, Any] = field(default_factory=_empty_plugin_payload)


@dataclass
class WorkflowPluginResult:
    """Ket qua plugin execution."""

    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=_empty_plugin_payload)


@runtime_checkable
class IWorkflowPlugin(Protocol):
    """Contract bat buoc cho workflow plugin."""

    metadata: WorkflowPluginMetadata

    def initialize(self) -> None:
        """Khoi tao resource can thiet truoc khi plugin duoc goi."""
        ...

    def execute(self, request: WorkflowPluginRequest) -> WorkflowPluginResult:
        """Thuc thi plugin voi request runtime."""
        ...

    def shutdown(self) -> None:
        """Cleanup resource khi server dung/refresh plugin."""
        ...
