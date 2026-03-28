"""
Two-Pass Refactor Workflow - Refactor an toàn với 2 phases tách biệt.

Pass 1 (Discovery): Không sửa code, chỉ phân tích:
- Quét cấu trúc liên quan đến refactor scope
- Tìm cơ hội tối ưu, patterns làm lại
- Ghi lại dependencies, risk areas, backward compat concerns
- Output: Discovery Report (structured analysis)

Pass 2 (Planning): Dựa trên discovery report:
- Lên kế hoạch cụ thể: file nào cần sửa, sửa gì
- Đảm bảo backward compatibility
- Đề xuất migration path nếu cần
- Output: Refactor Plan prompt (sẵn sàng cho coding agent)
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from domain.workflow.shared.scope_detector import detect_scope_from_symbols
from domain.workflow.shared.token_budget_manager import TokenBudgetManager
from domain.workflow.shared.handoff_formatter import (
    HandoffContext,
    format_handoff_xml,
    format_relationships_section,
)
from domain.smart_context.parser import smart_parse
from application.services.tokenization_service import TokenizationService
from domain.errors import DomainValidationError

logger = logging.getLogger(__name__)


def _empty_str_list() -> List[str]:
    """Tao list rong co typing ro rang cho dataclass factories."""
    return []


def _empty_dependency_map() -> Dict[str, List[str]]:
    """Tao dict rong co typing ro rang cho dataclass factories."""
    return {}


@dataclass
class DiscoveryReport:
    """
    Kết quả Pass 1 — Discovery (phân tích, không sửa code).

    Attributes:
        scope_files: Files nằm trong refactor scope
        dependencies: Map symbol -> [files that depend on it]
        patterns_found: Patterns hiện tại (để hiểu code trước khi sửa)
        risk_areas: Vùng code có rủi ro cao nếu thay đổi
        opportunities: Cơ hội cải thiện tìm thấy
        backward_compat_concerns: Những chỗ cần giữ backward compatibility
        prompt: Discovery prompt hoàn chỉnh
        total_tokens: Tổng tokens
    """

    scope_files: List[str] = field(default_factory=_empty_str_list)
    dependencies: Dict[str, List[str]] = field(default_factory=_empty_dependency_map)
    patterns_found: List[str] = field(default_factory=_empty_str_list)
    risk_areas: List[str] = field(default_factory=_empty_str_list)
    opportunities: List[str] = field(default_factory=_empty_str_list)
    backward_compat_concerns: List[str] = field(default_factory=_empty_str_list)
    prompt: str = ""
    total_tokens: int = 0


@dataclass
class RefactorPlan:
    """
    Kết quả Pass 2 — Planning (kế hoạch cụ thể).

    Attributes:
        prompt: Refactor plan prompt hoàn chỉnh
        total_tokens: Tổng tokens
        files_to_modify: Danh sách files cần sửa
        migration_needed: True nếu cần migration steps
    """

    prompt: str = ""
    total_tokens: int = 0
    files_to_modify: List[str] = field(default_factory=_empty_str_list)
    migration_needed: bool = False


def run_refactor_discovery(
    workspace_path: str,
    refactor_scope: str,
    file_paths: Optional[List[str]] = None,
    max_tokens: int = 80_000,
    tokenization_service: Optional[TokenizationService] = None,
) -> DiscoveryReport:
    """
    Chạy Pass 1 — Discovery: Phân tích code trước khi refactor.

    Args:
        workspace_path: Absolute path to workspace
        refactor_scope: Mô tả phạm vi refactor
        file_paths: Optional danh sách files đã biết thuộc scope
        max_tokens: Token budget
        tokenization_service: Optional TokenizationService

    Returns:
        DiscoveryReport với phân tích và prompt
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        raise DomainValidationError(f"'{workspace_path}' is not a valid directory")

    tok_service = tokenization_service or TokenizationService()

    # Step 1: Detect scope
    if not file_paths:
        # Try to extract symbol names from refactor_scope
        # Simple heuristic: look for capitalized words or quoted strings
        import re

        potential_symbols = set(re.findall(r"\b[A-Z]\w+\b", refactor_scope))
        potential_symbols.update(re.findall(r"['\"](\w+)['\"]", refactor_scope))

        if potential_symbols:
            scope = detect_scope_from_symbols(ws, potential_symbols)
            file_paths = scope.primary_files
        else:
            file_paths = []

    if not file_paths:
        return DiscoveryReport(
            prompt="[Error: No files detected in refactor scope]",
            scope_files=[],
        )

    # Step 2: Extract smart context for all scope files
    file_contents: Dict[str, str] = {}
    for rel_path in file_paths:
        file_path = (ws / rel_path).resolve()
        if not file_path.exists():
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            smart = smart_parse(str(file_path), content)
            if smart:  # Only add if not None
                file_contents[rel_path] = smart
        except Exception:
            pass

    # Step 3: Build relationships
    relationships = format_relationships_section(ws, file_paths)

    # Step 4: Assemble discovery prompt
    action_instructions = (
        "DISCOVERY PHASE - DO NOT WRITE CODE\n\n"
        "Analyze the code structure and identify:\n"
        "1. Current patterns and design decisions\n"
        "2. Dependencies and coupling points\n"
        "3. Risk areas (high-traffic code, public APIs)\n"
        "4. Refactoring opportunities\n"
        "5. Backward compatibility concerns\n\n"
        "Output a structured analysis report."
    )

    context = HandoffContext(
        task_description=f"Refactor Discovery: {refactor_scope}",
        file_contents=file_contents,
        file_map="",
        relationships=relationships,
        action_instructions=action_instructions,
        metadata={
            "phase": "discovery",
            "scope_files": len(file_paths),
        },
    )

    # Inject contract pack vào extra_sections
    from domain.workflow.shared.contract_injector import inject_contract_pack_to_handoff

    inject_contract_pack_to_handoff(context, ws)

    prompt = format_handoff_xml(context)
    total_tokens = tok_service.count_tokens(prompt)

    return DiscoveryReport(
        scope_files=file_paths,
        dependencies={},
        patterns_found=[],
        risk_areas=[],
        opportunities=[],
        backward_compat_concerns=[],
        prompt=prompt,
        total_tokens=total_tokens,
    )


def run_refactor_planning(
    workspace_path: str,
    refactor_scope: str,
    discovery_report_text: str,
    file_paths: Optional[List[str]] = None,
    max_tokens: int = 80_000,
    tokenization_service: Optional[TokenizationService] = None,
) -> RefactorPlan:
    """
    Chạy Pass 2 — Planning: Lên kế hoạch cụ thể dựa trên discovery.

    Args:
        workspace_path: Absolute path to workspace
        refactor_scope: Mô tả refactor (giống Pass 1)
        discovery_report_text: Output của Pass 1 (text từ AI response)
        file_paths: Optional files cần sửa (override từ discovery)
        max_tokens: Token budget
        tokenization_service: Optional TokenizationService

    Returns:
        RefactorPlan với plan prompt
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        raise DomainValidationError(f"'{workspace_path}' is not a valid directory")

    tok_service = tokenization_service or TokenizationService()

    # Step 1: Parse discovery report to extract file list
    if not file_paths:
        # Simple heuristic: extract file paths from discovery report
        import re

        file_paths = list(
            set(
                re.findall(
                    r"[\w/]+\.(?:py|js|ts|jsx|tsx|java|cpp|c|h)", discovery_report_text
                )
            )
        )

    if not file_paths:
        return RefactorPlan(
            prompt="[Error: No files found in discovery report]",
            files_to_modify=[],
        )

    # Step 2: Read full content for files to modify
    budget_mgr = TokenBudgetManager(tok_service, max_tokens)

    primary_paths = [ws / p for p in file_paths if (ws / p).exists()]

    budget_result = budget_mgr.fit_files_to_budget(
        primary_files=primary_paths,
        dependency_files=[],
        instructions=f"{refactor_scope}\n\nDiscovery Report:\n{discovery_report_text[:2000]}",
        workspace_root=ws,
        relevant_symbols=None,
    )

    # Step 3: Assemble planning prompt
    action_instructions = (
        "PLANNING PHASE\n\n"
        "Based on the discovery report, create a detailed refactoring plan:\n"
        "1. List specific files to modify\n"
        "2. Describe changes for each file\n"
        "3. Ensure backward compatibility\n"
        "4. Identify migration steps if needed\n"
        "5. Suggest test updates\n\n"
        "Output a concrete, actionable plan."
    )

    context = HandoffContext(
        task_description=f"Refactor Planning: {refactor_scope}",
        file_contents=budget_result.file_contents,
        file_map="",
        relationships="",
        action_instructions=action_instructions,
        metadata={
            "phase": "planning",
            "files_to_modify": len(file_paths),
            "discovery_summary": discovery_report_text[:500],
        },
    )

    # Inject contract pack vào extra_sections
    from domain.workflow.shared.contract_injector import inject_contract_pack_to_handoff

    inject_contract_pack_to_handoff(context, ws)

    prompt = format_handoff_xml(context)
    total_tokens = tok_service.count_tokens(prompt)

    return RefactorPlan(
        prompt=prompt,
        total_tokens=total_tokens,
        files_to_modify=file_paths,
        migration_needed=False,  # TODO: detect from discovery report
    )
