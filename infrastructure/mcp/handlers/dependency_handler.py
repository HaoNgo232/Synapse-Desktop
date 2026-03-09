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
            from application.services.dependency_resolver import DependencyResolver
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
            from application.services.dependency_resolver import DependencyResolver
            from application.services.workspace_index import collect_files_from_disk

            max_depth = max(1, min(max_depth, 5))

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

            def _analyze() -> dict:
                resolver = DependencyResolver(ws)
                resolver.build_file_index(None)

                code_exts = {
                    ".py",
                    ".js",
                    ".ts",
                    ".jsx",
                    ".tsx",
                    ".go",
                    ".rs",
                    ".java",
                    ".c",
                    ".cpp",
                    ".h",
                }
                all_files = collect_files_from_disk(ws, workspace_path=ws)
                code_files = [
                    Path(f) for f in all_files if Path(f).suffix.lower() in code_exts
                ]

                # Build reverse dependency map: file -> set of files that import it
                reverse_deps: dict[Path, set[Path]] = {}
                for cf in code_files:
                    try:
                        imports = resolver.get_related_files(cf, max_depth=1)
                        for imp in imports:
                            if imp not in reverse_deps:
                                reverse_deps[imp] = set()
                            reverse_deps[imp].add(cf)
                    except Exception:
                        continue

                # BFS from target files to find dependents at each depth level
                depth_map: dict[Path, int] = {}
                for tf in target_files:
                    depth_map[tf] = 0

                current_level = set(target_files)
                for depth in range(1, max_depth + 1):
                    next_level: set[Path] = set()
                    for f in current_level:
                        for dep in reverse_deps.get(f, set()):
                            if dep not in depth_map:
                                depth_map[dep] = depth
                                next_level.add(dep)
                    current_level = next_level
                    if not current_level:
                        break

                # Categorize by depth
                changed: list[str] = []
                first_order: list[str] = []
                transitive: list[tuple[str, int]] = []
                for fp, d in depth_map.items():
                    rel = os.path.relpath(fp, ws)
                    if d == 0:
                        changed.append(rel)
                    elif d == 1:
                        first_order.append(rel)
                    else:
                        transitive.append((rel, d))

                # Find related test files
                test_files: list[str] = []
                if include_tests:
                    file_index: dict[str, list[str]] = {}
                    for f in all_files:
                        name = Path(f).name.lower()
                        if name not in file_index:
                            file_index[name] = []
                        file_index[name].append(f)

                    seen_tests: set[str] = set()
                    for af in depth_map:
                        stem = af.stem
                        ext = af.suffix.lower()
                        candidates = _get_test_candidates(stem, ext)

                        for c in candidates:
                            c_lower = c.lower()
                            if c_lower in file_index:
                                for mp in file_index[c_lower]:
                                    rel = os.path.relpath(mp, ws)
                                    if rel not in seen_tests:
                                        seen_tests.add(rel)
                                        test_files.append(rel)

                        # Also search in test/spec directories
                        stem_lower = stem.lower()
                        for fname, fpaths in file_index.items():
                            if stem_lower in fname and (
                                "test" in fname or "spec" in fname
                            ):
                                for mp in fpaths:
                                    rel = os.path.relpath(mp, ws)
                                    if rel not in seen_tests:
                                        if any(
                                            part in rel.lower()
                                            for part in ["test", "spec", "__test"]
                                        ):
                                            seen_tests.add(rel)
                                            test_files.append(rel)

                # Token estimate
                token_count = 0
                if include_token_estimate:
                    from application.services.tokenization_service import (
                        TokenizationService,
                    )

                    tok_svc = TokenizationService()
                    for fp in depth_map:
                        try:
                            content = fp.read_text(encoding="utf-8", errors="replace")
                            token_count += tok_svc.count_tokens(content)
                        except OSError:
                            continue
                    for tf_rel in test_files:
                        try:
                            content = (ws / tf_rel).read_text(
                                encoding="utf-8", errors="replace"
                            )
                            token_count += tok_svc.count_tokens(content)
                        except OSError:
                            continue

                return {
                    "changed": sorted(changed),
                    "first_order": sorted(first_order),
                    "transitive": sorted(transitive, key=lambda x: (x[1], x[0])),
                    "test_files": sorted(test_files),
                    "token_count": token_count,
                }

            data = await asyncio.to_thread(_analyze)

            # Build the report
            total_affected = (
                len(data["changed"])
                + len(data["first_order"])
                + len(data["transitive"])
                + len(data["test_files"])
            )

            if total_affected <= 3:
                risk = "LOW"
            elif total_affected <= 10:
                risk = "MEDIUM"
            elif total_affected <= 25:
                risk = "HIGH"
            else:
                risk = "CRITICAL"

            lines = ["# Blast Radius Analysis\n"]

            lines.append(f"## Directly Affected Files ({len(data['changed'])})")
            for f in data["changed"]:
                lines.append(f"  - {f}")

            lines.append(f"\n## First-Order Dependents ({len(data['first_order'])})")
            if data["first_order"]:
                for f in data["first_order"]:
                    lines.append(f"  - {f}")
            else:
                lines.append("  (none)")

            lines.append(f"\n## Transitive Dependents ({len(data['transitive'])})")
            if data["transitive"]:
                for f, d in data["transitive"]:
                    lines.append(f"  - {f} (depth {d})")
            else:
                lines.append("  (none)")

            if include_tests:
                lines.append(f"\n## Related Test Files ({len(data['test_files'])})")
                if data["test_files"]:
                    for f in data["test_files"]:
                        lines.append(f"  - {f}")
                else:
                    lines.append("  (none)")

            lines.append(f"\n## Risk Assessment: {risk}")
            lines.append(f"Total affected files: {total_affected}")

            if include_token_estimate:
                lines.append(f"Estimated tokens to review: {data['token_count']:,}")

            lines.append("\n## Summary")
            lines.append(
                f"Changed: {len(data['changed'])} | "
                f"Direct dependents: {len(data['first_order'])} | "
                f"Transitive: {len(data['transitive'])} | "
                f"Tests: {len(data['test_files'])}"
            )

            return "\n".join(lines)

        except Exception as e:
            logger.error("blast_radius error: %s", e)
            return f"Error: {e}"
