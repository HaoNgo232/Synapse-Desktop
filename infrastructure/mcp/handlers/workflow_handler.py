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
                    layer=layer,
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
                matches = store.get_by_layer(layer)
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
            save_contract_pack,
        )

        try:
            pack = await asyncio.to_thread(load_contract_pack, ws)

            # Thêm convention mới
            if action == "add_convention":
                if not content:
                    return "Error: 'content' is required for 'add_convention' action."
                if content not in pack.conventions:
                    pack.conventions.append(content)
                    await asyncio.to_thread(save_contract_pack, ws, pack)
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
                if content not in pack.anti_patterns:
                    pack.anti_patterns.append(content)
                    await asyncio.to_thread(save_contract_pack, ws, pack)
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
                for p in paths:
                    if p and p not in pack.guarded_paths:
                        pack.guarded_paths.append(p)
                        added.append(p)
                if added:
                    await asyncio.to_thread(save_contract_pack, ws, pack)
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
                if content not in pack.review_checklist:
                    pack.review_checklist.append(content)
                    await asyncio.to_thread(save_contract_pack, ws, pack)
                return (
                    f"Review Item Added\n"
                    f"{'=' * 40}\n"
                    f"Content: {content}\n"
                    f"Total review items: {len(pack.review_checklist)}\n"
                    f"{'=' * 40}"
                )

            # Lấy toàn bộ contract pack dạng JSON
            if action == "get":
                pack_data = pack.to_dict()
                return (
                    f"Contract Pack\n"
                    f"{'=' * 40}\n"
                    f"{json.dumps(pack_data, indent=2, ensure_ascii=False)}"
                )

            # Format cho prompt inclusion
            if action == "format_for_prompt":
                formatted = pack.format_for_prompt()
                if not formatted:
                    return "No contract pack entries to format."
                return f"Prompt-Ready Contract Pack\n{'=' * 40}\n{formatted}"

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
        ],
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

            actual_changed = await asyncio.to_thread(_get_changed_files, ws)

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
                    logger.warning("symbol_extractor not available, drift detection will proceed without symbol analysis")
                    return symbols_map, deps_map

                try:
                    from domain.codemap.relationship_extractor import extract_relationships
                except ImportError:
                    logger.warning("relationship_extractor not available, drift detection will proceed without dependency analysis")
                    extract_relationships = None  # type: ignore[assignment]

                for rel_path in file_list:
                    full_path = root / rel_path
                    if not full_path.is_file():
                        continue
                    try:
                        content = full_path.read_text(encoding="utf-8", errors="replace")
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
                _extract_file_info, ws, all_files
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
                f"Design Drift Report",
                f"{'=' * 40}",
                report.summary,
            ]

            if report.out_of_scope_files:
                result_lines.append(f"\nOut-of-scope files:")
                for f in report.out_of_scope_files:
                    result_lines.append(f"  - {f}")

            if report.new_dependencies:
                result_lines.append(f"\nNew dependencies:")
                for d in report.new_dependencies:
                    result_lines.append(f"  - {d}")

            if report.public_api_changes:
                result_lines.append(f"\nPublic API changes:")
                for c in report.public_api_changes:
                    result_lines.append(f"  {c}")

            if report.coupling_warnings:
                result_lines.append(f"\nCoupling warnings:")
                for w in report.coupling_warnings:
                    result_lines.append(f"  ⚠ {w}")

            result_lines.append(f"\n{'=' * 40}")
            return "\n".join(result_lines)

        except Exception as e:
            logger.error("detect_design_drift error: %s", e)
            return f"Error: {e}"
