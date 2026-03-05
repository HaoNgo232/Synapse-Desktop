"""
Dependency Handler - Xu ly cac tool lien quan den dependency analysis.

Bao gom: get_imports_graph, get_callers, get_related_tests.
"""

import os
import re
from pathlib import Path
from typing import Annotated, List, Optional

from mcp.server.fastmcp import Context
from pydantic import Field

from mcp_server.core.workspace_manager import WorkspaceManager
from mcp_server.core.constants import (
    INLINE_COMMENT_RE,
    STRING_LITERAL_RE,
    logger,
)


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
            from core.dependency_resolver import DependencyResolver
            from services.workspace_index import collect_files_from_disk
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
    async def get_callers(
        symbol_name: Annotated[
            str,
            Field(
                description="Function, method, or class name to find callers of (e.g., 'validate_token', 'UserService.save')."
            ),
        ],
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted."
            ),
        ] = None,
        ctx: Optional[Context] = None,
        file_extensions: Annotated[
            Optional[List[str]],
            Field(
                description='Optional file extensions to search (e.g., [".py", ".ts"]). Searches all code files if omitted.'
            ),
        ] = None,
        max_results: Annotated[
            int,
            Field(
                description="Maximum number of caller entries to return. Default: 30."
            ),
        ] = 30,
    ) -> str:
        """Find all functions/methods that CALL a given symbol, with caller context.

        For each call site, shows the enclosing function name, file path, line number, and code snippet.
        Use this to understand blast radius before modifying a function.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        try:
            from services.workspace_index import collect_files_from_disk
            from core.codemaps.symbol_extractor import extract_symbols
            from core.codemaps.types import SymbolKind

            all_files = collect_files_from_disk(ws, workspace_path=ws)

            # Filter by extension
            if file_extensions:
                ext_set = {e if e.startswith(".") else f".{e}" for e in file_extensions}
                all_files = [f for f in all_files if Path(f).suffix.lower() in ext_set]
            else:
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
                all_files = [
                    f for f in all_files if Path(f).suffix.lower() in code_exts
                ]

            callers: list[
                tuple[str, str, int, str]
            ] = []  # (caller_name, file, line, snippet)
            pattern = re.compile(rf"\b{re.escape(symbol_name)}\s*[\(.]")

            for file_path_str in all_files:
                try:
                    fp = Path(file_path_str)
                    content = fp.read_text(encoding="utf-8", errors="replace")
                    lines = content.splitlines()

                    # Extract symbols to know which function/method each line belongs to
                    symbols = extract_symbols(file_path_str, content)
                    func_symbols = [
                        s
                        for s in symbols
                        if s.kind in (SymbolKind.FUNCTION, SymbolKind.METHOD)
                    ]

                    for i, line in enumerate(lines, start=1):
                        # Skip definitions of the symbol itself
                        stripped = line.strip()
                        if stripped.startswith(
                            ("def ", "function ", "func ", "class ")
                        ):
                            if symbol_name in stripped.split("(")[0]:
                                continue
                        # Skip comments
                        if stripped.startswith(("#", "//", "/*", "*")):
                            continue

                        # Clean strings and inline comments
                        cleaned = STRING_LITERAL_RE.sub("", line)
                        cleaned = INLINE_COMMENT_RE.sub("", cleaned)

                        if pattern.search(cleaned):
                            # Find enclosing function
                            caller_name = "(top-level)"
                            for sym in func_symbols:
                                if sym.line_start <= i <= sym.line_end:
                                    caller_name = f"{sym.parent + '.' if sym.parent else ''}{sym.name}"
                                    break

                            rel_path = os.path.relpath(file_path_str, ws)
                            snippet = stripped[:80]
                            callers.append(
                                (
                                    caller_name,
                                    rel_path,
                                    i,
                                    snippet,
                                )
                            )

                            if len(callers) >= max_results:
                                break
                except (OSError, UnicodeDecodeError):
                    continue

                if len(callers) >= max_results:
                    break

            if not callers:
                return f"No callers found for: {symbol_name}"

            # Group by file
            result_lines = [f"Found {len(callers)} callers of `{symbol_name}`:\n"]
            current_file = ""
            for caller_name, rel_path, line_num, snippet in callers:
                if rel_path != current_file:
                    current_file = rel_path
                    result_lines.append(f"\n{rel_path}:")
                result_lines.append(f"  L{line_num} {caller_name}: {snippet}")

            return "\n".join(result_lines)

        except Exception as e:
            logger.error("get_callers error: %s", e)
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
            from services.workspace_index import collect_files_from_disk

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

                # Generate candidate test file names based on language conventions
                candidates: list[str] = []

                if ext == ".py":
                    candidates = [
                        f"test_{stem}.py",
                        f"{stem}_test.py",
                    ]
                elif ext in (
                    ".js",
                    ".jsx",
                    ".ts",
                    ".tsx",
                    ".mjs",
                    ".cjs",
                ):
                    for test_ext in [
                        ext,
                        ".ts",
                        ".tsx",
                        ".js",
                        ".jsx",
                    ]:
                        candidates.extend(
                            [
                                f"{stem}.test{test_ext}",
                                f"{stem}.spec{test_ext}",
                            ]
                        )
                elif ext == ".go":
                    candidates = [f"{stem}_test.go"]
                elif ext == ".rs":
                    candidates = [
                        f"{stem}_test.rs",
                        f"{stem}.rs",
                    ]
                elif ext == ".java":
                    candidates = [
                        f"{stem}Test.java",
                        f"{stem}Tests.java",
                        f"Test{stem}.java",
                    ]
                elif ext in (".c", ".cpp", ".h", ".hpp"):
                    candidates = [
                        f"test_{stem}.cpp",
                        f"{stem}_test.cpp",
                        f"test_{stem}.c",
                    ]

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
