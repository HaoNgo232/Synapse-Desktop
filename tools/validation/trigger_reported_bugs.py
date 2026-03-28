"""
Trigger script de xac minh cac bug duoc report co that hay khong.

Muc tieu:
- Tai hien TOCTOU race giua execute/unregister trong WorkflowPluginRegistry.
- Tai hien loi ApplicationError.from_domain khi goi qua subclass.

Su dung:
    PYTHONPATH="$PWD" .venv/bin/python tools/validation/trigger_reported_bugs.py
"""

from __future__ import annotations

import json
import argparse
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from application.errors import WorkflowExecutionError
from application.plugins.contracts import (
    WorkflowPluginMetadata,
    WorkflowPluginRequest,
    WorkflowPluginResult,
)
from application.plugins.registry import WorkflowPluginRegistry
from domain.errors import DomainValidationError


@dataclass
class TriggerOutcome:
    """Ket qua trigger cua tung bug."""

    triggered: bool
    details: str


class _RacePlugin:
    """Plugin dung de tai hien race execute vs shutdown."""

    def __init__(self, plugin_id: str) -> None:
        self.metadata = WorkflowPluginMetadata(
            plugin_id=plugin_id,
            display_name="Race Plugin",
            version="1.0.0",
            description="Reproduce execute/unregister race",
        )
        self._started = threading.Event()
        self._shutdown_called = threading.Event()
        self._continue = threading.Event()

    def initialize(self) -> None:
        return None

    def execute(self, request: WorkflowPluginRequest) -> WorkflowPluginResult:
        self._started.set()
        self._continue.wait(timeout=5.0)
        if self._shutdown_called.is_set():
            raise RuntimeError("execute observed plugin after shutdown")
        return WorkflowPluginResult(True, "ok", {"action": request.action})

    def shutdown(self) -> None:
        self._shutdown_called.set()
        self._continue.set()

    def wait_started(self, timeout: float) -> bool:
        """Cho den khi execution bat dau."""
        return self._started.wait(timeout=timeout)

    def allow_continue(self) -> None:
        """Cho phep execution tiep tuc sau khi da orchestrate race."""
        self._continue.set()


def _trigger_registry_race() -> TriggerOutcome:
    registry = WorkflowPluginRegistry()
    plugin = _RacePlugin("race_trigger_plugin")
    registry.register(plugin)

    errors: Dict[str, BaseException] = {}

    def worker() -> None:
        try:
            registry.execute(
                plugin.metadata.plugin_id,
                WorkflowPluginRequest(workspace_path=Path.cwd(), action="race"),
            )
        except BaseException as exc:
            errors["exc"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    started = plugin.wait_started(timeout=2.0)
    if not started:
        registry.unregister(plugin.metadata.plugin_id)
        return TriggerOutcome(False, "worker did not start execution in time")

    unregister_ok = registry.unregister(plugin.metadata.plugin_id)
    plugin.allow_continue()
    thread.join(timeout=2.0)

    exc = errors.get("exc")
    if isinstance(exc, WorkflowExecutionError):
        return TriggerOutcome(
            True,
            f"race reproduced (unregister_ok={unregister_ok}): {exc}",
        )

    if exc is not None:
        return TriggerOutcome(
            False,
            f"unexpected exception type: {type(exc).__name__}: {exc}",
        )

    return TriggerOutcome(
        False,
        "no exception observed; race not reproduced this run",
    )


def _trigger_subclass_from_domain_bug() -> TriggerOutcome:
    # Trigger bug: subclass ke thua from_domain nhung __init__ khong nhan kwarg 'code'.
    try:
        _ = WorkflowExecutionError.from_domain(DomainValidationError("boom"))
    except TypeError as exc:
        return TriggerOutcome(True, f"TypeError reproduced: {exc}")
    except Exception as exc:
        return TriggerOutcome(
            False,
            f"unexpected exception type: {type(exc).__name__}: {exc}",
        )

    return TriggerOutcome(False, "no TypeError observed")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Trigger/verify reported bug scenarios"
    )
    parser.add_argument(
        "--expect",
        choices=("triggered", "fixed"),
        default="triggered",
        help="Validation mode: 'triggered' expects bugs to reproduce, 'fixed' expects bugs resolved.",
    )
    args = parser.parse_args()

    race = _trigger_registry_race()
    subclass = _trigger_subclass_from_domain_bug()

    report: Dict[str, Any] = {
        "registry_execute_unregister_race": {
            "triggered": race.triggered,
            "details": race.details,
        },
        "subclass_from_domain_typeerror": {
            "triggered": subclass.triggered,
            "details": subclass.details,
        },
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.expect == "triggered":
        return 0 if race.triggered and subclass.triggered else 1
    return 0 if (not race.triggered and not subclass.triggered) else 1


if __name__ == "__main__":
    raise SystemExit(main())
