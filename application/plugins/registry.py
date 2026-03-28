"""
Workflow Plugin Registry - Registry trung tam quan ly plugins.

Ap dung Registry pattern + lifecycle management.
"""

import threading
from typing import Dict, List, Set

from application.errors import UseCaseValidationError, WorkflowExecutionError
from application.plugins.contracts import (
    IWorkflowPlugin,
    WorkflowPluginMetadata,
    WorkflowPluginRequest,
    WorkflowPluginResult,
)


class WorkflowPluginRegistry:
    """Thread-safe registry quan ly workflow plugins."""

    def __init__(self) -> None:
        self._plugins: Dict[str, IWorkflowPlugin] = {}
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._active_executions: Dict[str, int] = {}
        self._shutting_down: Set[str] = set()

    def register(
        self, plugin: IWorkflowPlugin, *, allow_override: bool = False
    ) -> None:
        """Dang ky plugin vao registry."""
        plugin_id = plugin.metadata.plugin_id.strip()
        if not plugin_id:
            raise UseCaseValidationError("plugin_id must not be empty")

        with self._lock:
            if plugin_id in self._plugins and not allow_override:
                raise UseCaseValidationError(f"Plugin '{plugin_id}' already registered")
            self._plugins[plugin_id] = plugin

    def unregister(self, plugin_id: str) -> bool:
        """Go plugin khoi registry va dam bao khong shutdown khi dang execute."""
        with self._condition:
            plugin = self._plugins.get(plugin_id)
            if plugin is None:
                return False

            # Chan executions moi va cho executions dang chay ket thuc.
            self._shutting_down.add(plugin_id)
            while self._active_executions.get(plugin_id, 0) > 0:
                self._condition.wait(timeout=0.1)

            plugin = self._plugins.pop(plugin_id, None)
            self._shutting_down.discard(plugin_id)

        if plugin is None:
            return False

        try:
            plugin.shutdown()
        except Exception:
            # Khong de shutdown failure lam vo unregister flow
            pass
        return True

    def get(self, plugin_id: str) -> IWorkflowPlugin | None:
        """Lay plugin theo id."""
        with self._lock:
            return self._plugins.get(plugin_id)

    def list_metadata(self) -> List[WorkflowPluginMetadata]:
        """Lay metadata cua tat ca plugin da dang ky."""
        with self._lock:
            plugins = list(self._plugins.values())
        return [p.metadata for p in plugins]

    def execute(
        self,
        plugin_id: str,
        request: WorkflowPluginRequest,
    ) -> WorkflowPluginResult:
        """Execute plugin theo id voi request runtime."""
        with self._condition:
            plugin = self._plugins.get(plugin_id)
            if plugin is None:
                raise UseCaseValidationError(f"Unknown plugin_id: {plugin_id}")
            if plugin_id in self._shutting_down:
                raise UseCaseValidationError(f"Plugin '{plugin_id}' is shutting down")
            self._active_executions[plugin_id] = (
                self._active_executions.get(plugin_id, 0) + 1
            )

        try:
            return plugin.execute(request)
        except UseCaseValidationError:
            raise
        except Exception as exc:
            raise WorkflowExecutionError(
                f"Plugin '{plugin_id}' execution failed",
                details={"plugin_id": plugin_id},
                cause=exc,
            ) from exc
        finally:
            with self._condition:
                remaining = self._active_executions.get(plugin_id, 1) - 1
                if remaining <= 0:
                    self._active_executions.pop(plugin_id, None)
                else:
                    self._active_executions[plugin_id] = remaining
                self._condition.notify_all()


workflow_plugin_registry = WorkflowPluginRegistry()
