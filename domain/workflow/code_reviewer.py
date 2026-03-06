"""
Code Review Workflow - Deep review bằng AI với full surrounding context.

Khác với review đơn giản (chỉ đọc diff), workflow này:
1. Pull git diff (staged + unstaged)
2. Parse diff để xác định files và symbols đã thay đổi
3. Kéo thêm surrounding context files (imports, callers, tests)
4. Tạo comprehensive review prompt
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from core.workflows.shared.scope_detector import detect_scope_from_git_diff
from core.workflows.shared.token_budget_manager import TokenBudgetManager
from core.workflows.shared.handoff_formatter import HandoffContext, format_handoff_xml
from core.utils.git_utils import get_git_diffs, GitDiffResult
from services.tokenization_service import TokenizationService
from services.workspace_index import collect_files_from_disk

logger = logging.getLogger(__name__)


@dataclass
class ReviewResult:
    """
    Kết quả của Code Review workflow.

    Attributes:
        prompt: Review prompt hoàn chỉnh
        total_tokens: Tổng tokens
        files_changed: Số files có thay đổi trong diff
        files_context: Số files surrounding context được thêm
        diff_stats: Thống kê diff (insertions, deletions)
        changed_symbols: Danh sách symbols đã thay đổi
    """

    prompt: str = ""
    total_tokens: int = 0
    files_changed: int = 0
    files_context: int = 0
    diff_stats: Dict[str, int] = field(default_factory=dict)
    changed_symbols: List[str] = field(default_factory=list)


def run_code_review(
    workspace_path: str,
    review_focus: str = "",
    include_tests: bool = True,
    include_callers: bool = True,
    max_tokens: int = 120_000,
    base_ref: Optional[str] = None,
    tokenization_service: Optional[TokenizationService] = None,
) -> ReviewResult:
    """
    Chạy Code Review workflow.

    Args:
        workspace_path: Absolute path to workspace
        review_focus: Optional focus area (e.g., "security", "performance")
        include_tests: Kéo test files liên quan (default True)
        include_callers: Kéo files gọi các changed symbols (default True)
        max_tokens: Token budget (default 120k)
        base_ref: Optional git ref để diff against (default: HEAD/working tree)
        tokenization_service: Optional TokenizationService

    Returns:
        ReviewResult với review prompt và metadata
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        raise ValueError(f"'{workspace_path}' is not a valid directory")

    tok_service = tokenization_service or TokenizationService()

    # Step 1: Pull git diff
    try:
        diff_result = get_git_diffs(ws)
        if not diff_result:
            return ReviewResult(
                prompt="[No changes detected in git diff]",
                files_changed=0,
            )

        # Parse diff to get changed files
        diffs = []
        # Simple parsing: extract file paths from diff headers

        for line in (diff_result.work_tree_diff + diff_result.staged_diff).splitlines():
            if line.startswith("diff --git"):
                # Parse filename tu git diff header: "diff --git a/X b/Y"
                # Tim vi tri cuoi cung cua " b/" de handle paths chua "b/"
                filename = _extract_filename_from_diff_header(line)
                if filename:
                    diffs.append({"file": filename})

        if not diffs:
            return ReviewResult(
                prompt="[No file changes detected in diff]",
                files_changed=0,
            )
    except Exception as e:
        logger.error(f"Error getting git diff: {e}")
        return ReviewResult(
            prompt=f"[Error getting git diff: {e}]",
            files_changed=0,
        )

    # Step 2: Detect scope from diff
    scope = detect_scope_from_git_diff(ws, max_depth=1)

    if not scope.primary_files:
        return ReviewResult(
            prompt="[No files detected in diff scope]",
            files_changed=0,
        )

    # Step 3: Find test files
    test_files = []
    if include_tests:
        test_files = _find_test_files(ws, scope.primary_files)

    # Step 4: Find callers (simplified - just add dependencies)
    caller_files = scope.dependency_files if include_callers else []

    # Step 5: Optimize content to fit budget
    budget_mgr = TokenBudgetManager(tok_service, max_tokens)

    primary_paths = [ws / p for p in scope.primary_files]
    context_paths = [ws / p for p in (caller_files + test_files)]

    # Build diff summary
    diff_summary = _build_diff_summary(diff_result)

    budget_result = budget_mgr.fit_files_to_budget(
        primary_files=primary_paths,
        dependency_files=context_paths,
        instructions=f"Code Review{': ' + review_focus if review_focus else ''}\n\n{diff_summary}",
        workspace_root=ws,
        relevant_symbols=scope.relevant_symbols,
    )

    # Step 6: Assemble review prompt
    action_instructions = (
        "Review the code changes carefully. Check for:\n"
        "- Correctness and logic errors\n"
        "- Security vulnerabilities\n"
        "- Performance issues\n"
        "- Code style and best practices\n"
        "- Test coverage\n"
    )

    if review_focus:
        action_instructions += f"\nFocus area: {review_focus}"

    context = HandoffContext(
        task_description=f"Code Review\n\n{diff_summary}",
        file_contents=budget_result.file_contents,
        file_map="",
        relationships="",
        action_instructions=action_instructions,
        metadata={
            "files_changed": len(scope.primary_files),
            "files_context": len(caller_files) + len(test_files),
            "total_tokens": budget_result.total_tokens,
        },
    )

    prompt = format_handoff_xml(context)
    total_tokens = tok_service.count_tokens(prompt)

    # Extract changed symbols
    changed_symbols = []
    for file_path in scope.primary_files:
        if file_path in scope.relevant_symbols:
            changed_symbols.extend(scope.relevant_symbols[file_path])

    return ReviewResult(
        prompt=prompt,
        total_tokens=total_tokens,
        files_changed=len(scope.primary_files),
        files_context=len(caller_files) + len(test_files),
        diff_stats={"insertions": 0, "deletions": 0},  # TODO: parse from diff
        changed_symbols=changed_symbols,
    )


def _find_test_files(
    workspace_path: Path,
    source_files: List[str],
) -> List[str]:
    """
    Tìm test files tương ứng với source files.

    Strategy:
    - Python: test_<name>.py hoặc <name>_test.py trong tests/
    - JS/TS: <name>.test.ts hoặc <name>.spec.ts

    Args:
        workspace_path: Workspace root
        source_files: Danh sách relative paths của source files

    Returns:
        Danh sách relative paths của test files tìm được
    """
    test_files = []
    all_files = collect_files_from_disk(workspace_path, workspace_path=workspace_path)

    for source_file in source_files:
        source_path = Path(source_file)
        stem = source_path.stem
        ext = source_path.suffix

        # Python patterns
        if ext == ".py":
            patterns = [
                f"test_{stem}.py",
                f"{stem}_test.py",
                f"tests/test_{stem}.py",
                f"tests/{stem}_test.py",
            ]
        # JS/TS patterns
        elif ext in [".js", ".ts", ".jsx", ".tsx"]:
            patterns = [
                f"{stem}.test{ext}",
                f"{stem}.spec{ext}",
            ]
        else:
            continue

        # Search for matching test files
        for file_path_str in all_files:
            file_path = Path(file_path_str)
            if any(
                file_path.name == pattern or str(file_path).endswith(pattern)
                for pattern in patterns
            ):
                try:
                    rel_path = file_path.relative_to(workspace_path).as_posix()
                    if rel_path not in test_files:
                        test_files.append(rel_path)
                except ValueError:
                    pass

    return test_files


def _extract_filename_from_diff_header(line: str) -> Optional[str]:
    """Trich xuat filename tu git diff header.

    Handle cac edge case:
    - Normal: 'diff --git a/src/main.py b/src/main.py'
    - Path chua 'b/': 'diff --git a/sub/b/test.py b/sub/b/test.py'
    - Rename: 'diff --git a/old.py b/new.py'

    Su dung " b/" (co space phia truoc) de tim boundary chinh xac.
    """
    # Tim vi tri cuoi cung cua " b/" de handle paths chua "b/"
    marker = " b/"
    idx = line.rfind(marker)
    if idx >= 0:
        return line[idx + len(marker) :]
    return None


def _build_diff_summary(diff_result: "GitDiffResult") -> str:
    """Build human-readable diff summary tu GitDiffResult."""
    changed_files = set()
    for line in (diff_result.work_tree_diff + diff_result.staged_diff).splitlines():
        if line.startswith("diff --git"):
            filename = _extract_filename_from_diff_header(line)
            if filename:
                changed_files.add(filename)

    if not changed_files:
        return "No changes"

    lines = ["Git Diff Summary:", ""]
    for file_path in sorted(changed_files)[:10]:  # Limit to 10 files
        lines.append(f"  {file_path}")

    if len(changed_files) > 10:
        lines.append(f"... and {len(changed_files) - 10} more files")

    return "\n".join(lines)
