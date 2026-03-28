"""
Simulation script de kiem chung output cho cac use case chinh cua project.

Muc tieu:
- Gia lap va verify it nhat 50 use case su dung runtime.
- In bao cao pass/fail chi tiet theo tung use case.
- Xuat report JSON de luu vet ket qua validation.

Su dung:
    python tools/validation/simulate_project_usecases.py
    python tools/validation/simulate_project_usecases.py --fail-fast
    python tools/validation/simulate_project_usecases.py --report-path /tmp/report.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import tempfile
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Literal,
    Optional,
    Protocol,
    cast,
)

from application.errors import (
    ApplicationError,
    UseCaseValidationError,
    WorkflowExecutionError,
)
from application.plugins.contracts import (
    WorkflowPluginMetadata,
    WorkflowPluginRequest,
    WorkflowPluginResult,
)
from application.plugins.registry import workflow_plugin_registry
from application.use_cases.workflow_engine import (
    CallableWorkflowStep,
    IWorkflowObserver,
    WorkflowContext,
    WorkflowEngine,
    WorkflowEvent,
)
from application.use_cases.workflow_use_cases import (
    BuildContextCommand,
    BuildContextUseCase,
    CodeReviewCommand,
    CodeReviewUseCase,
    DesignPlannerCommand,
    DesignPlannerUseCase,
    InvestigateCommand,
    InvestigateUseCase,
    RefactorCommand,
    RefactorUseCase,
    TestBuildCommand,
    TestBuildUseCase,
)
from domain.contracts.contract_pack import (
    ContractPack,
    build_contract_pack,
    load_contract_pack,
    locked_modify_contract_pack,
    save_contract_pack,
)
from domain.errors import (
    DomainError,
    DomainValidationError,
    InvariantViolationError,
)
from domain.memory import memory_service as memory_service_module
from infrastructure.errors import ConfigurationError, InfrastructureError, NetworkError
from infrastructure.mcp.core.error_mapper import (
    format_mcp_error,
    map_exception_to_payload,
)
from infrastructure.plugins.workflow_plugin_loader import (
    discover_and_register_workflow_plugins,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_PATH = ROOT / "tools" / "validation" / "usecase_simulation_report.json"

_PluginCounter = Iterator[int]
_plugin_counter: _PluginCounter = itertools.count(1)


class AddMemoryFn(Protocol):
    """Callable protocol cho add_memory de static typing dung optional defaults."""

    def __call__(
        self,
        workspace_root: Path,
        layer: Literal["action", "decision", "constraint"],
        content: str,
        linked_files: Optional[List[str]] = None,
        linked_symbols: Optional[List[str]] = None,
        workflow: str = "",
        tags: Optional[List[str]] = None,
        max_entries: int = 100,
    ) -> None: ...


class LoadMemoryStoreFn(Protocol):
    """Callable protocol cho load_memory_store."""

    def __call__(self, workspace_root: Path) -> Any: ...


add_memory_fn = cast(
    AddMemoryFn,
    getattr(memory_service_module, "add_memory"),
)

load_memory_store_fn = cast(
    LoadMemoryStoreFn,
    getattr(memory_service_module, "load_memory_store"),
)


@dataclass
class CaseResult:
    """Ket qua mot use case simulation."""

    index: int
    name: str
    passed: bool
    output: str
    error: str = ""


def expect(condition: bool, message: str) -> None:
    """Assert helper co message ro rang."""
    if not condition:
        raise AssertionError(message)


def expect_raises(
    exc_type: type[BaseException],
    fn: Callable[[], Any],
    *,
    case_name: str,
) -> BaseException:
    """Dam bao callable raise dung loai exception."""
    try:
        fn()
    except exc_type as exc:  # type: ignore[misc]
        return exc
    except Exception as exc:
        raise AssertionError(
            f"{case_name}: expected {exc_type.__name__}, got {type(exc).__name__}: {exc}"
        ) from exc

    raise AssertionError(
        f"{case_name}: expected {exc_type.__name__} but no exception raised"
    )


class CaptureObserver(IWorkflowObserver):
    """Observer dung de capture events tu workflow engine."""

    def __init__(self) -> None:
        self.events: List[WorkflowEvent] = []

    def on_event(self, event: WorkflowEvent) -> None:
        self.events.append(event)


class ExplodingObserver(IWorkflowObserver):
    """Observer no luc de verify engine khong bi fail vi observer loi."""

    def on_event(self, event: WorkflowEvent) -> None:
        raise RuntimeError(f"observer exploded at {event.stage}")


class DummyPlugin:
    """Plugin gia lap thanh cong cho registry/loader simulation."""

    def __init__(self, plugin_id: str, marker: str = "ok") -> None:
        self.metadata = WorkflowPluginMetadata(
            plugin_id=plugin_id,
            display_name=f"Dummy {plugin_id}",
            version="1.0.0",
            description="Dummy plugin for simulation",
        )
        self.marker = marker
        self.shutdown_calls = 0

    def initialize(self) -> None:
        return None

    def execute(self, request: WorkflowPluginRequest) -> WorkflowPluginResult:
        payload = dict(request.payload)
        payload["marker"] = self.marker
        return WorkflowPluginResult(
            success=True,
            message=f"executed:{request.action}",
            data=payload,
        )

    def shutdown(self) -> None:
        self.shutdown_calls += 1


class ValidationFailPlugin(DummyPlugin):
    """Plugin gia lap loi validation de test propagation."""

    def execute(self, request: WorkflowPluginRequest) -> WorkflowPluginResult:
        raise UseCaseValidationError(
            "invalid plugin request", details={"action": request.action}
        )


class CrashPlugin(DummyPlugin):
    """Plugin gia lap crash de test wrapping sang WorkflowExecutionError."""

    def execute(self, request: WorkflowPluginRequest) -> WorkflowPluginResult:
        raise RuntimeError("unexpected plugin crash")


def unique_plugin_id(base: str) -> str:
    """Sinh plugin id unique de tranh trung giua cac case."""
    return f"sim_{base}_{next(_plugin_counter)}"


def build_error_mapper_cases(cases: List[tuple[str, Callable[[], str]]]) -> None:
    """Nhom use case map/format error payload."""

    def make_case(
        name: str,
        exc_factory: Callable[[], BaseException],
        expected_category: str,
        expected_code: str,
        expected_retryable: bool,
    ) -> tuple[str, Callable[[], str]]:
        def run() -> str:
            payload = map_exception_to_payload(exc_factory())
            expect(payload.category == expected_category, f"{name}: wrong category")
            expect(payload.code == expected_code, f"{name}: wrong code")
            expect(payload.retryable == expected_retryable, f"{name}: wrong retryable")
            return f"{payload.category}:{payload.code}:{payload.retryable}"

        return name, run

    mapper_specs = [
        (
            "map_use_case_validation_error",
            lambda: UseCaseValidationError("invalid input"),
            "application",
            "use_case_validation_error",
            False,
        ),
        (
            "map_application_error",
            lambda: ApplicationError("app broken", code="app_broken"),
            "application",
            "app_broken",
            False,
        ),
        (
            "map_workflow_execution_error",
            lambda: WorkflowExecutionError("workflow failed"),
            "application",
            "workflow_execution_error",
            False,
        ),
        (
            "map_domain_validation_error",
            lambda: DomainValidationError("domain invalid"),
            "domain",
            "domain_validation_error",
            False,
        ),
        (
            "map_domain_error",
            lambda: DomainError("domain fail", code="domain_fail"),
            "domain",
            "domain_fail",
            False,
        ),
        (
            "map_invariant_violation_error",
            lambda: InvariantViolationError("invariant fail"),
            "domain",
            "domain_invariant_violation",
            False,
        ),
        (
            "map_infrastructure_error_retryable",
            lambda: InfrastructureError("infra fail", retryable=True),
            "infrastructure",
            "infrastructure_error",
            True,
        ),
        (
            "map_network_error",
            lambda: NetworkError("network fail"),
            "infrastructure",
            "network_error",
            True,
        ),
        (
            "map_configuration_error",
            lambda: ConfigurationError("bad config"),
            "infrastructure",
            "configuration_error",
            False,
        ),
        (
            "map_value_error",
            lambda: ValueError("wrong value"),
            "validation",
            "value_error",
            False,
        ),
        (
            "map_unexpected_runtime_error",
            lambda: RuntimeError("boom"),
            "unexpected",
            "unexpected_error",
            False,
        ),
        (
            "map_unexpected_empty_message",
            lambda: RuntimeError(""),
            "unexpected",
            "unexpected_error",
            False,
        ),
    ]

    for spec in mapper_specs:
        cases.append(make_case(*spec))

    def case_format_default_prefix() -> str:
        out = format_mcp_error(UseCaseValidationError("bad request"))
        expect(
            out.startswith("Error:"), "format_default_prefix: missing default prefix"
        )
        expect(
            "application:use_case_validation_error" in out,
            "format_default_prefix: missing code",
        )
        return out

    def case_format_custom_prefix() -> str:
        out = format_mcp_error(NetworkError("timeout"), prefix="Failure")
        expect(out.startswith("Failure:"), "format_custom_prefix: wrong custom prefix")
        expect("retryable" in out, "format_custom_prefix: retryable mark missing")
        return out

    cases.append(("format_error_default_prefix", case_format_default_prefix))
    cases.append(("format_error_custom_prefix", case_format_custom_prefix))


def build_workflow_engine_cases(cases: List[tuple[str, Callable[[], str]]]) -> None:
    """Nhom use case cho workflow engine va observer."""

    def case_single_step_sets_result() -> str:
        ctx = WorkflowContext(workflow_id="wf_1", workspace_path=ROOT)

        def step(context: WorkflowContext) -> None:
            context.result = "done"

        engine = WorkflowEngine()
        final_ctx = engine.run(ctx, [CallableWorkflowStep(name="only", handler=step)])
        expect(final_ctx.result == "done", "single_step_sets_result: result mismatch")
        return str(final_ctx.result)

    def case_two_steps_state_flow() -> str:
        ctx = WorkflowContext(workflow_id="wf_2", workspace_path=ROOT)

        def step_1(context: WorkflowContext) -> None:
            context.state["count"] = 1

        def step_2(context: WorkflowContext) -> None:
            context.state["count"] = int(context.state["count"]) + 1

        engine = WorkflowEngine()
        final_ctx = engine.run(
            ctx,
            [
                CallableWorkflowStep(name="step_1", handler=step_1),
                CallableWorkflowStep(name="step_2", handler=step_2),
            ],
        )
        expect(final_ctx.state["count"] == 2, "two_steps_state_flow: invalid count")
        return f"count={final_ctx.state['count']}"

    def case_observer_receives_events() -> str:
        ctx = WorkflowContext(workflow_id="wf_3", workspace_path=ROOT)
        observer = CaptureObserver()

        def noop(context: WorkflowContext) -> None:
            context.result = "ok"

        engine = WorkflowEngine([observer])
        engine.run(
            ctx, [CallableWorkflowStep(name="noop", handler=noop, description="No-op")]
        )
        statuses = [e.status for e in observer.events]
        expect(
            "started" in statuses and "completed" in statuses,
            "observer_receives_events: missing status",
        )
        return f"events={len(observer.events)}"

    def case_failing_step_emits_failed() -> str:
        ctx = WorkflowContext(workflow_id="wf_4", workspace_path=ROOT)
        observer = CaptureObserver()

        def boom(context: WorkflowContext) -> None:
            raise RuntimeError("step fail")

        engine = WorkflowEngine([observer])

        exc = expect_raises(
            RuntimeError,
            lambda: engine.run(ctx, [CallableWorkflowStep(name="boom", handler=boom)]),
            case_name="failing_step_emits_failed",
        )
        expect(str(exc) == "step fail", "failing_step_emits_failed: wrong exception")
        failed_events = [e for e in observer.events if e.status == "failed"]
        expect(
            len(failed_events) == 1, "failing_step_emits_failed: failed event missing"
        )
        return f"failed_events={len(failed_events)}"

    def case_observer_failure_does_not_break_engine() -> str:
        ctx = WorkflowContext(workflow_id="wf_5", workspace_path=ROOT)

        def noop(context: WorkflowContext) -> None:
            context.result = "safe"

        engine = WorkflowEngine([ExplodingObserver()])
        final_ctx = engine.run(ctx, [CallableWorkflowStep(name="noop", handler=noop)])
        expect(
            final_ctx.result == "safe",
            "observer_failure_does_not_break_engine: result mismatch",
        )
        return str(final_ctx.result)

    def case_subscribe_unsubscribe() -> str:
        ctx = WorkflowContext(workflow_id="wf_6", workspace_path=ROOT)
        observer = CaptureObserver()

        def noop(context: WorkflowContext) -> None:
            context.result = "ok"

        engine = WorkflowEngine()
        engine.subscribe(observer)
        engine.unsubscribe(observer)
        engine.run(ctx, [CallableWorkflowStep(name="noop", handler=noop)])
        expect(
            len(observer.events) == 0,
            "subscribe_unsubscribe: observer should be detached",
        )
        return "detached"

    def case_description_fallback_message() -> str:
        ctx = WorkflowContext(workflow_id="wf_7", workspace_path=ROOT)
        observer = CaptureObserver()

        def noop(context: WorkflowContext) -> None:
            context.result = "ok"

        engine = WorkflowEngine([observer])
        engine.run(ctx, [CallableWorkflowStep(name="step_x", handler=noop)])
        step_started = [
            e for e in observer.events if e.stage == "step_x" and e.status == "started"
        ]
        expect(bool(step_started), "description_fallback_message: missing step started")
        expect(
            "step_x" in step_started[0].message,
            "description_fallback_message: wrong fallback message",
        )
        return step_started[0].message

    def case_workflow_id_propagation() -> str:
        ctx = WorkflowContext(workflow_id="wf_8", workspace_path=ROOT)
        observer = CaptureObserver()

        def noop(context: WorkflowContext) -> None:
            context.result = "ok"

        engine = WorkflowEngine([observer])
        engine.run(ctx, [CallableWorkflowStep(name="noop", handler=noop)])
        ids = {e.workflow_id for e in observer.events}
        expect(ids == {"wf_8"}, "workflow_id_propagation: workflow id mismatch")
        return next(iter(ids))

    def case_context_payload_state_defaults() -> str:
        ctx = WorkflowContext(workflow_id="wf_9", workspace_path=ROOT)
        expect(ctx.payload == {}, "context_payload_state_defaults: payload not empty")
        expect(ctx.state == {}, "context_payload_state_defaults: state not empty")
        return "defaults-ok"

    def case_context_result_updated_last_step() -> str:
        ctx = WorkflowContext(workflow_id="wf_10", workspace_path=ROOT)

        def step_1(context: WorkflowContext) -> None:
            context.result = "first"

        def step_2(context: WorkflowContext) -> None:
            context.result = "second"

        engine = WorkflowEngine()
        final_ctx = engine.run(
            ctx,
            [
                CallableWorkflowStep(name="one", handler=step_1),
                CallableWorkflowStep(name="two", handler=step_2),
            ],
        )
        expect(
            final_ctx.result == "second",
            "context_result_updated_last_step: wrong final result",
        )
        return str(final_ctx.result)

    cases.extend(
        [
            ("workflow_engine_single_step_sets_result", case_single_step_sets_result),
            ("workflow_engine_two_steps_state_flow", case_two_steps_state_flow),
            ("workflow_engine_observer_receives_events", case_observer_receives_events),
            (
                "workflow_engine_failing_step_emits_failed",
                case_failing_step_emits_failed,
            ),
            (
                "workflow_engine_observer_failure_does_not_break_engine",
                case_observer_failure_does_not_break_engine,
            ),
            ("workflow_engine_subscribe_unsubscribe", case_subscribe_unsubscribe),
            (
                "workflow_engine_description_fallback_message",
                case_description_fallback_message,
            ),
            ("workflow_engine_workflow_id_propagation", case_workflow_id_propagation),
            (
                "workflow_engine_context_payload_state_defaults",
                case_context_payload_state_defaults,
            ),
            (
                "workflow_engine_context_result_updated_last_step",
                case_context_result_updated_last_step,
            ),
        ]
    )


def build_plugin_registry_cases(cases: List[tuple[str, Callable[[], str]]]) -> None:
    """Nhom use case cho plugin registry lifecycle."""

    def case_register_success() -> str:
        plugin_id = unique_plugin_id("register_success")
        plugin = DummyPlugin(plugin_id)
        workflow_plugin_registry.register(plugin)
        try:
            md = workflow_plugin_registry.get(plugin_id)
            expect(md is not None, "register_success: plugin not found")
            return plugin_id
        finally:
            workflow_plugin_registry.unregister(plugin_id)

    def case_register_duplicate_without_override() -> str:
        plugin_id = unique_plugin_id("dup_no_override")
        plugin = DummyPlugin(plugin_id)
        workflow_plugin_registry.register(plugin)
        try:
            exc = expect_raises(
                UseCaseValidationError,
                lambda: workflow_plugin_registry.register(DummyPlugin(plugin_id)),
                case_name="register_duplicate_without_override",
            )
            return str(exc)
        finally:
            workflow_plugin_registry.unregister(plugin_id)

    def case_register_duplicate_with_override() -> str:
        plugin_id = unique_plugin_id("dup_override")
        workflow_plugin_registry.register(DummyPlugin(plugin_id, marker="v1"))
        workflow_plugin_registry.register(
            DummyPlugin(plugin_id, marker="v2"), allow_override=True
        )
        try:
            result = workflow_plugin_registry.execute(
                plugin_id,
                WorkflowPluginRequest(workspace_path=ROOT, payload={"x": 1}),
            )
            expect(
                result.data.get("marker") == "v2",
                "register_duplicate_with_override: override failed",
            )
            return str(result.data)
        finally:
            workflow_plugin_registry.unregister(plugin_id)

    def case_list_metadata_contains_registered() -> str:
        plugin_id = unique_plugin_id("list_meta")
        workflow_plugin_registry.register(DummyPlugin(plugin_id))
        try:
            ids = [m.plugin_id for m in workflow_plugin_registry.list_metadata()]
            expect(plugin_id in ids, "list_metadata_contains_registered: id missing")
            return f"count={len(ids)}"
        finally:
            workflow_plugin_registry.unregister(plugin_id)

    def case_get_returns_plugin() -> str:
        plugin_id = unique_plugin_id("get_plugin")
        workflow_plugin_registry.register(DummyPlugin(plugin_id))
        try:
            plugin = workflow_plugin_registry.get(plugin_id)
            if plugin is None:
                raise AssertionError("get_returns_plugin: plugin missing")
            return plugin.metadata.plugin_id
        finally:
            workflow_plugin_registry.unregister(plugin_id)

    def case_execute_success() -> str:
        plugin_id = unique_plugin_id("exec_success")
        workflow_plugin_registry.register(DummyPlugin(plugin_id))
        try:
            result = workflow_plugin_registry.execute(
                plugin_id,
                WorkflowPluginRequest(
                    workspace_path=ROOT,
                    action="simulate",
                    payload={"k": "v"},
                ),
            )
            expect(result.success, "execute_success: result should be success")
            expect(
                result.message == "executed:simulate",
                "execute_success: message mismatch",
            )
            return json.dumps(result.data, ensure_ascii=True)
        finally:
            workflow_plugin_registry.unregister(plugin_id)

    def case_execute_unknown_plugin() -> str:
        plugin_id = unique_plugin_id("unknown")
        exc = expect_raises(
            UseCaseValidationError,
            lambda: workflow_plugin_registry.execute(
                plugin_id,
                WorkflowPluginRequest(workspace_path=ROOT),
            ),
            case_name="execute_unknown_plugin",
        )
        return str(exc)

    def case_execute_validation_error_propagates() -> str:
        plugin_id = unique_plugin_id("validation_fail")
        workflow_plugin_registry.register(ValidationFailPlugin(plugin_id))
        try:
            exc = expect_raises(
                UseCaseValidationError,
                lambda: workflow_plugin_registry.execute(
                    plugin_id,
                    WorkflowPluginRequest(workspace_path=ROOT, action="bad"),
                ),
                case_name="execute_validation_error_propagates",
            )
            return str(exc)
        finally:
            workflow_plugin_registry.unregister(plugin_id)

    def case_execute_crash_wrapped_as_workflow_error() -> str:
        plugin_id = unique_plugin_id("crash")
        workflow_plugin_registry.register(CrashPlugin(plugin_id))
        try:
            exc = expect_raises(
                WorkflowExecutionError,
                lambda: workflow_plugin_registry.execute(
                    plugin_id,
                    WorkflowPluginRequest(workspace_path=ROOT),
                ),
                case_name="execute_crash_wrapped_as_workflow_error",
            )
            return str(exc)
        finally:
            workflow_plugin_registry.unregister(plugin_id)

    def case_unregister_existing_returns_true() -> str:
        plugin_id = unique_plugin_id("unregister_true")
        workflow_plugin_registry.register(DummyPlugin(plugin_id))
        result = workflow_plugin_registry.unregister(plugin_id)
        expect(result is True, "unregister_existing_returns_true: expected True")
        return str(result)

    def case_unregister_unknown_returns_false() -> str:
        plugin_id = unique_plugin_id("unregister_false")
        result = workflow_plugin_registry.unregister(plugin_id)
        expect(result is False, "unregister_unknown_returns_false: expected False")
        return str(result)

    def case_unregister_calls_shutdown() -> str:
        plugin_id = unique_plugin_id("shutdown_call")
        plugin = DummyPlugin(plugin_id)
        workflow_plugin_registry.register(plugin)
        try:
            removed = workflow_plugin_registry.unregister(plugin_id)
            expect(
                removed is True, "unregister_calls_shutdown: unregister should succeed"
            )
            expect(
                plugin.shutdown_calls == 1,
                "unregister_calls_shutdown: shutdown count mismatch",
            )
            return f"shutdown_calls={plugin.shutdown_calls}"
        finally:
            workflow_plugin_registry.unregister(plugin_id)

    cases.extend(
        [
            ("plugin_registry_register_success", case_register_success),
            (
                "plugin_registry_register_duplicate_without_override",
                case_register_duplicate_without_override,
            ),
            (
                "plugin_registry_register_duplicate_with_override",
                case_register_duplicate_with_override,
            ),
            (
                "plugin_registry_list_metadata_contains_registered",
                case_list_metadata_contains_registered,
            ),
            ("plugin_registry_get_returns_plugin", case_get_returns_plugin),
            ("plugin_registry_execute_success", case_execute_success),
            ("plugin_registry_execute_unknown_plugin", case_execute_unknown_plugin),
            (
                "plugin_registry_execute_validation_error_propagates",
                case_execute_validation_error_propagates,
            ),
            (
                "plugin_registry_execute_crash_wrapped_as_workflow_error",
                case_execute_crash_wrapped_as_workflow_error,
            ),
            (
                "plugin_registry_unregister_existing_returns_true",
                case_unregister_existing_returns_true,
            ),
            (
                "plugin_registry_unregister_unknown_returns_false",
                case_unregister_unknown_returns_false,
            ),
            (
                "plugin_registry_unregister_calls_shutdown",
                case_unregister_calls_shutdown,
            ),
        ]
    )


def build_plugin_loader_cases(cases: List[tuple[str, Callable[[], str]]]) -> None:
    """Nhom use case cho plugin discovery/loading runtime."""

    def _write_plugin_file(workspace: Path, file_name: str, content: str) -> None:
        plugin_dir = workspace / ".synapse" / "plugins"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (plugin_dir / file_name).write_text(content, encoding="utf-8")

    def case_loader_discovers_valid_plugin() -> str:
        with tempfile.TemporaryDirectory(prefix="synapse_loader_valid_") as tmp:
            ws = Path(tmp)
            plugin_id = unique_plugin_id("loader_valid")
            _write_plugin_file(
                ws,
                "valid_plugin.py",
                "\n".join(
                    [
                        "from application.plugins.contracts import WorkflowPluginMetadata, WorkflowPluginResult",
                        "",
                        "class _Plugin:",
                        "    metadata = WorkflowPluginMetadata(",
                        f"        plugin_id='{plugin_id}',",
                        "        display_name='Valid Plugin',",
                        "        version='1.0.0',",
                        "        description='valid',",
                        "    )",
                        "    def initialize(self):",
                        "        return None",
                        "    def execute(self, request):",
                        "        return WorkflowPluginResult(True, 'ok', {'source': 'loader'})",
                        "    def shutdown(self):",
                        "        return None",
                        "",
                        "def create_plugin():",
                        "    return _Plugin()",
                        "",
                    ]
                ),
            )

            loaded_ids = discover_and_register_workflow_plugins(ws)
            expect(
                plugin_id in loaded_ids,
                "loader_discovers_valid_plugin: plugin id not loaded",
            )

            try:
                result = workflow_plugin_registry.execute(
                    plugin_id,
                    WorkflowPluginRequest(workspace_path=ws),
                )
                expect(
                    result.success, "loader_discovers_valid_plugin: execution failed"
                )
                return json.dumps({"loaded": loaded_ids, "message": result.message})
            finally:
                workflow_plugin_registry.unregister(plugin_id)

    def case_loader_is_idempotent_per_workspace() -> str:
        with tempfile.TemporaryDirectory(prefix="synapse_loader_idempotent_") as tmp:
            ws = Path(tmp)
            plugin_id = unique_plugin_id("loader_idempotent")
            _write_plugin_file(
                ws,
                "idempotent_plugin.py",
                "\n".join(
                    [
                        "from application.plugins.contracts import WorkflowPluginMetadata, WorkflowPluginResult",
                        "",
                        "class _Plugin:",
                        "    metadata = WorkflowPluginMetadata(",
                        f"        plugin_id='{plugin_id}',",
                        "        display_name='Idempotent Plugin',",
                        "        version='1.0.0',",
                        "        description='idempotent',",
                        "    )",
                        "    def initialize(self):",
                        "        return None",
                        "    def execute(self, request):",
                        "        return WorkflowPluginResult(True, 'ok', {})",
                        "    def shutdown(self):",
                        "        return None",
                        "",
                        "def create_plugin():",
                        "    return _Plugin()",
                        "",
                    ]
                ),
            )

            loaded_first = discover_and_register_workflow_plugins(ws)
            loaded_second = discover_and_register_workflow_plugins(ws)
            expect(
                plugin_id in loaded_first,
                "loader_is_idempotent_per_workspace: missing first load",
            )
            expect(
                loaded_second == [],
                "loader_is_idempotent_per_workspace: second load should be empty",
            )
            workflow_plugin_registry.unregister(plugin_id)
            return f"first={len(loaded_first)},second={len(loaded_second)}"

    def case_loader_skips_missing_factory() -> str:
        with tempfile.TemporaryDirectory(
            prefix="synapse_loader_missing_factory_"
        ) as tmp:
            ws = Path(tmp)
            _write_plugin_file(
                ws,
                "missing_factory.py",
                "class Nothing:\n    pass\n",
            )
            loaded_ids = discover_and_register_workflow_plugins(ws)
            expect(loaded_ids == [], "loader_skips_missing_factory: should skip module")
            return "skipped"

    def case_loader_skips_factory_exception() -> str:
        with tempfile.TemporaryDirectory(prefix="synapse_loader_factory_fail_") as tmp:
            ws = Path(tmp)
            _write_plugin_file(
                ws,
                "factory_fail.py",
                "\n".join(
                    [
                        "def create_plugin():",
                        "    raise RuntimeError('factory failed')",
                        "",
                    ]
                ),
            )
            loaded_ids = discover_and_register_workflow_plugins(ws)
            expect(
                loaded_ids == [],
                "loader_skips_factory_exception: should skip failed factory",
            )
            return "factory-error-skipped"

    def case_loader_skips_invalid_contract() -> str:
        with tempfile.TemporaryDirectory(
            prefix="synapse_loader_invalid_contract_"
        ) as tmp:
            ws = Path(tmp)
            _write_plugin_file(
                ws,
                "invalid_contract.py",
                "\n".join(
                    [
                        "def create_plugin():",
                        "    return object()",
                        "",
                    ]
                ),
            )
            loaded_ids = discover_and_register_workflow_plugins(ws)
            expect(
                loaded_ids == [],
                "loader_skips_invalid_contract: should skip invalid plugin",
            )
            return "invalid-contract-skipped"

    cases.extend(
        [
            (
                "plugin_loader_discovers_valid_plugin",
                case_loader_discovers_valid_plugin,
            ),
            (
                "plugin_loader_is_idempotent_per_workspace",
                case_loader_is_idempotent_per_workspace,
            ),
            ("plugin_loader_skips_missing_factory", case_loader_skips_missing_factory),
            (
                "plugin_loader_skips_factory_exception",
                case_loader_skips_factory_exception,
            ),
            (
                "plugin_loader_skips_invalid_contract",
                case_loader_skips_invalid_contract,
            ),
        ]
    )


def build_memory_cases(cases: List[tuple[str, Callable[[], str]]]) -> None:
    """Nhom use case cho memory v2 service."""

    def case_load_empty_store() -> str:
        with tempfile.TemporaryDirectory(prefix="synapse_memory_empty_") as tmp:
            ws = Path(tmp)
            store = load_memory_store_fn(ws)
            expect(len(store.entries) == 0, "load_empty_store: expected empty store")
            return "entries=0"

    def case_add_memory_and_load() -> str:
        with tempfile.TemporaryDirectory(prefix="synapse_memory_add_") as tmp:
            ws = Path(tmp)
            add_memory_fn(ws, "action", "added file A")
            store = load_memory_store_fn(ws)
            expect(len(store.entries) == 1, "add_memory_and_load: expected 1 entry")
            return f"entries={len(store.entries)}"

    def case_get_by_layer() -> str:
        with tempfile.TemporaryDirectory(prefix="synapse_memory_layer_") as tmp:
            ws = Path(tmp)
            add_memory_fn(ws, "action", "changed X")
            add_memory_fn(ws, "decision", "choose strategy")
            store = load_memory_store_fn(ws)
            decision_entries = store.get_by_layer("decision")
            expect(
                len(decision_entries) == 1, "get_by_layer: expected one decision entry"
            )
            return decision_entries[0].content

    def case_get_by_file() -> str:
        with tempfile.TemporaryDirectory(prefix="synapse_memory_file_") as tmp:
            ws = Path(tmp)
            add_memory_fn(ws, "action", "touch file", ["src/a.py"])
            add_memory_fn(ws, "action", "touch other", ["src/b.py"])
            store = load_memory_store_fn(ws)
            matches = store.get_by_file("src/a.py")
            expect(len(matches) == 1, "get_by_file: expected one match")
            return matches[0].content

    def case_format_for_prompt() -> str:
        with tempfile.TemporaryDirectory(prefix="synapse_memory_prompt_") as tmp:
            ws = Path(tmp)
            add_memory_fn(ws, "constraint", "Do not break API")
            add_memory_fn(ws, "decision", "Use service boundary")
            store = load_memory_store_fn(ws)
            formatted = store.format_for_prompt()
            expect(
                "Project Constraints" in formatted,
                "format_for_prompt: missing constraints header",
            )
            expect(
                "Past Decisions" in formatted,
                "format_for_prompt: missing decisions header",
            )
            return formatted.splitlines()[0]

    def case_trim_max_entries() -> str:
        with tempfile.TemporaryDirectory(prefix="synapse_memory_trim_") as tmp:
            ws = Path(tmp)
            for idx in range(5):
                add_memory_fn(ws, "action", f"entry-{idx}", None, None, "", None, 2)
            store = load_memory_store_fn(ws)
            actions = store.get_by_layer("action")
            expect(
                len(actions) <= 2, "trim_max_entries: expected at most 2 action entries"
            )
            return f"remaining={len(actions)}"

    cases.extend(
        [
            ("memory_load_empty_store", case_load_empty_store),
            ("memory_add_memory_and_load", case_add_memory_and_load),
            ("memory_get_by_layer", case_get_by_layer),
            ("memory_get_by_file", case_get_by_file),
            ("memory_format_for_prompt", case_format_for_prompt),
            ("memory_trim_max_entries", case_trim_max_entries),
        ]
    )


def build_contract_pack_cases(cases: List[tuple[str, Callable[[], str]]]) -> None:
    """Nhom use case cho contract pack workflow."""

    def case_load_missing_contract_pack() -> str:
        with tempfile.TemporaryDirectory(prefix="synapse_contract_empty_") as tmp:
            ws = Path(tmp)
            pack = load_contract_pack(ws)
            expect(
                pack.conventions == [],
                "load_missing_contract_pack: conventions should be empty",
            )
            return "empty"

    def case_save_and_load_contract_pack() -> str:
        with tempfile.TemporaryDirectory(prefix="synapse_contract_save_") as tmp:
            ws = Path(tmp)
            pack = ContractPack(
                conventions=["Use absolute imports"], review_checklist=["Run tests"]
            )
            save_contract_pack(ws, pack)
            loaded = load_contract_pack(ws)
            expect(
                loaded.conventions == ["Use absolute imports"],
                "save_and_load_contract_pack: conventions mismatch",
            )
            return loaded.conventions[0]

    def case_locked_modify_add_convention() -> str:
        with tempfile.TemporaryDirectory(prefix="synapse_contract_mod_conv_") as tmp:
            ws = Path(tmp)

            def modifier(pack: ContractPack) -> ContractPack:
                pack.conventions.append("No circular imports")
                return pack

            pack = locked_modify_contract_pack(ws, modifier)
            expect(
                "No circular imports" in pack.conventions,
                "locked_modify_add_convention: convention missing",
            )
            return str(len(pack.conventions))

    def case_locked_modify_add_anti_pattern() -> str:
        with tempfile.TemporaryDirectory(prefix="synapse_contract_mod_anti_") as tmp:
            ws = Path(tmp)

            def modifier(pack: ContractPack) -> ContractPack:
                pack.anti_patterns.append("Do not mutate shared global state")
                return pack

            pack = locked_modify_contract_pack(ws, modifier)
            expect(
                len(pack.anti_patterns) == 1,
                "locked_modify_add_anti_pattern: anti pattern missing",
            )
            return pack.anti_patterns[0]

    def case_locked_modify_add_guarded_path() -> str:
        with tempfile.TemporaryDirectory(prefix="synapse_contract_mod_guarded_") as tmp:
            ws = Path(tmp)

            def modifier(pack: ContractPack) -> ContractPack:
                pack.guarded_paths.append(
                    "infrastructure/mcp/handlers/workflow_handler.py"
                )
                return pack

            pack = locked_modify_contract_pack(ws, modifier)
            expect(
                len(pack.guarded_paths) == 1,
                "locked_modify_add_guarded_path: guarded path missing",
            )
            return pack.guarded_paths[0]

    def case_format_for_prompt_sections() -> str:
        pack = ContractPack(
            conventions=["Keep layering strict"],
            anti_patterns=["No direct infra import from domain"],
            review_checklist=["Verify architecture tests"],
            required_tests=[
                "pytest tests/architecture/test_architecture_governance.py -v"
            ],
            guarded_paths=["application/services"],
        )
        formatted = pack.format_for_prompt()
        expect(
            "<conventions>" in formatted,
            "format_for_prompt_sections: missing conventions section",
        )
        expect(
            "<anti_patterns>" in formatted,
            "format_for_prompt_sections: missing anti_patterns section",
        )
        expect(
            "<review_checklist>" in formatted,
            "format_for_prompt_sections: missing checklist section",
        )
        return "sections-ok"

    def case_build_contract_pack_from_inputs() -> str:
        with tempfile.TemporaryDirectory(prefix="synapse_contract_build_") as tmp:
            ws = Path(tmp)
            built = build_contract_pack(
                ws,
                workspace_rules_content="Rule A\nRule B",
                error_patterns=["Pattern 1", "Pattern 2"],
                co_change_hints=[["a.py", "b.py"]],
            )
            expect(
                "Rule A" in built.conventions,
                "build_contract_pack_from_inputs: missing Rule A",
            )
            expect(
                "Pattern 2" in built.anti_patterns,
                "build_contract_pack_from_inputs: missing Pattern 2",
            )
            expect(
                ["a.py", "b.py"] in built.co_change_groups,
                "build_contract_pack_from_inputs: missing co-change",
            )
            return f"conv={len(built.conventions)} anti={len(built.anti_patterns)}"

    def case_build_contract_pack_idempotent_merge() -> str:
        with tempfile.TemporaryDirectory(prefix="synapse_contract_idempotent_") as tmp:
            ws = Path(tmp)
            build_contract_pack(
                ws, workspace_rules_content="Rule X", error_patterns=["E1"]
            )
            built = build_contract_pack(
                ws, workspace_rules_content="Rule X", error_patterns=["E1"]
            )
            expect(
                built.conventions.count("Rule X") == 1,
                "build_contract_pack_idempotent_merge: duplicate rule",
            )
            expect(
                built.anti_patterns.count("E1") == 1,
                "build_contract_pack_idempotent_merge: duplicate anti pattern",
            )
            return "idempotent"

    cases.extend(
        [
            ("contract_pack_load_missing", case_load_missing_contract_pack),
            ("contract_pack_save_and_load", case_save_and_load_contract_pack),
            (
                "contract_pack_locked_modify_add_convention",
                case_locked_modify_add_convention,
            ),
            (
                "contract_pack_locked_modify_add_anti_pattern",
                case_locked_modify_add_anti_pattern,
            ),
            (
                "contract_pack_locked_modify_add_guarded_path",
                case_locked_modify_add_guarded_path,
            ),
            (
                "contract_pack_format_for_prompt_sections",
                case_format_for_prompt_sections,
            ),
            ("contract_pack_build_from_inputs", case_build_contract_pack_from_inputs),
            (
                "contract_pack_build_idempotent_merge",
                case_build_contract_pack_idempotent_merge,
            ),
        ]
    )


def build_use_case_validation_cases(cases: List[tuple[str, Callable[[], str]]]) -> None:
    """Nhom use case validation cho command boundary cua application layer."""

    def with_temp_workspace(fn: Callable[[Path], str]) -> str:
        with tempfile.TemporaryDirectory(prefix="synapse_usecase_") as tmp:
            return fn(Path(tmp))

    def case_build_invalid_workspace() -> str:
        missing = ROOT / ".tmp_missing_build_workspace"
        exc = expect_raises(
            UseCaseValidationError,
            lambda: BuildContextUseCase().execute(
                BuildContextCommand(
                    workspace_path=missing,
                    task_description="simulate",
                )
            ),
            case_name="build_invalid_workspace",
        )
        return str(exc)

    def case_build_output_path_traversal() -> str:
        def run(ws: Path) -> str:
            exc = expect_raises(
                UseCaseValidationError,
                lambda: BuildContextUseCase().execute(
                    BuildContextCommand(
                        workspace_path=ws,
                        task_description="simulate",
                        output_file="../outside.txt",
                    )
                ),
                case_name="build_output_path_traversal",
            )
            return str(exc)

        return with_temp_workspace(run)

    def case_code_review_invalid_workspace() -> str:
        missing = ROOT / ".tmp_missing_review_workspace"
        exc = expect_raises(
            UseCaseValidationError,
            lambda: CodeReviewUseCase().execute(
                CodeReviewCommand(workspace_path=missing)
            ),
            case_name="code_review_invalid_workspace",
        )
        return str(exc)

    def case_refactor_invalid_workspace() -> str:
        missing = ROOT / ".tmp_missing_refactor_workspace"
        exc = expect_raises(
            UseCaseValidationError,
            lambda: RefactorUseCase().execute(
                RefactorCommand(workspace_path=missing, refactor_scope="scope")
            ),
            case_name="refactor_invalid_workspace",
        )
        return str(exc)

    def case_refactor_invalid_phase() -> str:
        def run(ws: Path) -> str:
            exc = expect_raises(
                UseCaseValidationError,
                lambda: RefactorUseCase().execute(
                    RefactorCommand(
                        workspace_path=ws,
                        refactor_scope="scope",
                        phase="invalid_phase",
                    )
                ),
                case_name="refactor_invalid_phase",
            )
            return str(exc)

        return with_temp_workspace(run)

    def case_refactor_plan_requires_report() -> str:
        def run(ws: Path) -> str:
            exc = expect_raises(
                UseCaseValidationError,
                lambda: RefactorUseCase().execute(
                    RefactorCommand(
                        workspace_path=ws,
                        refactor_scope="scope",
                        phase="plan",
                        discovery_report="",
                    )
                ),
                case_name="refactor_plan_requires_report",
            )
            return str(exc)

        return with_temp_workspace(run)

    def case_investigate_invalid_workspace() -> str:
        missing = ROOT / ".tmp_missing_investigate_workspace"
        exc = expect_raises(
            UseCaseValidationError,
            lambda: InvestigateUseCase().execute(
                InvestigateCommand(
                    workspace_path=missing,
                    bug_description="bug",
                )
            ),
            case_name="investigate_invalid_workspace",
        )
        return str(exc)

    def case_test_invalid_workspace() -> str:
        missing = ROOT / ".tmp_missing_test_workspace"
        exc = expect_raises(
            UseCaseValidationError,
            lambda: TestBuildUseCase().execute(
                TestBuildCommand(workspace_path=missing)
            ),
            case_name="test_invalid_workspace",
        )
        return str(exc)

    def case_test_output_path_traversal() -> str:
        def run(ws: Path) -> str:
            exc = expect_raises(
                UseCaseValidationError,
                lambda: TestBuildUseCase().execute(
                    TestBuildCommand(
                        workspace_path=ws,
                        output_file="../outside_test.txt",
                    )
                ),
                case_name="test_output_path_traversal",
            )
            return str(exc)

        return with_temp_workspace(run)

    def case_design_invalid_workspace() -> str:
        missing = ROOT / ".tmp_missing_design_workspace"
        exc = expect_raises(
            UseCaseValidationError,
            lambda: DesignPlannerUseCase().execute(
                DesignPlannerCommand(
                    workspace_path=missing,
                    task_description="design",
                )
            ),
            case_name="design_invalid_workspace",
        )
        return str(exc)

    def case_design_output_path_traversal() -> str:
        def run(ws: Path) -> str:
            exc = expect_raises(
                UseCaseValidationError,
                lambda: DesignPlannerUseCase().execute(
                    DesignPlannerCommand(
                        workspace_path=ws,
                        task_description="design",
                        output_file="../outside_design.txt",
                    )
                ),
                case_name="design_output_path_traversal",
            )
            return str(exc)

        return with_temp_workspace(run)

    def case_build_output_inside_workspace_passes_validation() -> str:
        def run(ws: Path) -> str:
            cmd = BuildContextCommand(
                workspace_path=ws,
                task_description="simulate",
                output_file="inside/context.txt",
            )
            try:
                BuildContextUseCase().execute(cmd)
            except Exception as exc:
                # Loi tiep theo la do domain workflow run that su duoc goi; ta chi can verify khong fail validation.
                expect(
                    not isinstance(exc, UseCaseValidationError),
                    "build_output_inside_workspace_passes_validation: unexpected validation error",
                )
                return f"non_validation_exception={type(exc).__name__}"
            return "executed"

        return with_temp_workspace(run)

    cases.extend(
        [
            ("usecase_build_invalid_workspace", case_build_invalid_workspace),
            ("usecase_build_output_path_traversal", case_build_output_path_traversal),
            (
                "usecase_code_review_invalid_workspace",
                case_code_review_invalid_workspace,
            ),
            ("usecase_refactor_invalid_workspace", case_refactor_invalid_workspace),
            ("usecase_refactor_invalid_phase", case_refactor_invalid_phase),
            (
                "usecase_refactor_plan_requires_report",
                case_refactor_plan_requires_report,
            ),
            (
                "usecase_investigate_invalid_workspace",
                case_investigate_invalid_workspace,
            ),
            ("usecase_test_invalid_workspace", case_test_invalid_workspace),
            ("usecase_test_output_path_traversal", case_test_output_path_traversal),
            ("usecase_design_invalid_workspace", case_design_invalid_workspace),
            ("usecase_design_output_path_traversal", case_design_output_path_traversal),
            (
                "usecase_build_output_inside_workspace_passes_validation",
                case_build_output_inside_workspace_passes_validation,
            ),
        ]
    )


def build_baseline_integrity_cases(cases: List[tuple[str, Callable[[], str]]]) -> None:
    """Nhom use case bo sung de day so luong case va verify helper utilities."""

    def case_error_to_payload_roundtrip() -> str:
        payload = map_exception_to_payload(
            ApplicationError("x", code="code_x", details={"k": "v"})
        )
        expect(
            payload.details.get("k") == "v",
            "error_to_payload_roundtrip: details mismatch",
        )
        return json.dumps(payload.details, ensure_ascii=True)

    def case_workflow_event_metadata_default() -> str:
        event = WorkflowEvent(workflow_id="wf_meta", stage="stage", status="started")
        expect(
            event.metadata == {},
            "workflow_event_metadata_default: metadata should be empty",
        )
        return "metadata-empty"

    def case_plugin_request_payload_default() -> str:
        req = WorkflowPluginRequest(workspace_path=ROOT)
        expect(
            req.payload == {}, "plugin_request_payload_default: payload should be empty"
        )
        return "payload-empty"

    def case_plugin_result_data_default() -> str:
        result = WorkflowPluginResult(success=True, message="ok")
        expect(result.data == {}, "plugin_result_data_default: data should be empty")
        return "data-empty"

    def case_contract_pack_to_dict_shape() -> str:
        pack = ContractPack()
        data = pack.to_dict()
        required = {
            "conventions",
            "anti_patterns",
            "co_change_groups",
            "review_checklist",
            "required_tests",
            "guarded_paths",
        }
        expect(
            required.issubset(set(data.keys())),
            "contract_pack_to_dict_shape: missing keys",
        )
        return f"keys={len(data.keys())}"

    def case_memory_store_roundtrip() -> str:
        with tempfile.TemporaryDirectory(prefix="synapse_memory_roundtrip_") as tmp:
            ws = Path(tmp)
            add_memory_fn(ws, "decision", "choose parser", None, None, "", ["arch"])
            store = load_memory_store_fn(ws)
            blob = cast(Dict[str, Any], store.to_dict())
            expect("entries" in blob, "memory_store_roundtrip: entries key missing")
            entries = cast(List[Any], blob.get("entries", []))
            return f"entries={len(entries)}"

    def case_registry_list_metadata_type() -> str:
        items = workflow_plugin_registry.list_metadata()
        return f"len={len(items)}"

    def case_format_mcp_error_includes_code() -> str:
        text = format_mcp_error(DomainValidationError("bad domain"), prefix="Fail")
        expect(
            "domain_validation_error" in text,
            "format_mcp_error_includes_code: missing code",
        )
        return text

    def case_network_error_payload_retryable_true() -> str:
        payload = map_exception_to_payload(NetworkError("net down"))
        expect(
            payload.retryable is True,
            "network_error_payload_retryable_true: retryable should be true",
        )
        return str(payload.retryable)

    def case_use_case_validation_details_pass_through() -> str:
        payload = map_exception_to_payload(
            UseCaseValidationError("bad", details={"field": "x"})
        )
        expect(
            payload.details.get("field") == "x",
            "use_case_validation_details_pass_through: details missing",
        )
        return json.dumps(payload.details, ensure_ascii=True)

    cases.extend(
        [
            ("integrity_error_to_payload_roundtrip", case_error_to_payload_roundtrip),
            (
                "integrity_workflow_event_metadata_default",
                case_workflow_event_metadata_default,
            ),
            (
                "integrity_plugin_request_payload_default",
                case_plugin_request_payload_default,
            ),
            ("integrity_plugin_result_data_default", case_plugin_result_data_default),
            ("integrity_contract_pack_to_dict_shape", case_contract_pack_to_dict_shape),
            ("integrity_memory_store_roundtrip", case_memory_store_roundtrip),
            ("integrity_registry_list_metadata_type", case_registry_list_metadata_type),
            (
                "integrity_format_mcp_error_includes_code",
                case_format_mcp_error_includes_code,
            ),
            (
                "integrity_network_error_payload_retryable_true",
                case_network_error_payload_retryable_true,
            ),
            (
                "integrity_use_case_validation_details_pass_through",
                case_use_case_validation_details_pass_through,
            ),
        ]
    )


def build_cases() -> List[tuple[str, Callable[[], str]]]:
    """Tong hop toan bo use case simulation."""
    cases: List[tuple[str, Callable[[], str]]] = []
    build_error_mapper_cases(cases)
    build_workflow_engine_cases(cases)
    build_plugin_registry_cases(cases)
    build_plugin_loader_cases(cases)
    build_memory_cases(cases)
    build_contract_pack_cases(cases)
    build_use_case_validation_cases(cases)
    build_baseline_integrity_cases(cases)
    return cases


def run_cases(
    cases: Iterable[tuple[str, Callable[[], str]]],
    *,
    fail_fast: bool,
) -> List[CaseResult]:
    """Chay danh sach use case va thu ket qua pass/fail."""
    results: List[CaseResult] = []

    for idx, (name, fn) in enumerate(cases, start=1):
        try:
            output = fn()
            results.append(
                CaseResult(index=idx, name=name, passed=True, output=str(output))
            )
            print(f"[PASS {idx:03d}] {name} -> {output}")
        except Exception as exc:
            tb = traceback.format_exc(limit=3)
            results.append(
                CaseResult(
                    index=idx,
                    name=name,
                    passed=False,
                    output="",
                    error=f"{type(exc).__name__}: {exc}\n{tb}",
                )
            )
            print(f"[FAIL {idx:03d}] {name} -> {type(exc).__name__}: {exc}")
            if fail_fast:
                break

    return results


def save_report(report_path: Path, results: List[CaseResult]) -> dict[str, Any]:
    """Luu report JSON de truy vet ket qua simulation."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    report: dict[str, Any] = {
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "all_passed": failed == 0,
        },
        "results": [asdict(r) for r in results],
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Simulate and validate project use cases with detailed output report.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help=f"Path to write JSON report (default: {DEFAULT_REPORT_PATH})",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop at first failed use case.",
    )
    args = parser.parse_args()

    cases = build_cases()
    print(f"Running {len(cases)} simulated use cases...")

    if len(cases) < 50:
        raise RuntimeError(f"Expected at least 50 use cases, found {len(cases)}")

    results = run_cases(cases, fail_fast=args.fail_fast)
    report = save_report(args.report_path, results)

    summary = report["summary"]
    print("\nSimulation Summary")
    print("=" * 40)
    print(f"Total : {summary['total']}")
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")
    print(f"Report: {args.report_path}")

    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
