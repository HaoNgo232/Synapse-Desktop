"""
Workflow Engine - Pipeline abstraction cho use case workflow.

Ap dung Observer pattern de tach telemetry/progress ra khoi business flow,
va ap dung Step pipeline de chuan hoa cach thuc thi workflows.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol


def _empty_metadata_dict() -> Dict[str, Any]:
    """Tao dict rong co typing ro rang cho dataclass factory."""
    return {}


@dataclass
class WorkflowContext:
    """Context duoc chia se giua cac step trong workflow."""

    workflow_id: str
    workspace_path: Path
    payload: Dict[str, Any] = field(default_factory=_empty_metadata_dict)
    state: Dict[str, Any] = field(default_factory=_empty_metadata_dict)
    result: Any = None


@dataclass(frozen=True)
class WorkflowEvent:
    """Event duoc emit boi WorkflowEngine."""

    workflow_id: str
    stage: str
    status: str
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=_empty_metadata_dict)


class IWorkflowObserver(Protocol):
    """Observer contract de nhan event tu workflow engine."""

    def on_event(self, event: WorkflowEvent) -> None:
        """Nhan event va xu ly (log/metric/UI)."""
        ...


@dataclass
class CallableWorkflowStep:
    """Step implementation don gian dua tren callable."""

    name: str
    handler: Callable[[WorkflowContext], None]
    description: str = ""


class WorkflowEngine:
    """Engine chay workflow theo pipeline steps."""

    def __init__(self, observers: Optional[List[IWorkflowObserver]] = None) -> None:
        self._observers: List[IWorkflowObserver] = list(observers or [])

    def subscribe(self, observer: IWorkflowObserver) -> None:
        """Dang ky observer moi cho workflow events."""
        self._observers.append(observer)

    def unsubscribe(self, observer: IWorkflowObserver) -> None:
        """Go dang ky observer khoi workflow events."""
        self._observers = [o for o in self._observers if o is not observer]

    def run(
        self,
        context: WorkflowContext,
        steps: List[CallableWorkflowStep],
    ) -> WorkflowContext:
        """Chay workflow context qua danh sach steps theo thu tu."""
        self._emit(
            WorkflowEvent(
                workflow_id=context.workflow_id,
                stage="workflow",
                status="started",
                message="Workflow started",
            )
        )

        for step in steps:
            self._emit(
                WorkflowEvent(
                    workflow_id=context.workflow_id,
                    stage=step.name,
                    status="started",
                    message=step.description or f"Step '{step.name}' started",
                )
            )
            try:
                step.handler(context)
                self._emit(
                    WorkflowEvent(
                        workflow_id=context.workflow_id,
                        stage=step.name,
                        status="completed",
                        message=step.description or f"Step '{step.name}' completed",
                    )
                )
            except Exception as exc:
                self._emit(
                    WorkflowEvent(
                        workflow_id=context.workflow_id,
                        stage=step.name,
                        status="failed",
                        message=str(exc),
                    )
                )
                raise

        self._emit(
            WorkflowEvent(
                workflow_id=context.workflow_id,
                stage="workflow",
                status="completed",
                message="Workflow completed",
            )
        )
        return context

    def _emit(self, event: WorkflowEvent) -> None:
        """Emit event den tat ca observers theo best-effort."""
        for observer in self._observers:
            try:
                observer.on_event(event)
            except Exception:
                # Observer errors khong duoc phep lam fail workflow runtime
                continue
