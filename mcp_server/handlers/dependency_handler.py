"""
Dependency Handler - Xu ly cac tool lien quan den dependency analysis.

Bao gom: get_imports_graph, get_callers, get_related_tests.
"""

import os
import re
from pathlib import Path
from typing import List, Optional

from mcp_server.core.constants import (
    INLINE_COMMENT_RE,
    STRING_LITERAL_RE,
    logger,
)


def register_tools(mcp_instance) -> None:
    """Dang ky dependency tools voi MCP server.

    Args:
        mcp_instance: FastMCP server instance.
    """

    # Ham get_imports_graph tao do thi phu thuoc giua cac file duoi dang JSON
    @mcp_instance.tool()
    def get_imports_graph(
        workspace_path: str,
        file_paths: Optional[List[str]] = None,
        max_depth: int = 1,
    ) -> str:
        """Get dependency graph between files as JSON adjacency list.

        WHY USE THIS OVER BUILT-IN: Your built-in grep can find import statements, but
        can't RESOLVE them to actual file paths (e.g., "from services.auth import login"
        -> "services/auth.py"). This tool uses Synapse's dependency resolver to build
        a proper file-to-file dependency graph.
        """
        ws = Path(workspace_path).resolve()
        if not ws.is_dir():
            return f"Error: '{workspace_path}' is not a valid directory."

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

    # Ham get_callers tim tat ca functions/methods goi mot symbol cu the
    @mcp_instance.tool()
    def get_callers(
        workspace_path: str,
        symbol_name: str,
        file_extensions: Optional[List[str]] = None,
        max_results: int = 30,
    ) -> str:
        """Find all functions/methods that CALL a given symbol, with caller context.

        WHY USE THIS OVER BUILT-IN: Your built-in grep finds text occurrences but can't
        tell you WHICH FUNCTION contains the call. This tool returns caller_function -> callee
        mappings with file and line info, essential for understanding impact before refactoring.

        Example output:
          UserService.create_user (services/user.py:45) calls validate_email
          test_registration (tests/test_user.py:23) calls validate_email

        When to use: Before modifying a function's signature or behavior, check who calls it
        to understand the blast radius of your change.

        Args:
            workspace_path: Absolute path to the workspace root directory.
            symbol_name: Function/method/class name to find callers of.
            file_extensions: Optional filter (e.g., [".py", ".ts"]). None searches all code files.
            max_results: Maximum number of caller entries to return (default: 30).
        """
        ws = Path(workspace_path).resolve()
        if not ws.is_dir():
            return f"Error: '{workspace_path}' is not a valid directory."

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

    # Ham get_related_tests tim test files tuong ung voi source files
    @mcp_instance.tool()
    def get_related_tests(
        workspace_path: str,
        file_paths: List[str],
    ) -> str:
        """Find test files corresponding to given source files.

        WHY USE THIS OVER BUILT-IN: Automatically handles multiple naming conventions
        across languages (test_X.py, X_test.py, X.test.ts, X.spec.ts, __tests__/X.js)
        and searches the entire project. Your built-in grep would need multiple patterns
        and still miss co-located test directories.

        When to use: Before modifying code, find existing tests that verify its behavior.
        After modifying code, find tests to run.

        Args:
            workspace_path: Absolute path to the workspace root directory.
            file_paths: List of relative source file paths to find tests for.
        """
        ws = Path(workspace_path).resolve()
        if not ws.is_dir():
            return f"Error: '{workspace_path}' is not a valid directory."

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
                    # Rust tests are usually inline, but integration tests exist
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
                                # Verify it's actually in a test-like directory or has test-like name
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
