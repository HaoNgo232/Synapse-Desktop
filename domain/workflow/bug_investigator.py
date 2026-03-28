"""
Bug Investigation Workflow - AI tự động dò tìm root cause.

Workflow:
1. Nhận bug description + optional error trace từ user
2. Parse error trace để extract file paths, line numbers, function names
3. Bắt đầu từ entry point (file/function trong error trace):
   a. Đọc code của function đó
   b. Trace dependencies (functions nó gọi, functions gọi nó)
   c. Đọc surrounding context
4. Lặp lại cho đến khi đủ context hoặc hết budget
5. Tạo investigation report prompt
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Protocol, Set, cast

from domain.workflow.shared.handoff_formatter import HandoffContext, format_handoff_xml
from domain.workflow.shared.token_budget_manager import TokenBudgetManager
from domain.codemap.graph_builder import CodeMapBuilder
from application.services.tokenization_service import TokenizationService
from domain.errors import DomainValidationError

logger = logging.getLogger(__name__)


def _empty_str_list() -> List[str]:
    """Tao list rong co typing ro rang cho dataclass factories."""
    return []


def _empty_trace_steps() -> List["TraceStep"]:
    """Tao list TraceStep rong co typing ro rang."""
    return []


def _empty_entry_points() -> List[str]:
    """Tao list entry points rong co typing ro rang."""
    return []


class InvestigationNodeLike(Protocol):
    """Protocol toi thieu cho node dung trong investigation workflow."""

    file_path: str
    symbol_name: str
    reason: str
    depth: int


@dataclass
class TraceStep:
    """
    Một bước trong quá trình trace execution path.

    Attributes:
        file_path: File được đọc trong bước này
        symbols: Symbols được focus (function/class names)
        content: Code content đã slice
        reason: Lý do đọc file này (e.g., "Error origin", "Called by X")
        depth: Độ sâu trace từ entry point
    """

    file_path: str = ""
    symbols: List[str] = field(default_factory=_empty_str_list)
    content: str = ""
    reason: str = ""
    depth: int = 0


@dataclass
class InvestigationResult:
    """
    Kết quả Bug Investigation workflow.

    Attributes:
        prompt: Investigation prompt hoàn chỉnh
        total_tokens: Tổng tokens
        trace_steps: Các bước trace (theo thứ tự)
        files_investigated: Số files đã đọc
        max_depth_reached: Độ sâu trace lớn nhất
        entry_points: Điểm bắt đầu trace (từ error trace)
    """

    prompt: str = ""
    total_tokens: int = 0
    trace_steps: List[TraceStep] = field(default_factory=_empty_trace_steps)
    files_investigated: int = 0
    max_depth_reached: int = 0
    entry_points: List[str] = field(default_factory=_empty_entry_points)


# Regex patterns for error trace parsing
PYTHON_TRACEBACK_RE = re.compile(
    r'File "([^"]+)", line (\d+)(?:, in (\w+))?', re.MULTILINE
)
JS_STACK_RE = re.compile(r"at (?:(\w+) )?\(([^:]+):(\d+):(\d+)\)", re.MULTILINE)


def run_bug_investigation(
    workspace_path: str,
    bug_description: str,
    error_trace: str = "",
    entry_files: Optional[List[str]] = None,
    max_depth: int = 4,
    max_tokens: int = 100_000,
    tokenization_service: Optional[TokenizationService] = None,
) -> InvestigationResult:
    """
    Chạy Bug Investigation workflow.

    Args:
        workspace_path: Absolute path to workspace
        bug_description: Mô tả bug/issue
        error_trace: Optional error trace/stacktrace (Python, JS, etc.)
        entry_files: Optional starting files (fallback khi không có trace)
        max_depth: Độ sâu trace tối đa (default 4)
        max_tokens: Token budget
        tokenization_service: Optional TokenizationService

    Returns:
        InvestigationResult với prompt và trace metadata
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        raise DomainValidationError(f"'{workspace_path}' is not a valid directory")

    tok_service = tokenization_service or TokenizationService()

    # Step 1: Parse error trace
    entry_points: List[Dict[str, object]] = []
    if error_trace:
        entry_points = _parse_error_trace(error_trace, ws)

    # Fallback to entry_files
    if not entry_points and entry_files:
        for file_path in entry_files:
            entry_points.append(
                {"file": file_path, "line": 1, "function": None, "depth": 0}
            )

    if not entry_points:
        return InvestigationResult(
            prompt="[Error: No entry points found. Provide error_trace or entry_files]",
            entry_points=[],
        )

    # Step 2: Build hybrid investigation graph
    from domain.workflow.shared import (
        hybrid_investigation_graph as hybrid_investigation_graph_module,
    )

    build_hybrid_investigation_graph = cast(
        Callable[[Path, List[Dict[str, object]], int], List[InvestigationNodeLike]],
        getattr(
            hybrid_investigation_graph_module,
            "build_hybrid_investigation_graph",
        ),
    )

    investigation_nodes = build_hybrid_investigation_graph(
        ws,
        entry_points,
        max_depth,
    )

    # Step 3: Optimize content to fit budget using TokenBudgetManager
    codemap_builder = CodeMapBuilder(ws)
    # BugInvestigator uses a dynamic graph, we don't need full workspace scan but
    # building for the discovered entry points helps scoring.
    for node in investigation_nodes:
        codemap_builder.build_for_file(str(ws / node.file_path))

    budget_mgr = TokenBudgetManager(tok_service, max_tokens, codemap_builder)

    # Map nodes to primary files and relevant symbols
    primary_paths = []
    relevant_symbols: Dict[str, Set[str]] = {}

    for node in investigation_nodes:
        p = ws / node.file_path
        if p.is_file() and p not in primary_paths:
            primary_paths.append(p)
            if node.symbol_name:
                relevant_symbols.setdefault(node.file_path, set()).add(node.symbol_name)

    budget_result = budget_mgr.fit_files_to_budget(
        primary_files=primary_paths,
        dependency_files=[],
        instructions=bug_description,
        workspace_root=ws,
        relevant_symbols=relevant_symbols,
    )

    file_contents = budget_result.file_contents

    # Build trace steps from investigation nodes
    trace_steps = [
        TraceStep(
            file_path=node.file_path,
            symbols=[node.symbol_name] if node.symbol_name else [],
            content=file_contents.get(node.file_path, ""),
            reason=node.reason,
            depth=node.depth,
        )
        for node in investigation_nodes
        if file_contents.get(node.file_path, "")
    ]

    # Step 3: Assemble investigation prompt
    file_contents = {
        step.file_path: step.content for step in trace_steps if step.content
    }

    action_instructions = (
        "Analyze the traced execution path and identify the root cause of the bug. "
        "Provide a detailed explanation and suggest a fix."
    )

    context = HandoffContext(
        task_description=f"Bug Investigation:\n{bug_description}",
        file_contents=file_contents,
        file_map="",
        relationships="",
        action_instructions=action_instructions,
        metadata={
            "trace_depth": max([s.depth for s in trace_steps]) if trace_steps else 0,
            "files_investigated": len(set(s.file_path for s in trace_steps)),
            "entry_points": [ep.get("file", "") for ep in entry_points[:5]],
        },
    )

    # Inject contract pack vào extra_sections
    from domain.workflow.shared.contract_injector import inject_contract_pack_to_handoff

    inject_contract_pack_to_handoff(context, ws)

    prompt = format_handoff_xml(context)
    total_tokens = tok_service.count_tokens(prompt)

    # Calculate optimizations
    optimizations = budget_result.optimizations_applied
    if "smart_truncated" in optimizations or "sliced_primary_files" in optimizations:
        logger.info(f"Bug investigation optimized context: {optimizations}")

    return InvestigationResult(
        prompt=prompt,
        total_tokens=total_tokens,
        trace_steps=trace_steps,
        files_investigated=len(set(s.file_path for s in trace_steps)),
        max_depth_reached=max([s.depth for s in trace_steps]) if trace_steps else 0,
        entry_points=[str(ep.get("file", "")) for ep in entry_points],
    )


def _parse_error_trace(
    error_trace: str,
    workspace_path: Path,
) -> List[Dict[str, object]]:
    """
    Parse error trace/stacktrace để extract entry points.

    Hỗ trợ:
    - Python traceback: File "X", line Y, in Z
    - JavaScript/Node.js: at functionName (file:line:col)

    Args:
        error_trace: Raw error trace string
        workspace_path: Workspace root để validate paths

    Returns:
        List of dicts: [{"file": "path", "line": 42, "function": "name", "depth": 0}, ...]
        Sắp xếp từ bottom (root cause) lên top (entry point)
    """
    entry_points: List[Dict[str, object]] = []

    # Try Python traceback
    for match in PYTHON_TRACEBACK_RE.finditer(error_trace):
        file_path = match.group(1)
        line_num = int(match.group(2))
        func_name = match.group(3) if match.group(3) else None

        # Validate path
        full_path = (workspace_path / file_path).resolve()
        if full_path.exists() and full_path.is_relative_to(workspace_path):
            rel_path = full_path.relative_to(workspace_path).as_posix()
            entry_points.append(
                {"file": rel_path, "line": line_num, "function": func_name, "depth": 0}
            )

    # Try JS stack trace
    if not entry_points:
        for match in JS_STACK_RE.finditer(error_trace):
            func_name = match.group(1)
            file_path = match.group(2)
            line_num = int(match.group(3))

            full_path = (workspace_path / file_path).resolve()
            if full_path.exists() and full_path.is_relative_to(workspace_path):
                rel_path = full_path.relative_to(workspace_path).as_posix()
                entry_points.append(
                    {
                        "file": rel_path,
                        "line": line_num,
                        "function": func_name,
                        "depth": 0,
                    }
                )

    # Reverse to get bottom-up order (root cause first)
    return list(reversed(entry_points))
