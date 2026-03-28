"""
Workflow Use Cases - Application layer orchestration cho rp_* workflows.

Layer nay la command/use-case boundary:
- Validate input command
- Dieu phoi execution qua WorkflowEngine
- Map exception thanh ApplicationError
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

from application.errors import UseCaseValidationError, WorkflowExecutionError
from application.use_cases.workflow_engine import (
    CallableWorkflowStep,
    WorkflowContext,
    WorkflowEngine,
)
from domain.errors import DomainError


def _ensure_workspace_dir(workspace_path: Path) -> None:
    """Validate workspace path tai use case boundary."""
    if not workspace_path.is_dir():
        raise UseCaseValidationError(
            f"'{workspace_path}' is not a valid directory",
            details={"workspace_path": str(workspace_path)},
        )


def _ensure_output_inside_workspace(
    workspace_path: Path,
    output_file: Optional[str],
) -> None:
    """Chong path traversal cho output_file o use case boundary."""
    if not output_file:
        return
    out_path = (workspace_path / output_file).resolve()
    if not out_path.is_relative_to(workspace_path):
        raise UseCaseValidationError(
            "output_file path traversal detected",
            details={"output_file": output_file},
        )


@dataclass(frozen=True)
class BuildContextCommand:
    workspace_path: Path
    task_description: str
    file_paths: Optional[List[str]] = None
    max_tokens: int = 100_000
    include_codemap: bool = True
    include_git_changes: bool = False
    output_file: Optional[str] = None


@dataclass(frozen=True)
class CodeReviewCommand:
    workspace_path: Path
    review_focus: str = ""
    include_tests: bool = True
    include_callers: bool = True
    max_tokens: int = 120_000
    base_ref: Optional[str] = None


@dataclass(frozen=True)
class RefactorCommand:
    workspace_path: Path
    refactor_scope: str
    phase: str = "discover"
    file_paths: Optional[List[str]] = None
    discovery_report: str = ""
    max_tokens: int = 80_000


@dataclass(frozen=True)
class InvestigateCommand:
    workspace_path: Path
    bug_description: str
    error_trace: str = ""
    entry_files: Optional[List[str]] = None
    max_depth: int = 4
    max_tokens: int = 100_000


@dataclass(frozen=True)
class TestBuildCommand:
    workspace_path: Path
    task_description: str = "Write tests for the specified files"
    file_paths: Optional[List[str]] = None
    max_tokens: int = 100_000
    test_framework: Optional[str] = None
    include_existing_tests: bool = True
    output_file: Optional[str] = None


@dataclass(frozen=True)
class DesignPlannerCommand:
    workspace_path: Path
    task_description: str
    file_paths: Optional[List[str]] = None
    max_tokens: int = 100_000
    include_tests: bool = True
    output_file: Optional[str] = None


class BuildContextUseCase:
    """Use case cho rp_build."""

    def __init__(self, engine: Optional[WorkflowEngine] = None) -> None:
        self._engine = engine or WorkflowEngine()

    def execute(self, command: BuildContextCommand) -> Any:
        _ensure_workspace_dir(command.workspace_path)
        _ensure_output_inside_workspace(command.workspace_path, command.output_file)

        from domain.workflow.context_builder import run_context_builder

        ctx = WorkflowContext(
            workflow_id="rp_build",
            workspace_path=command.workspace_path,
            payload={"task_description": command.task_description},
        )

        def _run(context: WorkflowContext) -> None:
            context.result = run_context_builder(
                workspace_path=str(command.workspace_path),
                task_description=command.task_description,
                file_paths=command.file_paths,
                max_tokens=command.max_tokens,
                include_codemap=command.include_codemap,
                include_git_changes=command.include_git_changes,
                output_file=command.output_file,
            )

        try:
            return self._engine.run(
                ctx,
                [
                    CallableWorkflowStep(
                        name="build_context",
                        handler=_run,
                        description="Build optimized context package",
                    )
                ],
            ).result
        except DomainError:
            raise
        except Exception as exc:
            raise WorkflowExecutionError(
                "Failed to execute rp_build",
                details={"workflow": "rp_build"},
                cause=exc,
            ) from exc


class CodeReviewUseCase:
    """Use case cho rp_review."""

    def __init__(self, engine: Optional[WorkflowEngine] = None) -> None:
        self._engine = engine or WorkflowEngine()

    def execute(self, command: CodeReviewCommand) -> Any:
        _ensure_workspace_dir(command.workspace_path)

        from domain.workflow.code_reviewer import run_code_review

        ctx = WorkflowContext(
            workflow_id="rp_review",
            workspace_path=command.workspace_path,
            payload={"review_focus": command.review_focus},
        )

        def _run(context: WorkflowContext) -> None:
            context.result = run_code_review(
                workspace_path=str(command.workspace_path),
                review_focus=command.review_focus,
                include_tests=command.include_tests,
                include_callers=command.include_callers,
                max_tokens=command.max_tokens,
                base_ref=command.base_ref,
            )

        try:
            return self._engine.run(
                ctx,
                [
                    CallableWorkflowStep(
                        name="code_review",
                        handler=_run,
                        description="Build deep code review context",
                    )
                ],
            ).result
        except DomainError:
            raise
        except Exception as exc:
            raise WorkflowExecutionError(
                "Failed to execute rp_review",
                details={"workflow": "rp_review"},
                cause=exc,
            ) from exc


class RefactorUseCase:
    """Use case cho rp_refactor (discover/plan)."""

    def __init__(self, engine: Optional[WorkflowEngine] = None) -> None:
        self._engine = engine or WorkflowEngine()

    def execute(self, command: RefactorCommand) -> Any:
        _ensure_workspace_dir(command.workspace_path)

        if command.phase not in ("discover", "plan"):
            raise UseCaseValidationError(
                "phase must be 'discover' or 'plan'",
                details={"phase": command.phase},
            )
        if command.phase == "plan" and not command.discovery_report.strip():
            raise UseCaseValidationError(
                "discovery_report required for phase='plan'",
                details={"phase": command.phase},
            )

        from domain.workflow.refactor_workflow import (
            run_refactor_discovery,
            run_refactor_planning,
        )

        ctx = WorkflowContext(
            workflow_id="rp_refactor",
            workspace_path=command.workspace_path,
            payload={"phase": command.phase},
        )

        def _run(context: WorkflowContext) -> None:
            if command.phase == "discover":
                context.result = run_refactor_discovery(
                    workspace_path=str(command.workspace_path),
                    refactor_scope=command.refactor_scope,
                    file_paths=command.file_paths,
                    max_tokens=command.max_tokens,
                )
            else:
                context.result = run_refactor_planning(
                    workspace_path=str(command.workspace_path),
                    refactor_scope=command.refactor_scope,
                    discovery_report_text=command.discovery_report,
                    file_paths=command.file_paths,
                    max_tokens=command.max_tokens,
                )

        try:
            return self._engine.run(
                ctx,
                [
                    CallableWorkflowStep(
                        name="refactor_flow",
                        handler=_run,
                        description="Run safe two-pass refactor flow",
                    )
                ],
            ).result
        except DomainError:
            raise
        except Exception as exc:
            raise WorkflowExecutionError(
                "Failed to execute rp_refactor",
                details={"workflow": "rp_refactor", "phase": command.phase},
                cause=exc,
            ) from exc


class InvestigateUseCase:
    """Use case cho rp_investigate."""

    def __init__(self, engine: Optional[WorkflowEngine] = None) -> None:
        self._engine = engine or WorkflowEngine()

    def execute(self, command: InvestigateCommand) -> Any:
        _ensure_workspace_dir(command.workspace_path)

        from domain.workflow.bug_investigator import run_bug_investigation

        ctx = WorkflowContext(
            workflow_id="rp_investigate",
            workspace_path=command.workspace_path,
            payload={"bug_description": command.bug_description},
        )

        def _run(context: WorkflowContext) -> None:
            context.result = run_bug_investigation(
                workspace_path=str(command.workspace_path),
                bug_description=command.bug_description,
                error_trace=command.error_trace,
                entry_files=command.entry_files,
                max_depth=command.max_depth,
                max_tokens=command.max_tokens,
            )

        try:
            return self._engine.run(
                ctx,
                [
                    CallableWorkflowStep(
                        name="investigate_bug",
                        handler=_run,
                        description="Trace root cause investigation graph",
                    )
                ],
            ).result
        except DomainError:
            raise
        except Exception as exc:
            raise WorkflowExecutionError(
                "Failed to execute rp_investigate",
                details={"workflow": "rp_investigate"},
                cause=exc,
            ) from exc


class TestBuildUseCase:
    """Use case cho rp_test."""

    def __init__(self, engine: Optional[WorkflowEngine] = None) -> None:
        self._engine = engine or WorkflowEngine()

    def execute(self, command: TestBuildCommand) -> Any:
        _ensure_workspace_dir(command.workspace_path)
        _ensure_output_inside_workspace(command.workspace_path, command.output_file)

        from domain.workflow.test_builder import run_test_builder

        ctx = WorkflowContext(
            workflow_id="rp_test",
            workspace_path=command.workspace_path,
            payload={"task_description": command.task_description},
        )

        def _run(context: WorkflowContext) -> None:
            context.result = run_test_builder(
                workspace_path=str(command.workspace_path),
                task_description=command.task_description,
                file_paths=command.file_paths,
                max_tokens=command.max_tokens,
                test_framework=command.test_framework,
                include_existing_tests=command.include_existing_tests,
                output_file=command.output_file,
            )

        try:
            return self._engine.run(
                ctx,
                [
                    CallableWorkflowStep(
                        name="build_test_context",
                        handler=_run,
                        description="Analyze coverage and build test context",
                    )
                ],
            ).result
        except DomainError:
            raise
        except Exception as exc:
            raise WorkflowExecutionError(
                "Failed to execute rp_test",
                details={"workflow": "rp_test"},
                cause=exc,
            ) from exc


class DesignPlannerUseCase:
    """Use case cho rp_design."""

    def __init__(self, engine: Optional[WorkflowEngine] = None) -> None:
        self._engine = engine or WorkflowEngine()

    def execute(self, command: DesignPlannerCommand) -> Any:
        _ensure_workspace_dir(command.workspace_path)
        _ensure_output_inside_workspace(command.workspace_path, command.output_file)

        from domain.workflow.design_planner import run_design_planner

        ctx = WorkflowContext(
            workflow_id="rp_design",
            workspace_path=command.workspace_path,
            payload={"task_description": command.task_description},
        )

        def _run(context: WorkflowContext) -> None:
            context.result = run_design_planner(
                workspace_path=str(command.workspace_path),
                task_description=command.task_description,
                file_paths=command.file_paths,
                max_tokens=command.max_tokens,
                include_tests=command.include_tests,
                output_file=command.output_file,
            )

        try:
            return self._engine.run(
                ctx,
                [
                    CallableWorkflowStep(
                        name="design_plan",
                        handler=_run,
                        description="Build architectural design plan context",
                    )
                ],
            ).result
        except DomainError:
            raise
        except Exception as exc:
            raise WorkflowExecutionError(
                "Failed to execute rp_design",
                details={"workflow": "rp_design"},
                cause=exc,
            ) from exc
