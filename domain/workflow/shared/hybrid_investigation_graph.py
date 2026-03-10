"""
Hybrid Investigation Graph - Nâng cấp từ import-BFS sang execution graph.

Kết hợp:
1. Same-file symbol context (local scope)
2. Callers/callees (execution flow)
3. Imports (module dependencies)
4. Related tests (test context)
5. Recent git changes (change history)
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set

logger = logging.getLogger(__name__)


@dataclass
class InvestigationNode:
    """Node trong investigation graph."""

    file_path: str
    line_num: int = 0
    symbol_name: str = ""
    depth: int = 0
    reason: str = ""  # why this node was added


def build_hybrid_investigation_graph(
    workspace_root: Path,
    entry_points: List[Dict],
    max_depth: int = 4,
) -> List[InvestigationNode]:
    """Build hybrid investigation graph từ entry points.

    Thứ tự expand:
    1. Same-file symbol context (depth 0)
    2. Callers/callees (depth 1)
    3. Imports (depth 2)
    4. Related tests (depth 2)
    5. Recent git changes (depth 3)

    Args:
        workspace_root: Workspace root
        entry_points: Parsed entry points từ stack trace
        max_depth: Max depth (1-5)

    Returns:
        List[InvestigationNode] theo thứ tự priority
    """
    from application.services.dependency_resolver import DependencyResolver
    from domain.codemap.graph_builder import CodeMapBuilder

    max_depth = max(1, min(max_depth, 5))
    nodes: List[InvestigationNode] = []
    visited: Set[str] = set()

    resolver = DependencyResolver(workspace_root)
    resolver.build_file_index_from_disk(workspace_root)

    codemap = CodeMapBuilder(workspace_root)

    # Depth 0: Entry points + same-file symbols
    for ep in entry_points:
        file_path = str(ep.get("file", ""))
        line_num = int(ep.get("line", 0))
        func_name = str(ep.get("function", ""))

        if not file_path or file_path in visited:
            continue

        visited.add(file_path)
        nodes.append(
            InvestigationNode(
                file_path=file_path,
                line_num=line_num,
                symbol_name=func_name,
                depth=0,
                reason="entry_point",
            )
        )

        # Add same-file symbols
        try:
            abs_path = str((workspace_root / file_path).resolve())
            codemap.build_for_file(abs_path)
            # Symbols từ cùng file sẽ được include khi format context
        except Exception:
            pass

    # Depth 1: Callers/callees
    if max_depth >= 1:
        for ep in entry_points:
            file_path = str(ep.get("file", ""))
            if not file_path:
                continue

            try:
                abs_path = (workspace_root / file_path).resolve()
                # Get files that call this file
                callers = resolver.get_related_files(abs_path, max_depth=1)
                for caller in callers:
                    caller_rel = caller.relative_to(workspace_root).as_posix()
                    if caller_rel not in visited:
                        visited.add(caller_rel)
                        nodes.append(
                            InvestigationNode(
                                file_path=caller_rel,
                                depth=1,
                                reason="caller",
                            )
                        )
            except Exception:
                pass

    # Depth 2: Imports + related tests
    if max_depth >= 2:
        for node in nodes[:]:  # Iterate over copy
            if node.depth >= 1:
                continue

            try:
                abs_path = (workspace_root / node.file_path).resolve()
                imports = resolver.get_related_files(abs_path, max_depth=1)
                for imp in imports:
                    imp_rel = imp.relative_to(workspace_root).as_posix()
                    if imp_rel not in visited:
                        visited.add(imp_rel)
                        nodes.append(
                            InvestigationNode(
                                file_path=imp_rel,
                                depth=2,
                                reason="import",
                            )
                        )
            except Exception:
                pass

        # Related tests
        for node in nodes[:]:
            if node.depth >= 1:
                continue

            test_files = _find_related_tests(workspace_root, node.file_path)
            for test_file in test_files:
                if test_file not in visited:
                    visited.add(test_file)
                    nodes.append(
                        InvestigationNode(
                            file_path=test_file,
                            depth=2,
                            reason="related_test",
                        )
                    )

    # Depth 3: Recent git changes
    if max_depth >= 3:
        try:
            from infrastructure.git.git_utils import get_git_logs

            logs = get_git_logs(workspace_root, max_commits=10)
            if logs and logs.commits:
                changed_files_set: Set[str] = set()
                for commit in logs.commits[:10]:
                    for file_path in commit.files:
                        changed_files_set.add(file_path)

                for changed_file in list(changed_files_set)[:5]:
                    if changed_file not in visited:
                        # Kiem tra file con ton tai truoc khi them
                        changed_abs = (workspace_root / changed_file).resolve()
                        if not changed_abs.is_file():
                            continue
                        if not changed_abs.is_relative_to(workspace_root):
                            continue
                        visited.add(changed_file)
                        nodes.append(
                            InvestigationNode(
                                file_path=changed_file,
                                depth=3,
                                reason="recent_change",
                            )
                        )
        except Exception:
            pass

    return nodes


def _find_related_tests(workspace_root: Path, source_file: str) -> List[str]:
    """Find test files related to source file."""
    from application.services.workspace_index import collect_files_from_disk

    stem = Path(source_file).stem
    test_candidates = [
        f"test_{stem}.py",
        f"{stem}_test.py",
        f"test_{stem}.ts",
        f"{stem}.test.ts",
        f"test_{stem}.js",
        f"{stem}.test.js",
    ]

    all_files = collect_files_from_disk(workspace_root, workspace_path=workspace_root)
    test_files: List[str] = []

    for test_candidate in test_candidates:
        for file_path in all_files:
            if Path(file_path).name.lower() == test_candidate.lower():
                rel_path = Path(file_path).relative_to(workspace_root).as_posix()
                test_files.append(rel_path)

    return test_files
