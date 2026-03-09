"""
Workflow Handler - Xu ly cac workflow tools cho AI agent handoff.

Bao gom: rp_build, rp_review, rp_refactor, rp_investigate, rp_test, rp_design.
"""

import asyncio
from typing import Annotated, List, Optional

from mcp.server.fastmcp import Context
from pydantic import Field

from infrastructure.mcp.core.workspace_manager import WorkspaceManager
from infrastructure.mcp.core.constants import SAFE_GIT_REF, logger


def register_tools(mcp_instance) -> None:
    """Dang ky workflow tools voi MCP server."""

    @mcp_instance.tool()
    async def rp_build(
        task_description: Annotated[
            str,
            Field(
                description="Description of what needs to be implemented (e.g., 'Add rate limiting to login endpoint')."
            ),
        ],
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted."
            ),
        ] = None,
        ctx: Optional[Context] = None,
        file_paths: Annotated[
            Optional[List[str]],
            Field(
                description="Optional list of known relevant relative file paths to seed the context."
            ),
        ] = None,
        max_tokens: Annotated[
            int,
            Field(
                description="Maximum token budget for the generated context. Default: 100,000."
            ),
        ] = 100_000,
        include_codemap: Annotated[
            bool,
            Field(
                description="Include AST code structure signatures in the context. Default: True."
            ),
        ] = True,
        include_git_changes: Annotated[
            bool,
            Field(
                description="Include recent git changes in the context. Default: False."
            ),
        ] = False,
        output_file: Annotated[
            Optional[str],
            Field(
                description="Relative path to write the prompt file (e.g., 'context.xml'). Returns inline if omitted."
            ),
        ] = None,
    ) -> str:
        """Prepare optimized implementation context for an AI agent to build a feature.

        Auto-detects relevant files, traces dependencies, optimizes token budget,
        and packages everything into a structured prompt. Use this as the starting point
        for any new feature implementation or cross-agent delegation.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        if output_file:
            out_path = (ws / output_file).resolve()
            if not out_path.is_relative_to(ws):
                return "Error: output_file path traversal detected."

        from domain.workflow.context_builder import (
            run_context_builder,
        )

        try:
            result = await asyncio.to_thread(
                run_context_builder,
                workspace_path=str(ws),
                task_description=task_description,
                file_paths=file_paths,
                max_tokens=max_tokens,
                include_codemap=include_codemap,
                include_git_changes=include_git_changes,
                output_file=output_file,
            )  # type: ignore

            summary = (
                f"Context Builder Complete\n"
                f"{'=' * 40}\n"
                f"Files included: {result.files_included}\n"
                f"Files sliced: {result.files_sliced}\n"
                f"Files smart-only: {result.files_smart_only}\n"
                f"Total tokens: {result.total_tokens:,}\n"
                f"Scope: {result.scope_summary}\n"
            )

            if result.optimizations:
                summary += f"Optimizations: {', '.join(result.optimizations)}\n"

            if output_file:
                summary += f"\nPrompt written to: {output_file}\n"
            else:
                summary += f"\n{'=' * 40}\n{result.prompt}"

            return summary

        except Exception as e:
            logger.error("rp_build error: %s", e)
            return f"Error: {e}"

    @mcp_instance.tool()
    async def rp_review(
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted."
            ),
        ] = None,
        ctx: Optional[Context] = None,
        review_focus: Annotated[
            str,
            Field(
                description='Optional focus area for the review (e.g., "security", "performance", "breaking-changes"). Reviews all aspects if empty.'
            ),
        ] = "",
        include_tests: Annotated[
            bool,
            Field(
                description="Pull related test files into the review context. Default: True."
            ),
        ] = True,
        include_callers: Annotated[
            bool,
            Field(
                description="Pull files that call changed functions to assess blast radius. Default: True."
            ),
        ] = True,
        max_tokens: Annotated[
            int,
            Field(
                description="Maximum token budget for the review context. Default: 120,000."
            ),
        ] = 120_000,
        base_ref: Annotated[
            Optional[str],
            Field(
                description='Git ref to diff against (e.g., "main", "HEAD~5", a commit hash). Uses HEAD if omitted.'
            ),
        ] = None,
    ) -> str:
        """Deep code review with full surrounding context (imports, callers, tests).

        Automatically finds changed files via git diff, gathers their callers and tests,
        and packages everything for comprehensive review analysis.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        if base_ref and not SAFE_GIT_REF.match(base_ref):
            return f"Error: Invalid git reference: {base_ref}"

        from domain.workflow.code_reviewer import run_code_review

        try:
            result = await asyncio.to_thread(
                run_code_review,
                workspace_path=str(ws),
                review_focus=review_focus,
                include_tests=include_tests,
                include_callers=include_callers,
                max_tokens=max_tokens,
                base_ref=base_ref,
            )  # type: ignore

            summary = (
                f"Code Review Context Ready\n"
                f"{'=' * 40}\n"
                f"Changed files: {result.files_changed}\n"
                f"Context files: {result.files_context}\n"
                f"Total tokens: {result.total_tokens:,}\n"
                f"\n{'=' * 40}\n{result.prompt}"
            )
            return summary

        except Exception as e:
            logger.error("rp_review error: %s", e)
            return f"Error: {e}"

    @mcp_instance.tool()
    async def rp_refactor(
        refactor_scope: Annotated[
            str,
            Field(
                description="Description of what to refactor (e.g., 'Extract validation logic from UserService into separate ValidationService')."
            ),
        ],
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted."
            ),
        ] = None,
        ctx: Optional[Context] = None,
        phase: Annotated[
            str,
            Field(
                description='Refactoring phase: "discover" (analyze dependencies and risks) or "plan" (generate refactoring plan from discovery report). Default: "discover".'
            ),
        ] = "discover",
        file_paths: Annotated[
            Optional[List[str]],
            Field(
                description="Optional list of relative file paths in the refactoring scope."
            ),
        ] = None,
        discovery_report: Annotated[
            str,
            Field(
                description='Output from phase="discover" (required when phase="plan"). Pass the full discovery report text here.'
            ),
        ] = "",
        max_tokens: Annotated[
            int,
            Field(description="Maximum token budget. Default: 80,000."),
        ] = 80_000,
    ) -> str:
        """Two-pass safe refactoring: analyze first (discover), then plan second.

        Phase "discover": Maps all dependencies, callers, tests, and coupling points for the target code.
        Phase "plan": Takes the discovery report and generates a step-by-step refactoring plan with rollback strategy.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        if phase not in ("discover", "plan"):
            return "Error: phase must be 'discover' or 'plan'."

        if phase == "plan" and not discovery_report.strip():
            return "Error: discovery_report required for phase='plan'."

        from domain.workflow.refactor_workflow import (
            run_refactor_discovery,
            run_refactor_planning,
        )

        try:
            if phase == "discover":
                result = await asyncio.to_thread(
                    run_refactor_discovery,
                    workspace_path=str(ws),
                    refactor_scope=refactor_scope,
                    file_paths=file_paths,
                    max_tokens=max_tokens,
                )  # type: ignore
                return (
                    f"Refactor Discovery Complete\n"
                    f"{'=' * 40}\n"
                    f"Scope files: {len(result.scope_files)}\n"
                    f"Total tokens: {result.total_tokens:,}\n"
                    f"\n{'=' * 40}\n{result.prompt}"
                )
            else:
                result = await asyncio.to_thread(
                    run_refactor_planning,
                    workspace_path=str(ws),
                    refactor_scope=refactor_scope,
                    discovery_report_text=discovery_report,
                    file_paths=file_paths,
                    max_tokens=max_tokens,
                )  # type: ignore
                return (
                    f"Refactor Plan Ready\n"
                    f"{'=' * 40}\n"
                    f"Files to modify: {len(result.files_to_modify)}\n"
                    f"Total tokens: {result.total_tokens:,}\n"
                    f"\n{'=' * 40}\n{result.prompt}"
                )

        except Exception as e:
            logger.error("rp_refactor error: %s", e)
            return f"Error: {e}"

    @mcp_instance.tool()
    async def rp_investigate(
        bug_description: Annotated[
            str,
            Field(
                description="Description of the bug or unexpected behavior (e.g., 'Login fails with 500 error after password reset')."
            ),
        ],
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted."
            ),
        ] = None,
        ctx: Optional[Context] = None,
        error_trace: Annotated[
            str,
            Field(
                description="Optional error traceback or stack trace to help locate the bug origin."
            ),
        ] = "",
        entry_files: Annotated[
            Optional[List[str]],
            Field(
                description="Optional starting file paths for the investigation (e.g., files mentioned in the stack trace)."
            ),
        ] = None,
        max_depth: Annotated[
            int,
            Field(description="Maximum call chain trace depth. Default: 4."),
        ] = 4,
        max_tokens: Annotated[
            int,
            Field(description="Maximum token budget. Default: 100,000."),
        ] = 100_000,
    ) -> str:
        """Trace execution path through the codebase to find the root cause of a bug.

        Follows call chains from error points, gathers surrounding context (callers, imports, tests),
        and packages everything for root cause analysis.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        from domain.workflow.bug_investigator import (
            run_bug_investigation,
        )

        try:
            result = await asyncio.to_thread(
                run_bug_investigation,
                workspace_path=str(ws),
                bug_description=bug_description,
                error_trace=error_trace,
                entry_files=entry_files,
                max_depth=max_depth,
                max_tokens=max_tokens,
            )  # type: ignore

            summary = (
                f"Bug Investigation Complete\n"
                f"{'=' * 40}\n"
                f"Files investigated: {result.files_investigated}\n"
                f"Trace depth: {result.max_depth_reached}\n"
                f"Total tokens: {result.total_tokens:,}\n"
                f"\n{'=' * 40}\n{result.prompt}"
            )
            return summary

        except Exception as e:
            logger.error("rp_investigate error: %s", e)
            return f"Error: {e}"

    @mcp_instance.tool()
    async def rp_test(
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted."
            ),
        ] = None,
        ctx: Optional[Context] = None,
        task_description: Annotated[
            str,
            Field(
                description="Description of what tests to write (e.g., 'Write unit tests for the authentication module')."
            ),
        ] = "Write tests for the specified files",
        file_paths: Annotated[
            Optional[List[str]],
            Field(
                description="Optional list of source file paths to generate tests for (e.g., ['src/auth/service.py'])."
            ),
        ] = None,
        max_tokens: Annotated[
            int,
            Field(description="Maximum token budget. Default: 100,000."),
        ] = 100_000,
        test_framework: Annotated[
            Optional[str],
            Field(
                description='Test framework to use (e.g., "pytest", "jest", "vitest"). Auto-detected if omitted.'
            ),
        ] = None,
        include_existing_tests: Annotated[
            bool,
            Field(
                description="Include existing test files in the context for pattern matching. Default: True."
            ),
        ] = True,
        output_file: Annotated[
            Optional[str],
            Field(
                description="Relative path to write the prompt file. Returns inline if omitted."
            ),
        ] = None,
    ) -> str:
        """Analyze code, find test coverage gaps, and prepare context for writing high-quality tests.

        Compares source symbols with existing test symbols to identify untested functions,
        suggests test file names, and packages source + existing tests for AI test generation.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        if output_file:
            out_path = (ws / output_file).resolve()
            if not out_path.is_relative_to(ws):
                return "Error: output_file path traversal detected."

        from domain.workflow.test_builder import run_test_builder

        try:
            result = await asyncio.to_thread(
                run_test_builder,
                workspace_path=str(ws),
                task_description=task_description,
                file_paths=file_paths,
                max_tokens=max_tokens,
                test_framework=test_framework,
                include_existing_tests=include_existing_tests,
                output_file=output_file,
            )  # type: ignore

            summary = (
                f"Test Builder Complete\n"
                f"{'=' * 40}\n"
                f"Files included: {result.files_included}\n"
                f"Files sliced: {result.files_sliced}\n"
                f"Files smart-only: {result.files_smart_only}\n"
                f"Total tokens: {result.total_tokens:,}\n"
                f"Scope: {result.scope_summary}\n"
                f"Coverage: {result.coverage_summary}\n"
                f"Untested symbols: {result.untested_symbols}\n"
            )

            if result.suggested_test_files:
                summary += (
                    f"Suggested test files: {', '.join(result.suggested_test_files)}\n"
                )

            if result.optimizations:
                summary += f"Optimizations: {', '.join(result.optimizations)}\n"

            if output_file:
                summary += f"\nPrompt written to: {output_file}\n"
            else:
                summary += f"\n{'=' * 40}\n{result.prompt}"

            return summary

        except Exception as e:
            logger.error("rp_test error: %s", e)
            return f"Error: {e}"

    @mcp_instance.tool()
    async def rp_design(
        task_description: Annotated[
            str,
            Field(
                description="Description of the architectural change or feature to plan (e.g., 'Migrate authentication from session-based to JWT tokens')."
            ),
        ],
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted."
            ),
        ] = None,
        ctx: Optional[Context] = None,
        file_paths: Annotated[
            Optional[List[str]],
            Field(
                description="Optional list of known relevant relative file paths to seed the context."
            ),
        ] = None,
        max_tokens: Annotated[
            int,
            Field(
                description="Maximum token budget for the generated context. Default: 100,000."
            ),
        ] = 100_000,
        include_tests: Annotated[
            bool,
            Field(description="Include test files in the design scope. Default: True."),
        ] = True,
        output_file: Annotated[
            Optional[str],
            Field(
                description="Relative path to write the prompt file (e.g., 'design.xml'). Returns inline if omitted."
            ),
        ] = None,
    ) -> str:
        """Produce an architectural design and implementation plan for a feature or change.

        Detects scope, traces dependencies, identifies impacted modules and risk areas,
        and packages everything into a structured prompt that instructs an AI to produce
        a full design plan covering architecture goals, API contracts, migration needs,
        test strategy, rollout plan, and a do-not-touch list.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        if output_file:
            out_path = (ws / output_file).resolve()
            if not out_path.is_relative_to(ws):
                return "Error: output_file path traversal detected."

        from domain.workflow.design_planner import run_design_planner

        try:
            result = await asyncio.to_thread(
                run_design_planner,
                workspace_path=str(ws),
                task_description=task_description,
                file_paths=file_paths,
                max_tokens=max_tokens,
                include_tests=include_tests,
                output_file=output_file,
            )  # type: ignore

            summary = (
                f"Design Planner Complete\n"
                f"{'=' * 40}\n"
                f"Files included: {result.files_included}\n"
                f"Files sliced: {result.files_sliced}\n"
                f"Files smart-only: {result.files_smart_only}\n"
                f"Total tokens: {result.total_tokens:,}\n"
                f"Scope: {result.scope_summary}\n"
            )

            if result.impacted_modules:
                summary += f"Impacted modules: {', '.join(result.impacted_modules)}\n"

            if result.risk_areas:
                summary += f"Risk areas: {len(result.risk_areas)}\n"

            if result.optimizations:
                summary += f"Optimizations: {', '.join(result.optimizations)}\n"

            if output_file:
                summary += f"\nPrompt written to: {output_file}\n"
            else:
                summary += f"\n{'=' * 40}\n{result.prompt}"

            return summary

        except Exception as e:
            logger.error("rp_design error: %s", e)
            return f"Error: {e}"
