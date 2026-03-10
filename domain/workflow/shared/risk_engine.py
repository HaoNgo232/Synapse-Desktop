"""
Risk Engine - Shared service để analyze blast radius của code changes.

Tách logic từ dependency_handler.py thành reusable service
dùng cho rp_build, rp_design, rp_review, rp_refactor.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class BlastRadiusResult:
    """Kết quả phân tích blast radius."""

    changed: List[str] = field(default_factory=list)
    first_order_dependents: List[str] = field(default_factory=list)
    transitive_dependents: List[Tuple[str, int]] = field(default_factory=list)
    related_tests: List[str] = field(default_factory=list)
    token_estimate: int = 0
    risk_score: float = 0.0
    risk_reasons: List[str] = field(default_factory=list)


def analyze_blast_radius(
    workspace_root: Path,
    target_files: List[Path],
    max_depth: int = 2,
    include_tests: bool = True,
    include_token_estimate: bool = True,
) -> BlastRadiusResult:
    """Analyze blast radius của target files.

    Args:
        workspace_root: Workspace root path
        target_files: List of absolute paths to files being changed
        max_depth: Max depth for transitive dependency tracing (1-5)
        include_tests: Include related test files
        include_token_estimate: Estimate token cost

    Returns:
        BlastRadiusResult với structured analysis
    """
    from application.services.dependency_resolver import DependencyResolver
    from application.services.workspace_index import collect_files_from_disk

    max_depth = max(1, min(max_depth, 5))

    result = BlastRadiusResult()

    try:
        resolver = DependencyResolver(workspace_root)
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
        all_files = collect_files_from_disk(
            workspace_root, workspace_path=workspace_root
        )
        code_files = [Path(f) for f in all_files if Path(f).suffix.lower() in code_exts]

        # Build reverse dependency map
        reverse_deps: Dict[Path, Set[Path]] = {}
        for cf in code_files:
            try:
                imports = resolver.get_related_files(cf, max_depth=1)
                for imp in imports:
                    if imp not in reverse_deps:
                        reverse_deps[imp] = set()
                    reverse_deps[imp].add(cf)
            except Exception:
                continue

        # BFS from target files
        depth_map: Dict[Path, int] = {}
        for tf in target_files:
            depth_map[tf] = 0

        current_level = set(target_files)
        for depth in range(1, max_depth + 1):
            next_level: Set[Path] = set()
            for f in current_level:
                for dep in reverse_deps.get(f, set()):
                    if dep not in depth_map:
                        depth_map[dep] = depth
                        next_level.add(dep)
            current_level = next_level
            if not current_level:
                break

        # Categorize by depth
        for fp, d in depth_map.items():
            rel = os.path.relpath(fp, workspace_root)
            if d == 0:
                result.changed.append(rel)
            elif d == 1:
                result.first_order_dependents.append(rel)
            else:
                result.transitive_dependents.append((rel, d))

        # Find related test files
        if include_tests:
            result.related_tests = _find_related_tests(
                workspace_root, depth_map, all_files
            )

        # Calculate risk score
        result.risk_score = _calculate_risk_score(result)
        result.risk_reasons = _identify_risk_reasons(result)

        # Estimate tokens
        if include_token_estimate:
            result.token_estimate = _estimate_tokens(result, workspace_root)

    except Exception as e:
        logger.error("Failed to analyze blast radius: %s", e)

    return result


def _find_related_tests(
    workspace_root: Path, depth_map: Dict[Path, int], all_files: List[str]
) -> List[str]:
    """Find test files related to changed files."""
    file_index: Dict[str, List[str]] = {}
    for f in all_files:
        name = Path(f).name.lower()
        if name not in file_index:
            file_index[name] = []
        file_index[name].append(f)

    seen_tests: Set[str] = set()
    test_files: List[str] = []

    for af in depth_map:
        stem = af.stem
        candidates = _get_test_candidates(stem)

        for c in candidates:
            c_lower = c.lower()
            if c_lower in file_index:
                for mp in file_index[c_lower]:
                    rel = os.path.relpath(mp, workspace_root)
                    if rel not in seen_tests:
                        seen_tests.add(rel)
                        test_files.append(rel)

    return test_files


def _get_test_candidates(stem: str) -> List[str]:
    """Generate test file name candidates."""
    return [
        f"test_{stem}.py",
        f"{stem}_test.py",
        f"test_{stem}.ts",
        f"{stem}.test.ts",
        f"test_{stem}.js",
        f"{stem}.test.js",
    ]


def _calculate_risk_score(result: BlastRadiusResult) -> float:
    """Calculate risk score (0.0 - 1.0)."""
    score = 0.0

    # More dependents = higher risk
    score += min(len(result.first_order_dependents) * 0.1, 0.3)
    score += min(len(result.transitive_dependents) * 0.05, 0.2)

    # Deeper transitive deps = higher risk
    if result.transitive_dependents:
        max_depth = max(d for _, d in result.transitive_dependents)
        score += min(max_depth * 0.1, 0.2)

    # No tests = higher risk
    if not result.related_tests:
        score += 0.2

    return min(score, 1.0)


def _identify_risk_reasons(result: BlastRadiusResult) -> List[str]:
    """Identify risk reasons based on analysis."""
    reasons: List[str] = []

    if len(result.first_order_dependents) > 5:
        reasons.append(
            f"High coupling: {len(result.first_order_dependents)} direct dependents"
        )

    if len(result.transitive_dependents) > 10:
        reasons.append(
            f"Deep dependency tree: {len(result.transitive_dependents)} transitive dependents"
        )

    if not result.related_tests:
        reasons.append("No related test files found")

    if result.risk_score > 0.7:
        reasons.append("High risk: Consider extra review and testing")

    return reasons


def _estimate_tokens(result: BlastRadiusResult, workspace_root: Path) -> int:
    """Estimate token cost for reviewing blast radius."""
    from application.services.tokenization_service import TokenizationService

    tok_service = TokenizationService()
    total_tokens = 0

    # Estimate tokens for each file
    files_to_estimate = (
        result.changed
        + result.first_order_dependents
        + [f for f, _ in result.transitive_dependents]
        + result.related_tests
    )

    for rel_path in files_to_estimate:
        try:
            fp = (workspace_root / rel_path).resolve()
            if fp.is_file():
                content = fp.read_text(encoding="utf-8", errors="ignore")
                total_tokens += tok_service.count_tokens(content)
        except Exception:
            continue

    return total_tokens
