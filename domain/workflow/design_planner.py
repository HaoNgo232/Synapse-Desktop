"""
Design Planner Workflow - Lập kế hoạch thiết kế kiến trúc và triển khai.

Workflow:
1. Nhận task description + optional file paths từ user
2. Detect scope: primary files + dependency files
3. Build file map và thu thập tất cả related files
4. Xác định impacted modules (group files theo top-level directory)
5. Xác định risk areas (files có nhiều callers, dependency depth cao)
6. Tạo design-oriented handoff prompt hướng dẫn AI tạo:
   - Architecture change goals
   - Impacted modules list
   - API/contracts affected
   - Risk areas
   - Migration needs
   - Open questions
   - Test strategy
   - Rollout plan
   - "Do-not-touch" list
7. Package qua HandoffContext + format_handoff_xml
8. Trả về DesignResult
"""

import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

from domain.workflow.shared.scope_detector import detect_scope_from_file_paths
from domain.workflow.shared.token_budget_manager import TokenBudgetManager
from domain.workflow.shared.handoff_formatter import (
    HandoffContext,
    format_handoff_xml,
    format_relationships_section,
)
from domain.prompt.generator import generate_file_map
from infrastructure.filesystem.file_utils import scan_directory
from application.services.dependency_resolver import DependencyResolver
from domain.codemap.graph_builder import CodeMapBuilder
from application.services.tokenization_service import TokenizationService

logger = logging.getLogger(__name__)


HIGH_FAN_IN_THRESHOLD = 3
"""Ngưỡng số callers để coi file là risk area."""

DEEP_CHAIN_THRESHOLD = 3
"""Ngưỡng dependency depth để coi file là risk area."""

DEFAULT_SCOPE_DEPTH = 2
"""Độ sâu mặc định khi trace dependencies cho scope detection."""


@dataclass
class DesignResult:
    """
    Kết quả của Design Planner workflow.

    Attributes:
        prompt: Prompt hoàn chỉnh (XML format)
        total_tokens: Tổng tokens của prompt
        files_included: Số files được include
        files_sliced: Số files bị cắt (không full content)
        files_smart_only: Số files chỉ có signatures
        scope_summary: Tóm tắt scope detection
        impacted_modules: Danh sách top-level modules bị ảnh hưởng
        risk_areas: Danh sách files/modules có rủi ro cao
        optimizations: Danh sách các bước tối ưu đã áp dụng
    """

    prompt: str = ""
    total_tokens: int = 0
    files_included: int = 0
    files_sliced: int = 0
    files_smart_only: int = 0
    scope_summary: str = ""
    impacted_modules: List[str] = field(default_factory=list)
    risk_areas: List[str] = field(default_factory=list)
    optimizations: List[str] = field(default_factory=list)


def _identify_impacted_modules(
    file_paths: List[str],
) -> List[str]:
    """
    Xác định các modules bị ảnh hưởng bằng cách group files theo top-level directory.

    Args:
        file_paths: Danh sách relative file paths

    Returns:
        Sorted list các top-level module names (directories)
    """
    modules: Set[str] = set()
    for rel_path in file_paths:
        parts = Path(rel_path).parts
        if len(parts) > 1:
            modules.add(parts[0])
        else:
            # File ở root level
            modules.add("(root)")
    return sorted(modules)


def _identify_risk_areas(
    workspace_path: Path,
    file_paths: List[str],
    resolver: DependencyResolver,
    codemap_builder: CodeMapBuilder,
) -> List[str]:
    """
    Xác định risk areas — files có nhiều callers hoặc dependency depth cao.

    Phân tích:
    - Files được import bởi nhiều files khác (high fan-in)
    - Files có dependency depth cao (deep trong import chain)

    Args:
        workspace_path: Workspace root
        file_paths: Danh sách relative file paths trong scope
        resolver: DependencyResolver đã build index
        codemap_builder: CodeMapBuilder đã build workspace

    Returns:
        List mô tả risk areas
    """
    risks: List[str] = []

    # Đếm số lần mỗi file được import bởi các files khác trong scope
    import_count: Counter[str] = Counter()
    for rel_path in file_paths:
        file_path = (workspace_path / rel_path).resolve()
        if not file_path.exists():
            continue
        try:
            related = resolver.get_related_files(file_path, max_depth=1)
            for dep in related:
                try:
                    dep_rel = dep.relative_to(workspace_path).as_posix()
                    import_count[dep_rel] += 1
                except ValueError:
                    pass
        except Exception:
            pass

    # Files có nhiều callers
    for dep_rel, count in import_count.most_common():
        if count >= HIGH_FAN_IN_THRESHOLD:
            risks.append(f"{dep_rel} (imported by {count} scope files — high fan-in)")

    # Files có dependency depth cao
    for rel_path in file_paths:
        file_path = (workspace_path / rel_path).resolve()
        if not file_path.exists():
            continue
        try:
            deps_with_depth = resolver.get_related_files_with_depth(
                file_path, max_depth=DEEP_CHAIN_THRESHOLD
            )
            max_depth = max(deps_with_depth.values(), default=0)
            if max_depth >= DEEP_CHAIN_THRESHOLD:
                risks.append(
                    f"{rel_path} (dependency depth {max_depth} — deep import chain)"
                )
        except Exception:
            pass

    # Files có nhiều callers trong codemap
    for rel_path in file_paths:
        abs_path = str((workspace_path / rel_path).resolve())
        codemap = codemap_builder.get_codemap(abs_path)
        if not codemap:
            continue
        for symbol in codemap.symbols:
            callers = codemap_builder.get_callers(symbol.name)
            if len(callers) >= HIGH_FAN_IN_THRESHOLD:
                risks.append(
                    f"{rel_path}::{symbol.name} ({len(callers)} callers — high usage)"
                )

    # Loại bỏ duplicates giữ thứ tự
    seen: Set[str] = set()
    unique_risks: List[str] = []
    for r in risks:
        if r not in seen:
            seen.add(r)
            unique_risks.append(r)

    return unique_risks


def run_design_planner(
    workspace_path: str,
    task_description: str,
    file_paths: Optional[List[str]] = None,
    max_tokens: int = 100_000,
    include_tests: bool = True,
    output_file: Optional[str] = None,
    tokenization_service: Optional[TokenizationService] = None,
) -> DesignResult:
    """
    Chạy Design Planner workflow.

    Args:
        workspace_path: Absolute path to workspace root
        task_description: Mô tả task thiết kế cần lập kế hoạch
        file_paths: Optional danh sách relative paths (nếu None, auto-detect)
        max_tokens: Token budget tối đa (default 100k)
        include_tests: Có bao gồm test files trong scope không
        output_file: Optional path để ghi prompt ra file (cho cross-agent handoff)
        tokenization_service: Optional TokenizationService (inject)

    Returns:
        DesignResult với prompt và metadata
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        raise ValueError(f"'{workspace_path}' is not a valid directory")

    # Validate output_file path traversal
    if output_file:
        out_path = (ws / output_file).resolve()
        if not out_path.is_relative_to(ws):
            raise ValueError("output_file path traversal detected")

    # Initialize services
    tok_service = tokenization_service or TokenizationService()

    # Step 1: Detect scope
    if not file_paths:
        file_paths = []

    scope = detect_scope_from_file_paths(ws, file_paths, max_depth=DEFAULT_SCOPE_DEPTH)

    if not scope.primary_files:
        return DesignResult(
            prompt="[Error: No files detected in scope]",
            scope_summary="No files found",
        )

    all_scope_files = scope.primary_files + scope.dependency_files

    # Lọc test files nếu không include_tests
    if not include_tests:
        all_scope_files = [f for f in all_scope_files if not _is_test_file(f)]

    # Step 2: Build file map
    from infrastructure.filesystem.ignore_engine import IgnoreEngine

    ignore_engine = IgnoreEngine()
    tree = scan_directory(ws, ignore_engine)
    selected_paths = set(str(ws / p) for p in all_scope_files)
    file_map = generate_file_map(tree, selected_paths, workspace_root=ws)

    # Step 3: Build dependency resolver và codemap cho risk analysis
    resolver = DependencyResolver(ws)
    resolver.build_file_index_from_disk(ws)

    codemap_builder = CodeMapBuilder(ws)
    for rel_path in all_scope_files:
        abs_path = str((ws / rel_path).resolve())
        codemap_builder.build_for_file(abs_path)

    # Step 4: Xác định impacted modules
    impacted_modules = _identify_impacted_modules(all_scope_files)

    # Step 5: Xác định risk areas
    risk_areas = _identify_risk_areas(ws, all_scope_files, resolver, codemap_builder)

    # Step 6: Optimize content to fit budget
    budget_mgr = TokenBudgetManager(tok_service, max_tokens)

    primary_paths = [ws / p for p in scope.primary_files]
    dep_paths = [ws / p for p in scope.dependency_files]

    budget_result = budget_mgr.fit_files_to_budget(
        primary_files=primary_paths,
        dependency_files=dep_paths,
        instructions=task_description,
        workspace_root=ws,
        relevant_symbols=scope.relevant_symbols,
    )

    # Step 7: Build relationships section
    relationships = format_relationships_section(ws, all_scope_files)

    # Step 8: Build design-oriented action instructions
    action_instructions = _build_design_instructions(impacted_modules, risk_areas)

    # Step 9: Assemble handoff prompt
    context = HandoffContext(
        task_description=f"Design & Architecture Planning: {task_description}",
        file_contents=budget_result.file_contents,
        file_map=file_map,
        relationships=relationships,
        action_instructions=action_instructions,
        metadata={
            "total_tokens": budget_result.total_tokens,
            "files_included": len(budget_result.file_contents),
            "files_sliced": len(budget_result.files_sliced),
            "files_smartified": len(budget_result.files_smartified),
            "impacted_modules": ", ".join(impacted_modules),
            "risk_areas_count": len(risk_areas),
            "optimizations": ", ".join(budget_result.optimizations_applied),
        },
    )

    prompt = format_handoff_xml(context)

    # Step 10: Write to output file if specified
    if output_file:
        out_path = (ws / output_file).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(prompt, encoding="utf-8")

    # Build result
    scope_summary = (
        f"{len(scope.primary_files)} primary, "
        f"{len(scope.dependency_files)} dependencies"
    )

    return DesignResult(
        prompt=prompt,
        total_tokens=budget_result.total_tokens,
        files_included=len(budget_result.file_contents),
        files_sliced=len(budget_result.files_sliced),
        files_smart_only=len(budget_result.files_smartified),
        scope_summary=scope_summary,
        impacted_modules=impacted_modules,
        risk_areas=risk_areas,
        optimizations=budget_result.optimizations_applied,
    )


def _is_test_file(rel_path: str) -> bool:
    """Kiểm tra xem file có phải test file không."""
    name = Path(rel_path).name.lower()
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".test.ts")
        or name.endswith(".test.js")
        or name.endswith(".spec.ts")
        or name.endswith(".spec.js")
        or "/tests/" in rel_path
        or "/__tests__/" in rel_path
    )


def _build_design_instructions(
    impacted_modules: List[str],
    risk_areas: List[str],
) -> str:
    """
    Tạo action instructions hướng dẫn AI tạo design plan.

    Args:
        impacted_modules: Danh sách modules bị ảnh hưởng
        risk_areas: Danh sách risk areas đã phát hiện

    Returns:
        Action instructions string
    """
    modules_list = (
        "\n".join(f"  - {m}" for m in impacted_modules)
        if impacted_modules
        else "  (none detected)"
    )
    risks_list = (
        "\n".join(f"  - {r}" for r in risk_areas) if risk_areas else "  (none detected)"
    )

    return (
        "DESIGN & ARCHITECTURE PLANNING\n\n"
        "Analyze the provided code context and produce a comprehensive design plan.\n"
        "Your output MUST include ALL of the following sections:\n\n"
        "1. **Architecture Change Goals**\n"
        "   - What changes are needed and why\n"
        "   - Target state vs current state\n\n"
        "2. **Impacted Modules**\n"
        f"   Detected modules in scope:\n{modules_list}\n"
        "   - List every module/package that will be modified\n"
        "   - Describe the nature of changes per module\n\n"
        "3. **API / Contracts Affected**\n"
        "   - Public interfaces that will change\n"
        "   - Data models or schemas affected\n"
        "   - Breaking vs non-breaking changes\n\n"
        "4. **Risk Areas**\n"
        f"   Detected risks:\n{risks_list}\n"
        "   - Identify code with high coupling or fan-in\n"
        "   - Flag areas where changes may cascade\n\n"
        "5. **Migration Needs**\n"
        "   - Data migration steps (if any)\n"
        "   - Feature flags or gradual rollout needs\n"
        "   - Backward compatibility considerations\n\n"
        "6. **Open Questions**\n"
        "   - Ambiguities that need clarification before implementation\n"
        "   - Design alternatives to consider\n\n"
        "7. **Test Strategy**\n"
        "   - What new tests are needed\n"
        "   - What existing tests need updating\n"
        "   - Integration vs unit test coverage\n\n"
        "8. **Rollout Plan**\n"
        "   - Suggested implementation order (phases/PRs)\n"
        "   - Dependencies between phases\n\n"
        "9. **Do-Not-Touch List**\n"
        "   - Files/modules that MUST NOT be modified\n"
        "   - Invariants that must be preserved\n"
    )
