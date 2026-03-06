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
from typing import Dict, List, Optional

from domain.workflow.shared.file_slicer import slice_file_by_line_range
from domain.workflow.shared.handoff_formatter import HandoffContext, format_handoff_xml
from application.services.dependency_resolver import DependencyResolver
from application.services.tokenization_service import TokenizationService

logger = logging.getLogger(__name__)


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
    symbols: List[str] = field(default_factory=list)
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
    trace_steps: List[TraceStep] = field(default_factory=list)
    files_investigated: int = 0
    max_depth_reached: int = 0
    entry_points: List[str] = field(default_factory=list)


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
        raise ValueError(f"'{workspace_path}' is not a valid directory")

    tok_service = tokenization_service or TokenizationService()

    # Step 1: Parse error trace
    entry_points = []
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

    # Step 2: BFS trace execution
    token_budget_remaining = (
        max_tokens - tok_service.count_tokens(bug_description) - 1000
    )
    trace_steps = _trace_execution_bfs(
        ws, entry_points, max_depth, token_budget_remaining, tok_service
    )

    # Step 3: Assemble investigation prompt
    file_contents = {}
    for step in trace_steps:
        file_contents[step.file_path] = step.content

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

    prompt = format_handoff_xml(context)
    total_tokens = tok_service.count_tokens(prompt)

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


def _trace_execution_bfs(
    workspace_path: Path,
    entry_points: List[Dict[str, object]],
    max_depth: int,
    token_budget_remaining: int,
    tokenization_service: TokenizationService,
) -> List[TraceStep]:
    """BFS trace tu entry points, mo rong theo callers/callees.

    Su dung 'queued' set de tranh duplicate entries trong queue,
    va iteration limit de dam bao khong bi resource exhaustion.

    Args:
        workspace_path: Workspace root
        entry_points: Parsed entry points
        max_depth: Do sau toi da
        token_budget_remaining: Tokens con lai
        tokenization_service: Service dem token

    Returns:
        List[TraceStep] theo thu tu BFS
    """
    trace_steps = []
    visited = set()
    # Track files da queued de tranh duplicate entries
    queued: set = set()
    queue = list(entry_points)

    # Khoi tao queued set tu entry_points
    for ep in entry_points:
        file_path = str(ep.get("file", ""))
        if file_path:
            queued.add(file_path)

    resolver = DependencyResolver(workspace_path)
    resolver.build_file_index_from_disk(workspace_path)

    # Safety net: gioi han so iterations de tranh resource exhaustion
    max_iterations = 1000
    iteration_count = 0

    while queue and token_budget_remaining > 0 and iteration_count < max_iterations:
        iteration_count += 1
        current = queue.pop(0)
        file_path_obj = current.get("file", "")
        line_num_obj = current.get("line", 1)
        depth_obj = current.get("depth", 0)

        file_path = str(file_path_obj) if file_path_obj else ""
        line_num = int(line_num_obj) if isinstance(line_num_obj, (int, str)) else 1
        depth = int(depth_obj) if isinstance(depth_obj, (int, str)) else 0

        if depth > max_depth:
            continue

        if file_path in visited:
            continue

        visited.add(file_path)

        # Doc file content
        full_path = (workspace_path / file_path).resolve()
        if not full_path.exists():
            continue

        try:
            # Slice quanh error line
            slice_result = slice_file_by_line_range(
                full_path,
                start_line=max(1, line_num - 10),
                end_line=line_num + 10,
                context_padding=5,
                workspace_root=workspace_path,
            )

            content = slice_result.content
            tokens = tokenization_service.count_tokens(content)

            if tokens > token_budget_remaining:
                break

            token_budget_remaining -= tokens

            trace_steps.append(
                TraceStep(
                    file_path=file_path,
                    symbols=[],
                    content=content,
                    reason=f"Error at line {line_num}"
                    if depth == 0
                    else f"Dependency (depth {depth})",
                    depth=depth,
                )
            )

            # Mo rong: them dependencies vao queue
            if depth < max_depth:
                try:
                    related = resolver.get_related_files(full_path, max_depth=1)
                except Exception as e:
                    logger.warning(
                        "Failed to resolve dependencies for %s: %s", file_path, e
                    )
                    continue

                for dep_path in related:
                    try:
                        dep_rel = dep_path.relative_to(workspace_path).as_posix()
                        # Check ca visited VA queued de tranh duplicate
                        if dep_rel not in visited and dep_rel not in queued:
                            queue.append(
                                {"file": dep_rel, "line": 1, "depth": depth + 1}
                            )
                            queued.add(dep_rel)
                    except ValueError:
                        pass

        except Exception as e:
            logger.error(f"Error tracing {file_path}: {e}")
            continue

    return trace_steps
