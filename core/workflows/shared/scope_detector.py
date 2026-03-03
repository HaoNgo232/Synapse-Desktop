"""
Scope Detector - Phát hiện phạm vi ảnh hưởng từ task description.

Từ task description của user, xác định:
1. Files nào liên quan trực tiếp (primary files)
2. Files nào bị ảnh hưởng gián tiếp (dependency files)
3. Symbols nào trong mỗi file là relevant
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set

from core.dependency_resolver import DependencyResolver
from core.codemaps.symbol_extractor import extract_symbols
from services.workspace_index import collect_files_from_disk


@dataclass
class ScopeResult:
    """
    Kết quả phát hiện scope cho một task.

    Attributes:
        primary_files: Files trực tiếp liên quan (user-specified hoặc auto-detected)
        dependency_files: Files bị ảnh hưởng gián tiếp (imported by primary)
        relevant_symbols: Map file_path -> set của symbol names cần quan tâm
        confidence: Mức độ tin cậy của detection (0.0 - 1.0)
    """

    primary_files: List[str] = field(default_factory=list)
    dependency_files: List[str] = field(default_factory=list)
    relevant_symbols: Dict[str, Set[str]] = field(default_factory=dict)
    confidence: float = 0.0


def detect_scope_from_file_paths(
    workspace_path: Path,
    file_paths: List[str],
    max_depth: int = 2,
) -> ScopeResult:
    """
    Xác định scope từ danh sách file paths đã biết.

    Dùng DependencyResolver để trace imports và tìm các files phụ thuộc.

    Args:
        workspace_path: Workspace root
        file_paths: Danh sách relative file paths (primary targets)
        max_depth: Độ sâu đệ quy khi trace dependencies

    Returns:
        ScopeResult với primary + dependency files
    """
    resolver = DependencyResolver(workspace_path)
    resolver.build_file_index_from_disk(workspace_path)

    primary_files = []
    dependency_files_set: Set[Path] = set()

    for rel_path in file_paths:
        file_path = (workspace_path / rel_path).resolve()
        if not file_path.exists():
            continue

        primary_files.append(rel_path)

        # Trace dependencies
        try:
            related = resolver.get_related_files(file_path, max_depth=max_depth)
            for dep_path in related:
                try:
                    dep_rel = dep_path.relative_to(workspace_path).as_posix()
                    if dep_rel not in primary_files:
                        dependency_files_set.add(dep_path)
                except ValueError:
                    pass
        except Exception:
            pass

    dependency_files = [
        p.relative_to(workspace_path).as_posix() for p in dependency_files_set
    ]

    return ScopeResult(
        primary_files=primary_files,
        dependency_files=dependency_files,
        relevant_symbols={},
        confidence=1.0,  # User-specified paths = highest confidence
    )


def detect_scope_from_git_diff(
    workspace_path: Path,
    max_depth: int = 1,
) -> ScopeResult:
    """
    Xác định scope từ git diff (files đã thay đổi).

    Parse git diff để lấy danh sách changed files,
    sau đó trace dependencies của chúng.

    Args:
        workspace_path: Workspace root
        max_depth: Độ sâu trace dependency

    Returns:
        ScopeResult với changed files làm primary
    """
    from core.utils.git_utils import get_git_diffs
    import re

    try:
        diff_result = get_git_diffs(workspace_path)
        if not diff_result:
            return ScopeResult(confidence=0.0)

        # Extract changed file paths from diff content
        changed_files = []
        for line in (diff_result.work_tree_diff + diff_result.staged_diff).splitlines():
            if line.startswith("diff --git"):
                match = re.search(r"b/(.+)$", line)
                if match:
                    changed_files.append(match.group(1))

        if not changed_files:
            return ScopeResult(confidence=0.0)

        # Use detect_scope_from_file_paths
        result = detect_scope_from_file_paths(
            workspace_path, changed_files, max_depth=max_depth
        )
        result.confidence = 0.9  # Git diff = high confidence
        return result

    except Exception:
        return ScopeResult(confidence=0.0)


def detect_scope_from_symbols(
    workspace_path: Path,
    symbol_names: Set[str],
) -> ScopeResult:
    """
    Xác định scope từ tên các symbols (function/class names).

    Dùng find_references logic để tìm files chứa các symbols này.

    Args:
        workspace_path: Workspace root
        symbol_names: Tên các symbols cần tìm

    Returns:
        ScopeResult với files chứa symbols làm primary
    """
    all_files = collect_files_from_disk(workspace_path, workspace_path=workspace_path)

    primary_files = []
    relevant_symbols: Dict[str, Set[str]] = {}

    for file_path_str in all_files:
        file_path = Path(file_path_str)
        if not file_path.exists():
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            symbols = extract_symbols(str(file_path), content)

            # Check if any target symbols exist in this file
            found_symbols = set()
            for sym in symbols:
                if sym.name in symbol_names:
                    found_symbols.add(sym.name)

            if found_symbols:
                rel_path = file_path.relative_to(workspace_path).as_posix()
                primary_files.append(rel_path)
                relevant_symbols[rel_path] = found_symbols

        except Exception:
            pass

    # Trace dependencies
    result = detect_scope_from_file_paths(workspace_path, primary_files, max_depth=1)
    result.relevant_symbols = relevant_symbols
    result.confidence = (
        0.7 if primary_files else 0.0
    )  # Symbol search = medium confidence

    return result


def _calculate_confidence(
    primary_files: List[str],
    dependency_files: List[str],
    detection_method: str,
) -> float:
    """
    Tính confidence score dựa trên detection method và kết quả.

    Args:
        primary_files: Số primary files tìm được
        dependency_files: Số dependency files
        detection_method: "explicit_paths" | "git_diff" | "symbol_search"

    Returns:
        Confidence score (0.0 - 1.0)
    """
    if not primary_files:
        return 0.0

    base_confidence = {
        "explicit_paths": 1.0,
        "git_diff": 0.9,
        "symbol_search": 0.7,
    }.get(detection_method, 0.5)

    # Adjust based on results
    if len(primary_files) > 10:
        # Too many files = less confident
        base_confidence *= 0.8

    return base_confidence
