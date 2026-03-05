"""
Workflow Handler - Xu ly cac workflow tools cho AI agent handoff.

Bao gom: rp_build, rp_review, rp_refactor, rp_investigate, rp_test.
"""

import asyncio
from typing import List, Optional

from mcp.server.fastmcp import Context

from mcp_server.core.workspace_manager import WorkspaceManager
from mcp_server.core.constants import SAFE_GIT_REF, logger


def register_tools(mcp_instance) -> None:
    """Dang ky workflow tools voi MCP server.

    Args:
        mcp_instance: FastMCP server instance.
    """

    # Tool rp_build chuan bi context toi uu cho AI agent implement task
    @mcp_instance.tool()
    async def rp_build(
        task_description: str,
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
        file_paths: Optional[List[str]] = None,
        max_tokens: int = 100_000,
        include_codemap: bool = True,
        include_git_changes: bool = False,
        output_file: Optional[str] = None,
    ) -> str:
        """Prepare optimized context for an AI agent to implement a task.

        Args:
            task_description: Description of what needs to be implemented.
            file_paths: Optional list of known relevant files.
            max_tokens: Maximum token budget (default: 100,000).
            include_codemap: Include code structure signatures (default: True).
            include_git_changes: Include recent git changes (default: False).
            output_file: Optional path to write the prompt.
            workspace_path: Absolute path to the workspace root directory.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        if output_file:
            out_path = (ws / output_file).resolve()
            if not out_path.is_relative_to(ws):
                return "Error: output_file path traversal detected."

        from core.workflows.context_builder import (
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

    # Tool rp_review review code voi full context xung quanh
    @mcp_instance.tool()
    async def rp_review(
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
        review_focus: str = "",
        include_tests: bool = True,
        include_callers: bool = True,
        max_tokens: int = 120_000,
        base_ref: Optional[str] = None,
    ) -> str:
        """Deep code review with full surrounding context.

        Args:
            review_focus: Optional focus area ("security", "performance").
            include_tests: Pull related test files (default: True).
            include_callers: Pull files that call changed functions (default: True).
            max_tokens: Maximum token budget (default: 120,000).
            base_ref: Optional git ref to diff against.
            workspace_path: Absolute path to the workspace root.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        if base_ref and not SAFE_GIT_REF.match(base_ref):
            return f"Error: Invalid git reference: {base_ref}"

        from core.workflows.code_reviewer import run_code_review

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

    # Tool rp_refactor phan tich va lap ke hoach refactoring 2 pha
    @mcp_instance.tool()
    async def rp_refactor(
        refactor_scope: str,
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
        phase: str = "discover",
        file_paths: Optional[List[str]] = None,
        discovery_report: str = "",
        max_tokens: int = 80_000,
    ) -> str:
        """Two-pass refactoring: analyze first, plan second.

        Args:
            refactor_scope: Description of what to refactor.
            phase: "discover" or "plan" (default: "discover").
            file_paths: Optional list of files in scope.
            discovery_report: Output from phase="discover" (required for phase="plan").
            max_tokens: Maximum token budget (default: 80,000).
            workspace_path: Absolute path to the workspace root.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        if phase not in ("discover", "plan"):
            return "Error: phase must be 'discover' or 'plan'."

        if phase == "plan" and not discovery_report.strip():
            return "Error: discovery_report required for phase='plan'."

        from core.workflows.refactor_workflow import (
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

    # Tool rp_investigate tu dong dieu tra bug bang cach trace execution path
    @mcp_instance.tool()
    async def rp_investigate(
        bug_description: str,
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
        error_trace: str = "",
        entry_files: Optional[List[str]] = None,
        max_depth: int = 4,
        max_tokens: int = 100_000,
    ) -> str:
        """Trace execution path to find root cause of a bug.

        Args:
            bug_description: Description of the bug.
            error_trace: Optional error trace/stacktrace.
            entry_files: Optional starting files.
            max_depth: Maximum trace depth (default: 4).
            max_tokens: Maximum token budget (default: 100,000).
            workspace_path: Absolute path to the workspace root.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        from core.workflows.bug_investigator import (
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

    # Tool rp_test phan tich code, tim test coverage gaps,
    # va chuan bi context toi uu cho AI viet tests chat luong cao
    @mcp_instance.tool()
    async def rp_test(
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
        task_description: str = "Write tests for the specified files",
        file_paths: Optional[List[str]] = None,
        max_tokens: int = 100_000,
        test_framework: Optional[str] = None,
        include_existing_tests: bool = True,
        output_file: Optional[str] = None,
    ) -> str:
        """Analyze code, find coverage gaps, and prepare context for writing tests.

        Args:
            task_description: Description of what tests to write.
            file_paths: Optional list of source files to generate tests for.
            max_tokens: Maximum token budget (default: 100,000).
            test_framework: Framework ("pytest", "jest", "vitest").
            include_existing_tests: Include existing test files (default: True).
            output_file: Optional path to write the prompt.
            workspace_path: Absolute path to the workspace root directory.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        if output_file:
            out_path = (ws / output_file).resolve()
            if not out_path.is_relative_to(ws):
                return "Error: output_file path traversal detected."

        from core.workflows.test_builder import run_test_builder

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
