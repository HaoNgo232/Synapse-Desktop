"""
Context Handler - Xu ly cac tool lien quan den context building.

Bao gom: get_codemap, batch_codemap, build_prompt.
"""

from pathlib import Path
from typing import List, Optional

from mcp.server.fastmcp import Context

from mcp_server.core.workspace_manager import WorkspaceManager
from mcp_server.core.constants import logger
from mcp_server.core.profile_resolver import resolve_profile_params


def register_tools(mcp_instance) -> None:
    """Dang ky context tools voi MCP server.

    Args:
        mcp_instance: FastMCP server instance.
    """

    # Ham get_codemap dung Tree-sitter de trich xuat skeleton cua code (signatures, class defs)
    @mcp_instance.tool()
    async def get_codemap(
        file_paths: List[str],
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Extract code structure (signatures, classes, imports) from files using Tree-sitter.

        Args:
            file_paths: List of relative file paths to analyze.
            workspace_path: Absolute path to the workspace root directory.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        # Chuyen relative paths thanh absolute paths
        abs_paths: set[str] = set()
        for rp in file_paths:
            fp = (ws / rp).resolve()
            if not fp.is_relative_to(ws):
                return f"Error: Path traversal detected for: {rp}"
            if fp.is_file():
                abs_paths.add(str(fp))
            else:
                return f"Error: File not found: {rp}"

        if not abs_paths:
            return "Error: No valid files provided."

        try:
            from core.prompt_generator import generate_smart_context

            result = generate_smart_context(
                selected_paths=abs_paths,
                include_relationships=True,
                workspace_root=ws,
                use_relative_paths=True,
            )
            if not result or not result.strip():
                return "No code structure could be extracted from the provided files."
            return result

        except Exception as e:
            logger.error("get_codemap error: %s", e)
            return f"Error generating codemap: {e}"

    # Ham batch_codemap trich xuat codemap cho tat ca file trong thu muc
    @mcp_instance.tool()
    async def batch_codemap(
        directory: str = ".",
        extensions: Optional[List[str]] = None,
        max_files: int = 50,
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Extract code structure (signatures, classes, imports) for ALL files in a directory.

        Args:
            directory: Relative directory to scan (default: ".").
            extensions: Optional file extensions to include (e.g., [".py"]).
            max_files: Maximum files to process (default: 50).
            workspace_path: Absolute path to the workspace root directory.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        target_dir = (ws / directory).resolve()
        if not target_dir.is_relative_to(ws):
            return "Error: Path traversal detected."
        if not target_dir.is_dir():
            return f"Error: Directory not found: {directory}"

        try:
            from services.workspace_index import collect_files_from_disk
            from core.smart_context import is_supported

            all_files = collect_files_from_disk(target_dir, workspace_path=ws)

            # Filter by extension
            if extensions:
                ext_set = {
                    e.lower() if e.startswith(".") else f".{e.lower()}"
                    for e in extensions
                }
                all_files = [f for f in all_files if Path(f).suffix.lower() in ext_set]
            else:
                # Only include files with supported Smart Context extensions
                all_files = [
                    f for f in all_files if is_supported(Path(f).suffix.lstrip("."))
                ]

            # Sort by path for deterministic output
            all_files = sorted(all_files)[:max_files]

            if not all_files:
                return f"No supported code files found in {directory}/"

            # Convert to absolute path strings for generate_smart_context
            abs_paths = set(all_files)

            from core.prompt_generator import generate_smart_context

            result = generate_smart_context(
                selected_paths=abs_paths,
                include_relationships=False,  # Keep it focused on structure
                workspace_root=ws,
                use_relative_paths=True,
            )

            if not result or not result.strip():
                return f"No code structure could be extracted from {len(all_files)} files in {directory}/"

            header = (
                f"Codemap for {directory}/ ({len(all_files)} files"
                f"{f', filtered to {extensions}' if extensions else ''})\n"
                f"{'=' * 60}\n"
            )
            return header + result

        except Exception as e:
            logger.error("batch_codemap error: %s", e)
            return f"Error: {e}"

    # Ham build_prompt ket hop noi dung file, cau truc thu muc va git diffs de tao prompt cho AI
    @mcp_instance.tool()
    async def build_prompt(
        file_paths: List[str],
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
        instructions: str = "",
        output_format: str = "xml",
        output_file: Optional[str] = None,
        include_git_changes: bool = False,
        profile: Optional[str] = None,
        metadata_format: str = "text",
        use_selection: bool = False,
        auto_expand_dependencies: bool = False,
        dependency_depth: int = 1,
        max_tokens: Optional[int] = None,
        codemap_paths: Optional[List[str]] = None,
    ) -> str:
        """Build an AI-ready prompt combining files, directory tree, rules, and git diffs.

        Args:
            file_paths: List of relative file paths to include.
            instructions: Optional user instructions.
            output_format: Output format ("xml", "json", "plain", "smart").
            output_file: Optional path to write output.
            include_git_changes: Include recent git diffs and logs.
            profile: Preset config ("review", "bugfix", "refactor", "doc").
            metadata_format: Response format for output_file ("text", "json").
            use_selection: Merge current selection from .synapse/selection.json.
            auto_expand_dependencies: Include files imported by selected files.
            dependency_depth: Depth for dependency resolution (1-3).
            max_tokens: Maximum token count for prompt trimming.
            codemap_paths: Relative file paths for AST signatures only (no bodies).
            workspace_path: Absolute path to the workspace root directory.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        # ================================================================
        # Phase 0: Validate metadata_format
        # ================================================================
        if metadata_format not in ("text", "json"):
            return "Error: metadata_format must be 'text' or 'json'."

        # ================================================================
        # Phase 1: Resolve profile params (explicit > profile > default)
        # ================================================================
        try:
            (
                output_format,
                include_git_changes,
                instructions,
                max_tokens,
                auto_expand_dependencies,
                resolved_profile_name,
            ) = resolve_profile_params(
                profile_name=profile,
                output_format=output_format,
                include_git_changes=include_git_changes,
                instructions=instructions,
                max_tokens=max_tokens,
                auto_expand_dependencies=auto_expand_dependencies,
            )
        except ValueError as e:
            return f"Error: {e}"

        # ================================================================
        # Phase 2: Resolve file list (file_paths + selection merge)
        # ================================================================
        abs_paths: list[Path] = []
        for rp in file_paths:
            fp = (ws / rp).resolve()
            if not fp.is_relative_to(ws):
                return f"Error: Path traversal detected for: {rp}"
            if not fp.is_file():
                return f"Error: File not found: {rp}"
            abs_paths.append(fp)

        # Merge selection files khi use_selection=True
        if use_selection:
            import json as _json

            session_file = ws / ".synapse" / "selection.json"
            if not session_file.exists():
                if not abs_paths:
                    return "Error: use_selection=True but no selection found and no file_paths provided."
            else:
                try:
                    data = _json.loads(session_file.read_text(encoding="utf-8"))
                    sel_files = data.get("selected_files", [])
                    existing_set = {str(p) for p in abs_paths}
                    for rp in sel_files:
                        fp = (ws / rp).resolve()
                        if fp.is_file() and str(fp) not in existing_set:
                            abs_paths.append(fp)
                            existing_set.add(str(fp))
                except Exception as e:
                    logger.warning("Failed to read selection: %s", e)

        if not abs_paths:
            return "Error: No valid files provided."

        # ================================================================
        # Phase 2.5: Resolve codemap_paths tu user input
        # ================================================================
        resolved_codemap_set: set[str] = set()
        if codemap_paths:
            for rp in codemap_paths:
                fp = (ws / rp).resolve()
                if not fp.is_relative_to(ws):
                    return f"Error: Path traversal detected for codemap_path: {rp}"
                if fp.is_file():
                    resolved_codemap_set.add(str(fp))
                else:
                    # Khong return error, chi warning vi codemap file co the
                    # khong ton tai (user chi dinh sai)
                    logger.warning("Codemap path not found, skipping: %s", rp)

        # ================================================================
        # Phase 3: Expand dependencies khi auto_expand_dependencies=True
        # ================================================================
        dependency_files: list[Path] = []
        dependency_graph: dict[str, list[str]] | None = None

        if auto_expand_dependencies:
            # Cap dependency_depth o 1-3
            dependency_depth = max(1, min(3, dependency_depth))
            try:
                from core.dependency_resolver import DependencyResolver

                resolver = DependencyResolver(ws)
                # Build file index tu disk (khong can TreeItem)
                resolver.build_file_index_from_disk(ws)

                dep_graph: dict[str, list[str]] = {}
                primary_set = {str(p) for p in abs_paths}
                all_deps: set[Path] = set()

                # ============================================================
                # Feature 2: Depth-based codemap for transitive dependencies
                # Khi dependency_depth >= 2, su dung get_related_files_with_depth()
                # de phan biet depth level. Files o depth >= 2 duoc tu dong
                # them vao codemap_paths.
                # ============================================================
                depth_2_plus_paths: set[str] = set()

                for pf in abs_paths:
                    if dependency_depth >= 2:
                        # Su dung depth-aware resolution
                        related_with_depth = resolver.get_related_files_with_depth(  # type: ignore[attr-defined]
                            pf, max_depth=dependency_depth
                        )
                        related = set(related_with_depth.keys())

                        # Phan loai files theo depth
                        for dep_path, depth_level in related_with_depth.items():
                            if str(dep_path) not in primary_set and depth_level >= 2:
                                depth_2_plus_paths.add(str(dep_path))
                    else:
                        related = resolver.get_related_files(
                            pf, max_depth=dependency_depth
                        )

                    # Chi lay files chua co trong primary
                    new_deps = {r for r in related if str(r) not in primary_set}
                    all_deps.update(new_deps)

                    # Ghi nhan dependency graph
                    rel_pf = str(pf.relative_to(ws))
                    dep_graph[rel_pf] = [
                        str(r.relative_to(ws)) for r in related if r != pf
                    ]

                dependency_files = sorted(all_deps)
                dependency_graph = dep_graph

                # Auto-add depth >= 2 files vao codemap set
                if depth_2_plus_paths:
                    resolved_codemap_set.update(depth_2_plus_paths)
                    logger.info(
                        "Auto-codemap %d transitive dependencies (depth >= 2)",
                        len(depth_2_plus_paths),
                    )

                # Warning neu qua nhieu files
                if len(dependency_files) > 50:
                    logger.warning(
                        "Dependency expansion returned %d files. Consider reducing depth.",
                        len(dependency_files),
                    )
            except Exception as e:
                logger.warning("Dependency expansion failed: %s", e)

        # Validate output_format
        valid_formats = {"xml", "json", "plain", "smart"}
        if output_format not in valid_formats:
            return f"Error: Invalid format '{output_format}'. Use: {', '.join(valid_formats)}"

        try:
            from services.prompt_build_service import (
                PromptBuildService,
            )

            service = PromptBuildService()

            # Goi build_prompt_full de lay BuildResult day du
            build_result = service.build_prompt_full(
                file_paths=abs_paths,
                workspace=ws,
                instructions=instructions,
                output_format=output_format,
                include_git_changes=include_git_changes,
                use_relative_paths=True,
                dependency_files=dependency_files if dependency_files else None,
                profile=resolved_profile_name,
                max_tokens=max_tokens,
                codemap_paths=resolved_codemap_set if resolved_codemap_set else None,
            )

            # Gan dependency_graph vao BuildResult
            if dependency_graph:
                build_result.dependency_graph = dependency_graph

            prompt_text = build_result.prompt_text
            token_count = build_result.total_tokens

            # Ghi ra file neu co chi dinh
            if output_file:
                out_path = Path(output_file)
                if not out_path.is_absolute():
                    out_path = ws / out_path
                out_path = out_path.resolve()

                # Validate output path stays within workspace (chong path traversal)
                if not out_path.is_relative_to(ws):
                    return "Error: Output file path must be within workspace."

                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(prompt_text, encoding="utf-8")

                # Tra ve JSON metadata khi metadata_format="json"
                if metadata_format == "json":
                    import json as _json

                    metadata = build_result.to_metadata_dict()
                    metadata["output_file"] = str(out_path)
                    # Include codemap info in metadata
                    if resolved_codemap_set:
                        metadata["codemap_file_count"] = len(resolved_codemap_set)
                    return _json.dumps(metadata, ensure_ascii=False, indent=2)

                # Tra ve text summary (default behavior)
                breakdown = build_result.breakdown
                breakdown_lines = []
                for key, val in breakdown.items():
                    if val > 0:
                        label = key.replace("_", " ").title()
                        breakdown_lines.append(f"  {label}: {val:,}")

                total_files = len(abs_paths) + len(dependency_files)
                summary = (
                    f"Prompt written to: {out_path}\n"
                    f"Total tokens: {token_count:,}\n"
                    f"Files included: {total_files}\n"
                    f"Format: {output_format}\n"
                )
                if resolved_profile_name:
                    summary += f"Profile: {resolved_profile_name}\n"
                if dependency_files:
                    summary += f"Dependencies expanded: {len(dependency_files)} files\n"
                if resolved_codemap_set:
                    summary += f"Codemap-only files: {len(resolved_codemap_set)}\n"
                summary += "Breakdown:\n" + "\n".join(breakdown_lines)
                return summary
            else:
                # Tra ve truc tiep (canh bao: co the rat lon)
                total_files = len(abs_paths) + len(dependency_files)
                return (
                    f"--- Prompt ({token_count:,} tokens, {total_files} files, format={output_format}) ---\n"
                    + prompt_text
                )

        except Exception as e:
            logger.error("build_prompt error: %s", e)
            return f"Error building prompt: {e}"
