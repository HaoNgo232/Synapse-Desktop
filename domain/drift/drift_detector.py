"""
Design Drift Detector - Phát hiện khi code thay đổi vượt khỏi plan ban đầu.

So sánh trạng thái trước/sau edit để báo:
- Module nào tăng coupling
- Public API nào đổi
- Dependency edge nào mới xuất hiện
- File nào bị lan rộng ngoài phạm vi ban đầu
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Drift scoring thresholds
HIGH_SCOPE_RATIO = 0.5
MEDIUM_SCOPE_RATIO = 0.2
HIGH_ISSUE_COUNT = 10
MEDIUM_ISSUE_COUNT = 5
# Coupling: cảnh báo khi imports tăng hơn ngưỡng này
COUPLING_INCREASE_THRESHOLD = 2


@dataclass
class DriftReport:
    """Kết quả phân tích drift."""

    # Files trong plan gốc
    planned_files: List[str] = field(default_factory=list)
    # Files thực tế bị sửa
    actual_changed_files: List[str] = field(default_factory=list)
    # Files ngoài scope (drift)
    out_of_scope_files: List[str] = field(default_factory=list)
    # New dependency edges
    new_dependencies: List[str] = field(default_factory=list)  # "A -> B"
    # Changed public symbols (new/modified/removed)
    public_api_changes: List[str] = field(default_factory=list)
    # Coupling increase warnings
    coupling_warnings: List[str] = field(default_factory=list)
    # Overall drift score: LOW, MEDIUM, HIGH
    drift_score: str = "LOW"
    # Summary text
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "planned_files": self.planned_files,
            "actual_changed_files": self.actual_changed_files,
            "out_of_scope_files": self.out_of_scope_files,
            "new_dependencies": self.new_dependencies,
            "public_api_changes": self.public_api_changes,
            "coupling_warnings": self.coupling_warnings,
            "drift_score": self.drift_score,
            "summary": self.summary,
        }


def detect_drift(
    workspace_root: Path,
    planned_files: List[str],
    actual_changed_files: List[str],
    pre_edit_symbols: Optional[Dict[str, List[str]]] = None,
    post_edit_symbols: Optional[Dict[str, List[str]]] = None,
    pre_edit_deps: Optional[Dict[str, List[str]]] = None,
    post_edit_deps: Optional[Dict[str, List[str]]] = None,
) -> DriftReport:
    """
    Detect design drift by comparing planned vs actual changes.

    Args:
        workspace_root: Workspace root path
        planned_files: Files that were supposed to be changed
        actual_changed_files: Files that were actually changed
        pre_edit_symbols: Symbols before edit {file: [symbol_names]}
        post_edit_symbols: Symbols after edit {file: [symbol_names]}
        pre_edit_deps: Dependencies before edit {file: [imported_files]}
        post_edit_deps: Dependencies after edit {file: [imported_files]}

    Returns:
        DriftReport with analysis
    """
    report = DriftReport(
        planned_files=planned_files,
        actual_changed_files=actual_changed_files,
    )

    planned_set = set(planned_files)
    actual_set = set(actual_changed_files)

    # 1. Tìm files ngoài scope ban đầu
    report.out_of_scope_files = sorted(actual_set - planned_set)

    # 2. Tìm dependency edges mới
    if pre_edit_deps and post_edit_deps:
        for file_path, new_deps in post_edit_deps.items():
            old_deps = pre_edit_deps.get(file_path, [])
            for dep in new_deps:
                if dep not in old_deps:
                    report.new_dependencies.append(f"{file_path} -> {dep}")

    # 3. Tìm thay đổi public API
    if pre_edit_symbols and post_edit_symbols:
        all_files = set(
            list(pre_edit_symbols.keys()) + list(post_edit_symbols.keys())
        )
        for fp in all_files:
            old_syms = set(pre_edit_symbols.get(fp, []))
            new_syms = set(post_edit_symbols.get(fp, []))
            added = new_syms - old_syms
            removed = old_syms - new_syms
            for s in sorted(added):
                report.public_api_changes.append(f"+ {fp}::{s}")
            for s in sorted(removed):
                report.public_api_changes.append(f"- {fp}::{s}")

    # 4. Cảnh báo coupling tăng
    if post_edit_deps:
        for file_path, deps in post_edit_deps.items():
            old_deps = pre_edit_deps.get(file_path, []) if pre_edit_deps else []
            new_count = len(deps)
            old_count = len(old_deps)
            if new_count > old_count + COUPLING_INCREASE_THRESHOLD:
                report.coupling_warnings.append(
                    f"{file_path}: imports increased from {old_count} to {new_count}"
                )

    # 5. Tính drift score
    out_of_scope_ratio = len(report.out_of_scope_files) / max(len(planned_files), 1)
    issues = (
        len(report.out_of_scope_files)
        + len(report.new_dependencies)
        + len(report.coupling_warnings)
    )

    if out_of_scope_ratio > HIGH_SCOPE_RATIO or issues > HIGH_ISSUE_COUNT:
        report.drift_score = "HIGH"
    elif out_of_scope_ratio > MEDIUM_SCOPE_RATIO or issues > MEDIUM_ISSUE_COUNT:
        report.drift_score = "MEDIUM"
    else:
        report.drift_score = "LOW"

    # 6. Tạo summary
    lines = [f"Design Drift Score: {report.drift_score}"]
    lines.append(
        f"Planned files: {len(planned_files)}, Actual changed: {len(actual_changed_files)}"
    )
    if report.out_of_scope_files:
        lines.append(f"Out of scope: {len(report.out_of_scope_files)} files")
    if report.new_dependencies:
        lines.append(f"New dependencies: {len(report.new_dependencies)}")
    if report.public_api_changes:
        lines.append(f"Public API changes: {len(report.public_api_changes)}")
    if report.coupling_warnings:
        lines.append(f"Coupling warnings: {len(report.coupling_warnings)}")
    report.summary = "\n".join(lines)

    return report
