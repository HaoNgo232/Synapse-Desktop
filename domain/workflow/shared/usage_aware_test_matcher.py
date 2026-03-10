"""
Usage-Aware Test Matcher - Nâng cấp từ name-heuristic sang semantic matching.

3 tầng:
1. Name-based (fallback)
2. Import-aware (test file import symbol)
3. Call-aware (test body gọi symbol)
"""

import logging
import re
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


def match_tests_to_source_usage_aware(
    workspace_root: Path,
    source_file: str,
    source_symbol: str,
    test_files: List[str],
) -> List[str]:
    """Match test files to source symbol dùng 3 tầng matching.

    Args:
        workspace_root: Workspace root
        source_file: Relative path to source file
        source_symbol: Symbol name (function/class)
        test_files: List of test file paths

    Returns:
        List of matching test files, sorted by confidence
    """
    matches: Dict[str, int] = {}  # test_file -> confidence score

    # Tầng 1: Name-based matching (score 1)
    name_matches = _match_by_name(source_symbol, test_files)
    for test_file in name_matches:
        matches[test_file] = matches.get(test_file, 0) + 1

    # Tầng 2: Import-aware matching (score 2)
    import_matches = _match_by_import(
        workspace_root, source_file, source_symbol, test_files
    )
    for test_file in import_matches:
        matches[test_file] = matches.get(test_file, 0) + 2

    # Tầng 3: Call-aware matching (score 3)
    call_matches = _match_by_call(
        workspace_root, source_file, source_symbol, test_files
    )
    for test_file in call_matches:
        matches[test_file] = matches.get(test_file, 0) + 3

    # Sort by confidence score (descending)
    sorted_matches = sorted(matches.items(), key=lambda x: x[1], reverse=True)
    return [test_file for test_file, _ in sorted_matches]


def _match_by_name(source_symbol: str, test_files: List[str]) -> List[str]:
    """Tầng 1: Name-based heuristic matching."""
    matches: List[str] = []
    sym_lower = source_symbol.lower()

    if len(sym_lower) < 3:
        return matches

    for test_file in test_files:
        test_name = Path(test_file).stem.lower()

        # Remove test prefix
        if test_name.startswith("test_"):
            test_name = test_name[5:]
        elif test_name.startswith("test"):
            test_name = test_name[4:]

        # Match
        if sym_lower in test_name or test_name in sym_lower:
            matches.append(test_file)

    return matches


def _match_by_import(
    workspace_root: Path,
    source_file: str,
    source_symbol: str,
    test_files: List[str],
) -> List[str]:
    """Tầng 2: Import-aware matching - test file import source symbol."""
    matches: List[str] = []

    try:
        from application.services.dependency_resolver import DependencyResolver

        resolver = DependencyResolver(workspace_root)
        resolver.build_file_index_from_disk(workspace_root)

        source_abs = (workspace_root / source_file).resolve()

        for test_file in test_files:
            test_abs = (workspace_root / test_file).resolve()
            if not test_abs.is_file():
                continue

            try:
                # Check if test file imports source file
                imports = resolver.get_related_files(test_abs, max_depth=1)
                if source_abs in imports:
                    matches.append(test_file)
            except Exception:
                continue

    except Exception as e:
        logger.debug("Import-aware matching failed: %s", e)

    return matches


def _match_by_call(
    workspace_root: Path,
    source_file: str,
    source_symbol: str,
    test_files: List[str],
) -> List[str]:
    """Tầng 3: Call-aware matching - test body gọi source symbol."""
    matches: List[str] = []

    pattern = re.compile(r"\b" + re.escape(source_symbol) + r"\b")

    for test_file in test_files:
        test_abs = (workspace_root / test_file).resolve()
        if not test_abs.is_file():
            continue

        try:
            content = test_abs.read_text(encoding="utf-8", errors="ignore")
            if pattern.search(content):
                matches.append(test_file)
        except Exception:
            continue

    return matches
