"""
Dependency Handler - Xu ly cac tool lien quan den dependency analysis.

Bao gom: get_imports_graph, get_related_tests, blast_radius.
        (get_callers da go bo - dung built-in lsp_find_references.)
"""

import asyncio
import os
from pathlib import Path
from typing import Annotated, List, Optional

from mcp.server.fastmcp import Context
from pydantic import Field

from infrastructure.mcp.core.workspace_manager import WorkspaceManager
from infrastructure.mcp.core.constants import logger


def _get_test_candidates(stem: str, ext: str) -> list[str]:
    """Generate candidate test file names based on language conventions."""
    if ext == ".py":
        return [f"test_{stem}.py", f"{stem}_test.py"]
    elif ext in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
        candidates: list[str] = []
        for test_ext in [ext, ".ts", ".tsx", ".js", ".jsx"]:
            candidates.extend([f"{stem}.test{test_ext}", f"{stem}.spec{test_ext}"])
        return candidates
    elif ext == ".go":
        return [f"{stem}_test.go"]
    elif ext == ".rs":
        return [f"{stem}_test.rs", f"test_{stem}.rs"]
    elif ext == ".java":
        return [f"{stem}Test.java", f"{stem}Tests.java", f"Test{stem}.java"]
    elif ext in (".c", ".cpp", ".h", ".hpp"):
        return [f"test_{stem}.cpp", f"{stem}_test.cpp", f"test_{stem}.c"]
    return []


def register_tools(mcp_instance) -> None:
    """Dang ky dependency tools voi MCP server."""

    @mcp_instance.tool()
    async def get_imports_graph(
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
                description='Optional list of relative file paths to analyze (e.g., ["src/main.py"]). Analyzes all code files if omitted.'
            ),
        ] = None,
        max_depth: Annotated[
            int,
            Field(
                description="Maximum depth for transitive dependency resolution (1-3). Default: 1."
            ),
        ] = 1,
    ) -> str:
        """Get the dependency graph between files as a JSON adjacency list.

        Shows which files import which other files. Includes summary statistics (total edges, most coupled files)
        and the full graph as JSON. Use this to understand module coupling and plan refactoring scope.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        try:
            from domain.codemap.dependency_resolver import DependencyResolver
            from application.services.workspace_index import collect_files_from_disk
            import json

            resolver = DependencyResolver(ws)

            # Build file index (needed for resolution)
            resolver.build_file_index(None)

            # Determine which files to analyze
            if file_paths:
                target_files = []
                for rp in file_paths:
                    fp = (ws / rp).resolve()
                    if not fp.is_relative_to(ws):
                        return f"Error: Path traversal detected for: {rp}"
                    if not fp.is_file():
                        return f"Error: File not found: {rp}"
                    target_files.append(fp)
            else:
                # Analyze all code files
                all_files = collect_files_from_disk(ws, workspace_path=ws)
                code_exts = {
                    ".py",
                    ".js",
                    ".ts",
                    ".jsx",
                    ".tsx",
                    ".go",
                    ".rs",
                }
                target_files = [
                    Path(f) for f in all_files if Path(f).suffix.lower() in code_exts
                ]

            # Build adjacency list
            graph: dict[str, list[str]] = {}

            for file_path in target_files:
                rel_path = os.path.relpath(file_path, ws)
                imports = resolver.get_related_files(file_path, max_depth=max_depth)

                # Convert to relative paths
                import_rels = [os.path.relpath(imp, ws) for imp in imports]
                graph[rel_path] = sorted(import_rels)

            # Generate summary
            total_files = len(graph)
            total_edges = sum(len(imports) for imports in graph.values())

            # Find most coupled files (most imports)
            most_coupled = sorted(graph.items(), key=lambda x: len(x[1]), reverse=True)[
                :5
            ]

            result = [
                "Dependency Graph Summary:",
                f"Files analyzed: {total_files}",
                f"Total import edges: {total_edges}",
                f"Average imports per file: {total_edges / total_files:.1f}"
                if total_files > 0
                else "N/A",
                "\nMost coupled files:",
            ]

            for file, imports in most_coupled:
                result.append(f"  {file}: {len(imports)} imports")

            result.append("\nFull graph (JSON):")
            result.append(json.dumps(graph, indent=2))

            return "\n".join(result)
        except Exception as e:
            logger.error("get_imports_graph error: %s", e)
            return f"Error: {e}"

    @mcp_instance.tool()
    async def get_related_tests(
        file_paths: Annotated[
            List[str],
            Field(
                description='List of relative source file paths to find corresponding test files for (e.g., ["src/auth/login.py", "src/utils.py"]).'
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
        """Find test files corresponding to given source files.

        Uses language-specific naming conventions (test_*.py, *.test.ts, *_test.go, *Test.java, etc.)
        and searches test directories. Useful for verifying test coverage before making changes.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        try:
            from application.services.workspace_index import collect_files_from_disk

            all_files = collect_files_from_disk(ws, workspace_path=ws)
            # Build filename index for fast lookup
            file_index: dict[str, list[str]] = {}
            for f in all_files:
                name = Path(f).name.lower()
                if name not in file_index:
                    file_index[name] = []
                file_index[name].append(f)

            results: dict[str, list[str]] = {}

            for source_rel in file_paths:
                source_path = Path(source_rel)
                stem = source_path.stem
                ext = source_path.suffix.lower()

                candidates = _get_test_candidates(stem, ext)

                found_tests = []
                for candidate in candidates:
                    candidate_lower = candidate.lower()
                    if candidate_lower in file_index:
                        for match_path in file_index[candidate_lower]:
                            rel = os.path.relpath(match_path, ws)
                            if rel not in found_tests:
                                found_tests.append(rel)

                # Also search for files in __tests__ or tests/ directories containing the stem
                stem_lower = stem.lower()
                for fname, fpaths in file_index.items():
                    if stem_lower in fname and ("test" in fname or "spec" in fname):
                        for match_path in fpaths:
                            rel = os.path.relpath(match_path, ws)
                            if rel not in found_tests:
                                if any(
                                    part in rel.lower()
                                    for part in [
                                        "test",
                                        "spec",
                                        "__test",
                                    ]
                                ):
                                    found_tests.append(rel)

                if found_tests:
                    results[source_rel] = sorted(found_tests)

            if not results:
                return "No related test files found for the given source files."

            lines = [
                f"Found tests for {len(results)}/{len(file_paths)} source files:\n"
            ]
            for source, tests in results.items():
                lines.append(f"{source}:")
                for t in tests[:5]:
                    lines.append(f"  -> {t}")
                if len(tests) > 5:
                    lines.append(f"  ... +{len(tests) - 5} more")

            return "\n".join(lines)

        except Exception as e:
            logger.error("get_related_tests error: %s", e)
            return f"Error: {e}"

    @mcp_instance.tool()
    async def blast_radius(
        file_paths: Annotated[
            List[str],
            Field(
                description='List of relative file paths that will be changed (e.g., ["src/auth/login.py", "src/utils.py"]).'
            ),
        ],
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted."
            ),
        ] = None,
        ctx: Optional[Context] = None,
        max_depth: Annotated[
            int,
            Field(
                description="How deep to trace transitive dependents (1-5). Default: 2."
            ),
        ] = 2,
        include_tests: Annotated[
            bool,
            Field(
                description="Include related test files in the analysis. Default: true."
            ),
        ] = True,
        include_token_estimate: Annotated[
            bool,
            Field(
                description="Estimate token cost for reviewing the full blast radius. Default: true."
            ),
        ] = True,
    ) -> str:
        """Analyze the impact (blast radius) of changing a set of files before coding.

        For each file, traces dependents (files that import it) up to max_depth,
        finds related test files, and estimates token cost. Returns a risk-scored
        report to help decide whether a change is safe or needs extra review.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        try:
            from domain.workflow.shared.risk_engine import analyze_blast_radius

            # Validate all file paths
            target_files: list[Path] = []
            for rp in file_paths:
                fp = (ws / rp).resolve()
                if not fp.is_relative_to(ws):
                    return f"Error: Path traversal detected for: {rp}"
                if not fp.is_file():
                    return f"Error: File not found: {rp}"
                target_files.append(fp)

            if not target_files:
                return "Error: No valid file paths provided."

            # Use risk engine
            result = await asyncio.to_thread(
                analyze_blast_radius,
                ws,
                target_files,
                max_depth=max_depth,
                include_tests=include_tests,
                include_token_estimate=include_token_estimate,
            )

            # Format output
            lines = ["# Blast Radius Analysis"]
            lines.append(f"\n## Changed Files ({len(result.changed)})")
            for f in result.changed:
                lines.append(f"  - {f}")

            lines.append(
                f"\n## First-Order Dependents ({len(result.first_order_dependents)})"
            )
            if result.first_order_dependents:
                for f in result.first_order_dependents:
                    lines.append(f"  - {f}")
            else:
                lines.append("  (none)")

            lines.append(
                f"\n## Transitive Dependents ({len(result.transitive_dependents)})"
            )
            if result.transitive_dependents:
                for f, d in result.transitive_dependents:
                    lines.append(f"  - {f} (depth {d})")
            else:
                lines.append("  (none)")

            if include_tests:
                lines.append(f"\n## Related Test Files ({len(result.related_tests)})")
                if result.related_tests:
                    for f in result.related_tests:
                        lines.append(f"  - {f}")
                else:
                    lines.append("  (none)")

            lines.append("\n## Risk Assessment")
            lines.append(f"Risk Score: {result.risk_score:.2f}/1.0")
            if result.risk_reasons:
                lines.append("Risk Reasons:")
                for reason in result.risk_reasons:
                    lines.append(f"  - {reason}")

            total_affected = (
                len(result.changed)
                + len(result.first_order_dependents)
                + len(result.transitive_dependents)
            )
            lines.append(f"Total affected files: {total_affected}")

            if include_token_estimate:
                lines.append(f"Estimated tokens to review: {result.token_estimate:,}")

            lines.append("\n## Summary")
            lines.append(
                f"Changed: {len(result.changed)} | "
                f"Direct dependents: {len(result.first_order_dependents)} | "
                f"Transitive: {len(result.transitive_dependents)} | "
                f"Tests: {len(result.related_tests)}"
            )

            return "\n".join(lines)

        except Exception as e:
            logger.error("blast_radius error: %s", e)
            return f"Error: {e}"
