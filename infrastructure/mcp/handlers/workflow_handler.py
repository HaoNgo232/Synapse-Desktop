"""
Workflow Handler - Xu ly cac workflow tools cho AI agent handoff.

Bao gom: rp_build, rp_review, rp_refactor, rp_investigate, rp_test, rp_design, manage_memory, get_contract_pack, detect_design_drift.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Annotated, Dict, List, Optional

from mcp.server.fastmcp import Context
from pydantic import Field

from infrastructure.mcp.core.workspace_manager import WorkspaceManager
from infrastructure.mcp.core.constants import GIT_TIMEOUT, SAFE_GIT_REF, logger


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

    @mcp_instance.tool()
    async def manage_memory(
        action: Annotated[
            str,
            Field(
                description=(
                    "Action to perform: 'add' to store a new memory entry, "
                    "'get' to retrieve all entries formatted, "
                    "'get_by_file' to retrieve entries linked to a specific file, "
                    "'get_by_layer' to retrieve entries for a specific layer, "
                    "'format_for_prompt' to get prompt-ready memory text."
                ),
            ),
        ],
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted.",
            ),
        ] = None,
        ctx: Optional[Context] = None,
        layer: Annotated[
            Optional[str],
            Field(
                description=(
                    "Memory layer: 'action' (what was changed), "
                    "'decision' (why approach A over B), "
                    "'constraint' (invariants/rules/domain assumptions). "
                    "Required for 'add' and 'get_by_layer' actions."
                ),
            ),
        ] = None,
        content: Annotated[
            Optional[str],
            Field(
                description="Content of the memory entry. Required for 'add' action.",
            ),
        ] = None,
        linked_files: Annotated[
            Optional[List[str]],
            Field(
                description="List of file paths related to this memory entry.",
            ),
        ] = None,
        linked_symbols: Annotated[
            Optional[List[str]],
            Field(
                description="List of code symbols (functions, classes) related to this memory entry.",
            ),
        ] = None,
        workflow: Annotated[
            Optional[str],
            Field(
                description="Workflow that produced this memory (e.g., 'rp_build', 'rp_review').",
            ),
        ] = None,
        tags: Annotated[
            Optional[List[str]],
            Field(
                description="Tags for categorizing this memory entry.",
            ),
        ] = None,
        file_path: Annotated[
            Optional[str],
            Field(
                description="File path to filter memories by. Used with 'get_by_file' action.",
            ),
        ] = None,
    ) -> str:
        """Manage the Decision Memory v2 system with three layers: action, decision, and constraint.

        Use this tool to record and retrieve project memory across three layers:
        - **action**: Track what was changed (files modified, features added).
        - **decision**: Record why a particular approach was chosen over alternatives.
        - **constraint**: Store invariants, rules, and domain assumptions that must be respected.
        """
        valid_actions = (
            "add",
            "get",
            "get_by_file",
            "get_by_layer",
            "format_for_prompt",
        )
        if action not in valid_actions:
            return f"Error: Invalid action '{action}'. Must be one of: {', '.join(valid_actions)}"

        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        from domain.memory.memory_service import (
            add_memory,
            load_memory_store,
        )

        try:
            if action == "add":
                if not content:
                    return "Error: 'content' is required for 'add' action."
                valid_layers = ("action", "decision", "constraint")
                if not layer or layer not in valid_layers:
                    return f"Error: 'layer' must be one of: {', '.join(valid_layers)}"

                await asyncio.to_thread(
                    add_memory,
                    workspace_root=ws,
                    layer=layer,  # type: ignore[arg-type]
                    content=content,
                    linked_files=linked_files,
                    linked_symbols=linked_symbols,
                    workflow=workflow or "",
                    tags=tags,
                )
                return (
                    f"Memory Added\n"
                    f"{'=' * 40}\n"
                    f"Layer: {layer}\n"
                    f"Content: {content}\n"
                    f"{'=' * 40}"
                )

            store = await asyncio.to_thread(load_memory_store, ws)

            if action == "get":
                if not store.entries:
                    return "No memory entries found."
                entries_data = [e.to_dict() for e in store.entries]
                return (
                    f"Memory Store ({len(store.entries)} entries)\n"
                    f"{'=' * 40}\n"
                    f"{json.dumps(entries_data, indent=2, ensure_ascii=False)}"
                )

            if action == "get_by_file":
                if not file_path:
                    return "Error: 'file_path' is required for 'get_by_file' action."
                matches = store.get_by_file(file_path)
                if not matches:
                    return f"No memory entries linked to '{file_path}'."
                entries_data = [e.to_dict() for e in matches]
                return (
                    f"Memory entries for '{file_path}' ({len(matches)} entries)\n"
                    f"{'=' * 40}\n"
                    f"{json.dumps(entries_data, indent=2, ensure_ascii=False)}"
                )

            if action == "get_by_layer":
                valid_layers = ("action", "decision", "constraint")
                if not layer or layer not in valid_layers:
                    return f"Error: 'layer' must be one of: {', '.join(valid_layers)}"
                matches = store.get_by_layer(layer)  # type: ignore[arg-type]
                if not matches:
                    return f"No memory entries for layer '{layer}'."
                entries_data = [e.to_dict() for e in matches]
                return (
                    f"Memory entries for layer '{layer}' ({len(matches)} entries)\n"
                    f"{'=' * 40}\n"
                    f"{json.dumps(entries_data, indent=2, ensure_ascii=False)}"
                )

            if action == "format_for_prompt":
                formatted = store.format_for_prompt()
                if not formatted:
                    return "No memory entries to format."
                return f"Prompt-Ready Memory\n{'=' * 40}\n{formatted}"

            return f"Error: Unhandled action '{action}'."

        except Exception as e:
            logger.error("manage_memory error: %s", e)
            return f"Error: {e}"

    @mcp_instance.tool()
    async def get_contract_pack(
        action: Annotated[
            str,
            Field(
                description=(
                    "Action to perform: "
                    "'get' to retrieve the full contract pack as JSON, "
                    "'add_convention' to add a convention rule, "
                    "'add_anti_pattern' to add an anti-pattern from past errors, "
                    "'add_guarded_path' to add a guarded/watched path, "
                    "'add_review_item' to add a review checklist item, "
                    "'format_for_prompt' to get prompt-ready contract text."
                ),
            ),
        ],
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted.",
            ),
        ] = None,
        ctx: Optional[Context] = None,
        content: Annotated[
            Optional[str],
            Field(
                description=(
                    "Content to add. Required for 'add_convention', "
                    "'add_anti_pattern', and 'add_review_item' actions."
                ),
            ),
        ] = None,
        paths: Annotated[
            Optional[List[str]],
            Field(
                description="List of file/folder paths. Used with 'add_guarded_path' action.",
            ),
        ] = None,
    ) -> str:
        """Manage the Contract Pack system for workspace-level AI agent compliance.

        Contract packs combine conventions, anti-patterns from past errors,
        co-change groups, review checklists, required tests, and guarded paths
        into a single contract that the AI agent must follow.
        """
        valid_actions = (
            "get",
            "add_convention",
            "add_anti_pattern",
            "add_guarded_path",
            "add_review_item",
            "format_for_prompt",
        )
        if action not in valid_actions:
            return (
                f"Error: Invalid action '{action}'. "
                f"Must be one of: {', '.join(valid_actions)}"
            )

        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        from domain.contracts.contract_pack import (
            load_contract_pack,
            locked_modify_contract_pack,
        )

        try:
            # Lấy toàn bộ contract pack dạng JSON
            if action == "get":
                pack = await asyncio.to_thread(load_contract_pack, ws)
                pack_data = pack.to_dict()
                return (
                    f"Contract Pack\n"
                    f"{'=' * 40}\n"
                    f"{json.dumps(pack_data, indent=2, ensure_ascii=False)}"
                )

            # Format cho prompt inclusion
            if action == "format_for_prompt":
                pack = await asyncio.to_thread(load_contract_pack, ws)
                formatted = pack.format_for_prompt()
                if not formatted:
                    return "No contract pack entries to format."
                return f"Prompt-Ready Contract Pack\n{'=' * 40}\n{formatted}"

            # Thêm convention mới
            if action == "add_convention":
                if not content:
                    return "Error: 'content' is required for 'add_convention' action."

                def mod_conv(p):
                    if content not in p.conventions:
                        p.conventions.append(content)
                    return p

                pack = await asyncio.to_thread(
                    locked_modify_contract_pack, ws, mod_conv
                )
                return (
                    f"Convention Added\n"
                    f"{'=' * 40}\n"
                    f"Content: {content}\n"
                    f"Total conventions: {len(pack.conventions)}\n"
                    f"{'=' * 40}"
                )

            # Thêm anti-pattern từ lỗi trước đó
            if action == "add_anti_pattern":
                if not content:
                    return "Error: 'content' is required for 'add_anti_pattern' action."

                def mod_anti(p):
                    if content not in p.anti_patterns:
                        p.anti_patterns.append(content)
                    return p

                pack = await asyncio.to_thread(
                    locked_modify_contract_pack, ws, mod_anti
                )
                return (
                    f"Anti-Pattern Added\n"
                    f"{'=' * 40}\n"
                    f"Content: {content}\n"
                    f"Total anti-patterns: {len(pack.anti_patterns)}\n"
                    f"{'=' * 40}"
                )

            # Thêm guarded path cần cẩn thận khi sửa
            if action == "add_guarded_path":
                if not paths:
                    return "Error: 'paths' is required for 'add_guarded_path' action."

                added = []

                def mod_guard(p):
                    safe_paths = paths if paths else []
                    for path in safe_paths:
                        if path and path not in p.guarded_paths:
                            p.guarded_paths.append(path)
                            added.append(path)
                    return p

                pack = await asyncio.to_thread(
                    locked_modify_contract_pack, ws, mod_guard
                )
                return (
                    f"Guarded Paths Updated\n"
                    f"{'=' * 40}\n"
                    f"Added: {', '.join(added) if added else '(none, already existed)'}\n"
                    f"Total guarded paths: {len(pack.guarded_paths)}\n"
                    f"{'=' * 40}"
                )

            # Thêm review checklist item
            if action == "add_review_item":
                if not content:
                    return "Error: 'content' is required for 'add_review_item' action."

                def mod_rev(p):
                    if content not in p.review_checklist:
                        p.review_checklist.append(content)
                    return p

                pack = await asyncio.to_thread(locked_modify_contract_pack, ws, mod_rev)
                return (
                    f"Review Item Added\n"
                    f"{'=' * 40}\n"
                    f"Content: {content}\n"
                    f"Total review items: {len(pack.review_checklist)}\n"
                    f"{'=' * 40}"
                )

            return f"Error: Unhandled action '{action}'."

        except Exception as e:
            logger.error("get_contract_pack error: %s", e)
            return f"Error: {e}"

    @mcp_instance.tool()
    async def detect_design_drift(
        planned_files: Annotated[
            List[str],
            Field(
                description="List of relative file paths that were planned to be changed.",
            ),
        ] = [],
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted.",
            ),
        ] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Detect design drift by comparing planned changes vs actual git changes.

        Auto-detects changed files from git diff (staged + unstaged), extracts
        current symbols and dependencies, then reports out-of-scope files,
        new dependency edges, public API changes, and coupling warnings.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        try:
            # Lấy danh sách files thực tế thay đổi từ git (unstaged + staged)
            def _get_changed_files(ws_path: str) -> List[str]:
                unstaged = subprocess.run(
                    ["git", "diff", "--name-only"],
                    cwd=ws_path,
                    capture_output=True,
                    text=True,
                    timeout=GIT_TIMEOUT,
                    check=False,
                )
                staged = subprocess.run(
                    ["git", "diff", "--cached", "--name-only"],
                    cwd=ws_path,
                    capture_output=True,
                    text=True,
                    timeout=GIT_TIMEOUT,
                    check=False,
                )
                files: set[str] = set()
                for output in [unstaged.stdout, staged.stdout]:
                    for line in output.strip().split("\n"):
                        if line.strip():
                            files.add(line.strip())
                return sorted(files)

            actual_changed = await asyncio.to_thread(_get_changed_files, str(ws))

            if not actual_changed and not planned_files:
                return "No planned files and no git changes detected."

            # Extract symbols và dependencies cho các files thay đổi
            def _extract_file_info(
                ws_path: str, file_list: List[str]
            ) -> tuple[Dict[str, List[str]], Dict[str, List[str]]]:
                symbols_map: Dict[str, List[str]] = {}
                deps_map: Dict[str, List[str]] = {}
                root = Path(ws_path)

                try:
                    from domain.codemap.symbol_extractor import extract_symbols
                except ImportError:
                    logger.warning(
                        "symbol_extractor not available, drift detection will proceed without symbol analysis"
                    )
                    return symbols_map, deps_map

                try:
                    from domain.codemap.relationship_extractor import (
                        extract_relationships,
                    )
                except ImportError:
                    logger.warning(
                        "relationship_extractor not available, drift detection will proceed without dependency analysis"
                    )
                    extract_relationships = None  # type: ignore[assignment]

                for rel_path in file_list:
                    full_path = root / rel_path
                    if not full_path.is_file():
                        continue
                    try:
                        content = full_path.read_text(
                            encoding="utf-8", errors="replace"
                        )
                    except OSError:
                        continue

                    # Extract symbols
                    try:
                        syms = extract_symbols(rel_path, content)
                        symbols_map[rel_path] = [s.name for s in syms]
                    except Exception:
                        pass

                    # Extract relationships -> dependencies
                    if extract_relationships is not None:
                        try:
                            rels = extract_relationships(rel_path, content)
                            deps_map[rel_path] = [
                                r.target for r in rels if r.target != rel_path
                            ]
                        except Exception:
                            pass

                return symbols_map, deps_map

            all_files = sorted(set(planned_files) | set(actual_changed))
            post_symbols, post_deps = await asyncio.to_thread(
                _extract_file_info, str(ws), all_files
            )

            # Gọi detect_drift
            from domain.drift.drift_detector import detect_drift

            report = detect_drift(
                workspace_root=Path(ws),
                planned_files=planned_files,
                actual_changed_files=actual_changed,
                pre_edit_symbols=None,
                post_edit_symbols=post_symbols,
                pre_edit_deps=None,
                post_edit_deps=post_deps,
            )

            # Format kết quả
            result_lines = [
                "Design Drift Report",
                f"{'=' * 40}",
                report.summary,
            ]

            if report.out_of_scope_files:
                result_lines.append("\nOut-of-scope files:")
                for f in report.out_of_scope_files:
                    result_lines.append(f"  - {f}")

            if report.new_dependencies:
                result_lines.append("\nNew dependencies:")
                for d in report.new_dependencies:
                    result_lines.append(f"  - {d}")

            if report.public_api_changes:
                result_lines.append("\nPublic API changes:")
                for c in report.public_api_changes:
                    result_lines.append(f"  {c}")

            if report.coupling_warnings:
                result_lines.append("\nCoupling warnings:")
                for w in report.coupling_warnings:
                    result_lines.append(f"  ⚠ {w}")

            result_lines.append(f"\n{'=' * 40}")
            return "\n".join(result_lines)

        except Exception as e:
            logger.error("detect_design_drift error: %s", e)
            return f"Error: {e}"

    # ================================================================
    # simulate_patch - Dry-run OPX patch before applying
    # ================================================================

    @mcp_instance.tool()
    async def simulate_patch(
        opx_content: Annotated[
            str,
            Field(
                description="OPX content to simulate (the patch instructions)."
            ),
        ],
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted."
            ),
        ] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Simulate an OPX patch without actually applying changes (dry-run).

        Parses the OPX content, validates each file action against the current
        workspace state, and reports which actions would succeed or fail.
        Returns a summary with match/mismatch details, cascade failures, and
        blast radius estimate. Use this before apply to catch errors early.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        try:
            from domain.prompt.opx_parser import parse_opx_response
            from infrastructure.filesystem.file_actions import apply_file_actions

            parse_result = parse_opx_response(opx_content)
            file_actions = parse_result.file_actions if parse_result else []
            if not file_actions:
                return "No file actions found in OPX content."

            results = await asyncio.to_thread(
                apply_file_actions,
                file_actions,
                workspace_roots=[ws],
                dry_run=True,
            )

            passed = sum(1 for r in results if r.success)
            failed = sum(1 for r in results if not r.success)

            lines = [
                "Patch Simulation Report",
                f"{'=' * 40}",
                f"Total actions: {len(results)} | Pass: {passed} | Fail: {failed}",
                "",
            ]

            affected_files = set()
            for r in results:
                icon = "✅" if r.success else "❌"
                lines.append(f"  {icon} [{r.action}] {r.path}")
                if r.message:
                    lines.append(f"     {r.message}")
                if r.path:
                    affected_files.add(r.path)

            lines.append(f"\nAffected files: {len(affected_files)}")
            lines.append(f"Blast radius: {', '.join(sorted(affected_files)[:10])}")

            return "\n".join(lines)

        except Exception as e:
            logger.error("simulate_patch error: %s", e)
            return f"Error: {e}"

    # ================================================================
    # manage_execution_contract - Create/read/update execution contracts
    # ================================================================

    @mcp_instance.tool()
    async def manage_execution_contract(
        action: Annotated[
            str,
            Field(
                description='Action: "create" (new contract), "get" (read current), '
                '"update" (modify fields), "activate" (set status=active), '
                '"complete" (set status=completed), "format_for_prompt" (get prompt text).'
            ),
        ],
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted."
            ),
        ] = None,
        ctx: Optional[Context] = None,
        task: Annotated[
            Optional[str],
            Field(description="Task description for 'create' action."),
        ] = None,
        scope_files: Annotated[
            Optional[List[str]],
            Field(description="Files in scope for 'create'/'update'."),
        ] = None,
        guarded_paths: Annotated[
            Optional[List[str]],
            Field(description="Protected paths for 'create'/'update'."),
        ] = None,
        planned_interfaces: Annotated[
            Optional[List[str]],
            Field(description="Planned interface changes for 'create'/'update'."),
        ] = None,
        assumptions: Annotated[
            Optional[List[str]],
            Field(description="Assumptions to record for 'create'/'update'."),
        ] = None,
        required_tests: Annotated[
            Optional[List[str]],
            Field(description="Required tests for 'create'/'update'."),
        ] = None,
        risks: Annotated[
            Optional[List[str]],
            Field(description="Known risks for 'create'/'update'."),
        ] = None,
        success_criteria: Annotated[
            Optional[List[str]],
            Field(description="Success criteria for 'create'/'update'."),
        ] = None,
    ) -> str:
        """Manage execution contracts — the backbone artifact linking planning, coding, review, and testing.

        An execution contract captures task scope, guarded paths, assumptions,
        required tests, risks, and success criteria. Planner creates it,
        coder reads it, reviewer checks against it, drift detector compares with it.
        """
        allowed_actions = {
            "create", "get", "update", "activate", "complete", "format_for_prompt",
        }
        if action not in allowed_actions:
            return f"Error: Invalid action '{action}'. Allowed: {sorted(allowed_actions)}"

        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        try:
            from domain.contracts.execution_contract import (
                ExecutionContract,
                load_execution_contract,
                save_execution_contract,
            )

            if action == "create":
                if not task:
                    return "Error: 'task' is required for 'create' action."
                contract = ExecutionContract(
                    task=task,
                    scope_files=scope_files or [],
                    guarded_paths=guarded_paths or [],
                    planned_interfaces=planned_interfaces or [],
                    assumptions=assumptions or [],
                    required_tests=required_tests or [],
                    risks=risks or [],
                    success_criteria=success_criteria or [],
                    status="draft",
                )
                await asyncio.to_thread(save_execution_contract, ws, contract)
                return json.dumps(contract.to_dict(), indent=2, ensure_ascii=False)

            elif action == "get":
                contract = await asyncio.to_thread(load_execution_contract, ws)
                if contract is None:
                    return "No execution contract found."
                return json.dumps(contract.to_dict(), indent=2, ensure_ascii=False)

            elif action == "update":
                contract = await asyncio.to_thread(load_execution_contract, ws)
                if contract is None:
                    return "Error: No existing contract to update. Use 'create' first."
                if scope_files is not None:
                    contract.scope_files = scope_files
                if guarded_paths is not None:
                    contract.guarded_paths = guarded_paths
                if planned_interfaces is not None:
                    contract.planned_interfaces = planned_interfaces
                if assumptions is not None:
                    contract.assumptions = assumptions
                if required_tests is not None:
                    contract.required_tests = required_tests
                if risks is not None:
                    contract.risks = risks
                if success_criteria is not None:
                    contract.success_criteria = success_criteria
                await asyncio.to_thread(save_execution_contract, ws, contract)
                return json.dumps(contract.to_dict(), indent=2, ensure_ascii=False)

            elif action in ("activate", "complete"):
                contract = await asyncio.to_thread(load_execution_contract, ws)
                if contract is None:
                    return "Error: No contract found."
                contract.status = "active" if action == "activate" else "completed"
                await asyncio.to_thread(save_execution_contract, ws, contract)
                return f"Contract status set to '{contract.status}'."

            elif action == "format_for_prompt":
                contract = await asyncio.to_thread(load_execution_contract, ws)
                if contract is None:
                    return "No execution contract found."
                return contract.format_for_prompt()

            return "Error: Unhandled action."

        except Exception as e:
            logger.error("manage_execution_contract error: %s", e)
            return f"Error: {e}"

    # ================================================================
    # verify_assumptions - Check agent assumptions against real codebase
    # ================================================================

    @mcp_instance.tool()
    async def verify_assumptions(
        assumptions: Annotated[
            List[str],
            Field(
                description='List of assumptions to verify, e.g. '
                '["\'AuthService\' only used by login.py", '
                '"\'validate_token\' has test coverage", '
                '"renaming \'helper\' impacts 3 files"].'
            ),
        ],
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted."
            ),
        ] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Verify agent assumptions against the actual codebase.

        Checks assumptions like 'X only used by Y', 'not used externally',
        'impacts N files', 'has test coverage'. Returns pass/fail/uncertain
        verdict with evidence files and confidence scores.

        This solves the biggest weakness of IDE agents: confident but wrong assumptions.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        try:
            from domain.workflow.assumption_verifier import (
                verify_assumptions as _verify,
            )

            report = await asyncio.to_thread(_verify, ws, assumptions)
            return report.format_summary()

        except Exception as e:
            logger.error("verify_assumptions error: %s", e)
            return f"Error: {e}"

    # ================================================================
    # build_handoff_bundle - Role-specific context for multi-agent workflows
    # ================================================================

    @mcp_instance.tool()
    async def build_handoff_bundle(
        task_description: Annotated[
            str,
            Field(description="Task description for the handoff."),
        ],
        target_role: Annotated[
            str,
            Field(
                description='Target agent role: "implementer", "reviewer", '
                '"tester", "fixer". Each role gets optimized context.'
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
            Field(description="Relevant file paths."),
        ] = None,
        max_tokens: Annotated[
            int,
            Field(description="Maximum token budget. Default: 80000."),
        ] = 80_000,
    ) -> str:
        """Build a role-specific handoff bundle for multi-agent workflows.

        Creates context packages optimized for specific agent roles:
        - implementer: full file contents + dependencies + contract
        - reviewer: diff context + contract + test gaps + risks
        - tester: test files + coverage gaps + scope
        - fixer: error context + related files + memory

        This goes beyond generic 'build prompt' by tailoring content per role.
        """
        allowed_roles = {"implementer", "reviewer", "tester", "fixer"}
        if target_role not in allowed_roles:
            return f"Error: Invalid role '{target_role}'. Allowed: {sorted(allowed_roles)}"

        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        try:
            from domain.workflow.context_builder import run_context_builder
            from domain.contracts.execution_contract import load_execution_contract

            # Build base context
            result = await asyncio.to_thread(
                run_context_builder,
                workspace_path=str(ws),
                task_description=task_description,
                file_paths=file_paths,
                max_tokens=max_tokens,
                include_codemap=True,
                include_git_changes=(target_role in ("reviewer", "fixer")),
            )

            # Load contract if available
            contract = await asyncio.to_thread(load_execution_contract, ws)
            contract_section = ""
            if contract:
                contract_section = f"\n{contract.format_for_prompt()}\n"

            # Role-specific instructions
            role_instructions: Dict[str, str] = {
                "implementer": (
                    "You are the IMPLEMENTER. Follow the execution contract strictly. "
                    "Implement changes only within scope_files. "
                    "Do NOT modify guarded_paths without explicit approval. "
                    "Verify all assumptions before coding."
                ),
                "reviewer": (
                    "You are the REVIEWER. Compare the actual changes against the "
                    "execution contract. Check: scope adherence, assumption validity, "
                    "test coverage for required_tests, risk mitigation. "
                    "Flag any drift from the contract."
                ),
                "tester": (
                    "You are the TESTER. Write tests for all required_tests in the "
                    "execution contract. Verify success_criteria are testable. "
                    "Check test coverage gaps for scope_files."
                ),
                "fixer": (
                    "You are the FIXER. Analyze the error context, identify root cause, "
                    "and propose minimal fixes within scope_files. "
                    "Check execution contract for constraints and guarded_paths."
                ),
            }

            bundle = {
                "role": target_role,
                "task": task_description,
                "instructions": role_instructions.get(target_role, ""),
                "context_tokens": len(result) // 4,  # rough estimate
                "has_contract": contract is not None,
            }

            output = f"<handoff_bundle role=\"{target_role}\">\n"
            output += f"<role_instructions>\n{role_instructions.get(target_role, '')}\n</role_instructions>\n"
            if contract_section:
                output += contract_section
            output += f"\n{result}\n"
            output += "</handoff_bundle>"

            return output

        except Exception as e:
            logger.error("build_handoff_bundle error: %s", e)
            return f"Error: {e}"

    # ================================================================
    # manage_watchpoints - Architectural guardrails
    # ================================================================

    @mcp_instance.tool()
    async def manage_watchpoints(
        action: Annotated[
            str,
            Field(
                description='Action: "add" (add watchpoint), "list" (show all), '
                '"check" (check files against watchpoints), "remove" (remove watchpoint).'
            ),
        ],
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted."
            ),
        ] = None,
        ctx: Optional[Context] = None,
        paths: Annotated[
            Optional[List[str]],
            Field(
                description="Paths to add/remove as watchpoints, or files to check against watchpoints."
            ),
        ] = None,
        reason: Annotated[
            Optional[str],
            Field(description="Reason for adding the watchpoint."),
        ] = None,
    ) -> str:
        """Manage architectural watchpoints — protected areas of the codebase.

        Watchpoints guard critical paths (public APIs, config files, high fan-in symbols).
        When an agent's patch touches a watchpoint:
        - Extra review is required
        - Warning is raised
        - Priority increases in blast radius

        This creates an 'architecture guard' layer that most IDE agents lack.
        """
        allowed_actions = {"add", "list", "check", "remove"}
        if action not in allowed_actions:
            return f"Error: Invalid action '{action}'. Allowed: {sorted(allowed_actions)}"

        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        try:
            from domain.contracts.contract_pack import (
                load_contract_pack,
                locked_modify_contract_pack,
            )

            if action == "add":
                if not paths:
                    return "Error: 'paths' required for 'add' action."

                def _add_watchpoints(pack):
                    for p in paths:
                        entry = p if not reason else f"{p} — {reason}"
                        if entry not in pack.guarded_paths:
                            pack.guarded_paths.append(entry)
                    return pack

                await asyncio.to_thread(locked_modify_contract_pack, ws, _add_watchpoints)
                return f"Added {len(paths)} watchpoint(s). Use 'list' to see all."

            elif action == "list":
                pack = await asyncio.to_thread(load_contract_pack, ws)
                if not pack.guarded_paths:
                    return "No watchpoints configured."
                lines = ["Architectural Watchpoints:", f"{'=' * 40}"]
                for i, wp in enumerate(pack.guarded_paths, 1):
                    lines.append(f"  {i}. {wp}")
                return "\n".join(lines)

            elif action == "check":
                if not paths:
                    return "Error: 'paths' required for 'check' action."
                pack = await asyncio.to_thread(load_contract_pack, ws)
                if not pack.guarded_paths:
                    return "No watchpoints configured. All paths clear."

                # Extract just the path portion from watchpoints (before " — reason")
                guarded = set()
                for wp in pack.guarded_paths:
                    guarded.add(wp.split(" — ")[0].strip())

                violations = []
                for p in paths:
                    for g in guarded:
                        if p.startswith(g) or g.startswith(p) or p == g:
                            violations.append(f"⚠ {p} touches watchpoint: {g}")
                            break

                if not violations:
                    return f"All {len(paths)} path(s) clear — no watchpoint violations."
                lines = [
                    f"Watchpoint Violations: {len(violations)}",
                    f"{'=' * 40}",
                ]
                lines.extend(violations)
                lines.append("\n⚠ Extra review required for these changes.")
                return "\n".join(lines)

            elif action == "remove":
                if not paths:
                    return "Error: 'paths' required for 'remove' action."

                def _remove_watchpoints(pack):
                    pack.guarded_paths = [
                        wp for wp in pack.guarded_paths
                        if wp.split(" — ")[0].strip() not in paths
                    ]
                    return pack

                await asyncio.to_thread(locked_modify_contract_pack, ws, _remove_watchpoints)
                return f"Removed watchpoint(s) matching: {', '.join(paths)}"

            return "Error: Unhandled action."

        except Exception as e:
            logger.error("manage_watchpoints error: %s", e)
            return f"Error: {e}"

    # ================================================================
    # manage_plan_dag - Machine-readable task graph
    # ================================================================

    @mcp_instance.tool()
    async def manage_plan_dag(
        action: Annotated[
            str,
            Field(
                description='Action: "create" (new DAG), "get" (read current), '
                '"add_node" (add task node), "add_edge" (add dependency), '
                '"update_status" (change node status), "get_ready" (nodes ready to execute), '
                '"format_summary" (human-readable summary).'
            ),
        ],
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted."
            ),
        ] = None,
        ctx: Optional[Context] = None,
        task: Annotated[
            Optional[str],
            Field(description="Task description for 'create'."),
        ] = None,
        node_id: Annotated[
            Optional[str],
            Field(description="Node ID for add_node/update_status."),
        ] = None,
        node_type: Annotated[
            Optional[str],
            Field(description="Node type: 'decision', 'change', 'test', 'review', 'config'."),
        ] = None,
        node_title: Annotated[
            Optional[str],
            Field(description="Node title for add_node."),
        ] = None,
        node_file: Annotated[
            Optional[str],
            Field(description="File path associated with the node."),
        ] = None,
        status: Annotated[
            Optional[str],
            Field(description="New status for update_status: 'pending', 'in_progress', 'completed', 'skipped'."),
        ] = None,
        edge_from: Annotated[
            Optional[str],
            Field(description="Source node ID for add_edge."),
        ] = None,
        edge_to: Annotated[
            Optional[str],
            Field(description="Target node ID for add_edge."),
        ] = None,
        edge_kind: Annotated[
            Optional[str],
            Field(description="Edge kind: 'implements', 'must_verify', 'depends_on', 'blocks'."),
        ] = None,
    ) -> str:
        """Manage Plan DAG — a machine-readable task graph for agent coordination.

        Planner creates the graph, coder claims nodes, reviewer checks coverage,
        test agent verifies must_verify edges. Supports dependency tracking so
        agents know which tasks are ready to execute.
        """
        allowed_actions = {
            "create", "get", "add_node", "add_edge",
            "update_status", "get_ready", "format_summary",
        }
        if action not in allowed_actions:
            return f"Error: Invalid action '{action}'. Allowed: {sorted(allowed_actions)}"

        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        try:
            from domain.workflow.plan_dag import (
                PlanDAG,
                PlanNode,
                PlanEdge,
                load_plan_dag,
                save_plan_dag,
            )

            if action == "create":
                dag = PlanDAG(task=task or "")
                await asyncio.to_thread(save_plan_dag, ws, dag)
                return json.dumps(dag.to_dict(), indent=2, ensure_ascii=False)

            elif action == "get":
                dag = await asyncio.to_thread(load_plan_dag, ws)
                if dag is None:
                    return "No plan DAG found."
                return json.dumps(dag.to_dict(), indent=2, ensure_ascii=False)

            elif action == "add_node":
                if not node_id or not node_title:
                    return "Error: 'node_id' and 'node_title' required."
                dag = await asyncio.to_thread(load_plan_dag, ws)
                if dag is None:
                    dag = PlanDAG(task=task or "")
                node = PlanNode(
                    id=node_id,
                    type=node_type or "change",
                    title=node_title,
                    file=node_file or "",
                )
                dag.add_node(node)
                await asyncio.to_thread(save_plan_dag, ws, dag)
                return json.dumps(node.to_dict(), indent=2, ensure_ascii=False)

            elif action == "add_edge":
                if not edge_from or not edge_to:
                    return "Error: 'edge_from' and 'edge_to' required."
                dag = await asyncio.to_thread(load_plan_dag, ws)
                if dag is None:
                    return "Error: No plan DAG found. Use 'create' first."
                edge = PlanEdge(
                    source=edge_from,
                    target=edge_to,
                    kind=edge_kind or "depends_on",
                )
                dag.add_edge(edge)
                await asyncio.to_thread(save_plan_dag, ws, dag)
                return json.dumps(edge.to_dict(), indent=2, ensure_ascii=False)

            elif action == "update_status":
                if not node_id or not status:
                    return "Error: 'node_id' and 'status' required."
                dag = await asyncio.to_thread(load_plan_dag, ws)
                if dag is None:
                    return "Error: No plan DAG found."
                success = dag.update_node_status(node_id, status)
                if not success:
                    return f"Error: Node '{node_id}' not found."
                await asyncio.to_thread(save_plan_dag, ws, dag)
                return f"Node '{node_id}' status updated to '{status}'."

            elif action == "get_ready":
                dag = await asyncio.to_thread(load_plan_dag, ws)
                if dag is None:
                    return "No plan DAG found."
                ready = dag.get_ready_nodes()
                if not ready:
                    return "No nodes ready to execute (all completed or blocked)."
                lines = [f"Ready nodes ({len(ready)}):"]
                for n in ready:
                    lines.append(f"  - {n.id}: {n.title} [{n.type}]")
                return "\n".join(lines)

            elif action == "format_summary":
                dag = await asyncio.to_thread(load_plan_dag, ws)
                if dag is None:
                    return "No plan DAG found."
                return dag.format_summary()

            return "Error: Unhandled action."

        except Exception as e:
            logger.error("manage_plan_dag error: %s", e)
            return f"Error: {e}"
