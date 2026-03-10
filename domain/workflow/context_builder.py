"""
Context Builder Workflow - Tự động chuẩn bị context tối ưu cho AI agent.

Workflow:
1. Nhận task description + optional file paths từ user
2. Detect scope: primary files + dependency files
3. Thu thập code structure (codemap) cho các files
4. Đọc file contents và optimize để fit token budget
5. Tạo handoff prompt giải thích mối quan hệ giữa files
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from domain.workflow.shared.scope_detector import detect_scope_from_file_paths
from domain.workflow.shared.token_budget_manager import TokenBudgetManager
from domain.workflow.shared.handoff_formatter import (
    HandoffContext,
    format_handoff_xml,
    format_relationships_section,
)
from domain.prompt.generator import generate_file_map
from infrastructure.filesystem.file_utils import scan_directory
from application.services.tokenization_service import TokenizationService

logger = logging.getLogger(__name__)


@dataclass
class BuildResult:
    """
    Kết quả của Context Builder workflow.

    Attributes:
        prompt: Prompt hoàn chỉnh (XML format)
        total_tokens: Tổng tokens của prompt
        files_included: Số files được include
        files_sliced: Số files bị cắt (không full content)
        files_smart_only: Số files chỉ có signatures
        scope_summary: Tóm tắt scope detection
        optimizations: Danh sách các bước tối ưu đã áp dụng
    """

    prompt: str = ""
    total_tokens: int = 0
    files_included: int = 0
    files_sliced: int = 0
    files_smart_only: int = 0
    scope_summary: str = ""
    optimizations: List[str] = field(default_factory=list)


def run_context_builder(
    workspace_path: str,
    task_description: str,
    file_paths: Optional[List[str]] = None,
    max_tokens: int = 100_000,
    include_codemap: bool = True,
    include_git_changes: bool = False,
    include_relationships: bool = True,
    output_file: Optional[str] = None,
    tokenization_service: Optional[TokenizationService] = None,
) -> BuildResult:
    """
    Chạy Context Builder workflow.

    Args:
        workspace_path: Absolute path to workspace root
        task_description: Mô tả task cần thực hiện
        file_paths: Optional danh sách relative paths (nếu None, auto-detect)
        max_tokens: Token budget tối đa (default 100k)
        include_codemap: Có bao gồm code signatures không
        include_git_changes: Có bao gồm git diffs không
        include_relationships: Có bao gồm dependency relationships không
        output_file: Optional path để ghi prompt ra file (cho cross-agent handoff)
        tokenization_service: Optional TokenizationService (inject)

    Returns:
        BuildResult với prompt và metadata
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        raise ValueError(f"'{workspace_path}' is not a valid directory")

    # Validate output_file path traversal
    if output_file:
        out_path = (ws / output_file).resolve()
        if not out_path.is_relative_to(ws):
            raise ValueError("output_file path traversal detected")

    # Initialize tokenization service
    tok_service = tokenization_service or TokenizationService()

    # Step 1: Detect scope
    if not file_paths:
        # Auto-detect: scan workspace for relevant files
        # For now, fallback to empty list (future: NLP-based detection)
        file_paths = []

    scope = detect_scope_from_file_paths(ws, file_paths, max_depth=2)

    if not scope.primary_files:
        return BuildResult(
            prompt="[Error: No files detected in scope]",
            scope_summary="No files found",
        )

    # Step 2: Build file map
    from infrastructure.filesystem.ignore_engine import IgnoreEngine

    ignore_engine = IgnoreEngine()
    tree = scan_directory(ws, ignore_engine)
    selected_paths = set(
        str(ws / p) for p in scope.primary_files + scope.dependency_files
    )
    file_map = generate_file_map(tree, selected_paths, workspace_root=ws)

    # Step 3: Optimize content to fit budget
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

    # Step 4: Build relationships section
    relationships = ""
    if include_relationships:
        relationships = format_relationships_section(
            ws, scope.primary_files + scope.dependency_files
        )

    # Step 5: Assemble handoff prompt
    action_instructions = (
        "Analyze the provided code context and implement the requested task. "
        "Ensure backward compatibility and add appropriate tests."
    )

    context = HandoffContext(
        task_description=task_description,
        file_contents=budget_result.file_contents,
        file_map=file_map,
        relationships=relationships,
        action_instructions=action_instructions,
        metadata={
            "total_tokens": budget_result.total_tokens,
            "files_included": len(budget_result.file_contents),
            "files_sliced": len(budget_result.files_sliced),
            "files_smartified": len(budget_result.files_smartified),
            "optimizations": ", ".join(budget_result.optimizations_applied),
        },
    )

    # Inject contract pack vào extra_sections
    from domain.workflow.shared.contract_injector import inject_contract_pack_to_handoff

    inject_contract_pack_to_handoff(context, ws)

    prompt = format_handoff_xml(context)

    # Step 6: Write to output file if specified
    if output_file:
        out_path = (ws / output_file).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(prompt, encoding="utf-8")

    # Build result
    scope_summary = (
        f"{len(scope.primary_files)} primary, "
        f"{len(scope.dependency_files)} dependencies"
    )

    return BuildResult(
        prompt=prompt,
        total_tokens=budget_result.total_tokens,
        files_included=len(budget_result.file_contents),
        files_sliced=len(budget_result.files_sliced),
        files_smart_only=len(budget_result.files_smartified),
        scope_summary=scope_summary,
        optimizations=budget_result.optimizations_applied,
    )
