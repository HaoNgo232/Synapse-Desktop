"""
Token Budget Manager - Quản lý và tối ưu hóa token budget cho workflows.

Đảm bảo output prompt LUÔN fit trong giới hạn token của model.
Iterate qua nhiều strategy để giảm kích thước nếu vượt budget.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from application.interfaces.tokenization_port import ITokenizationService

from domain.workflow.shared.file_slicer import auto_slice_file
from domain.smart_context.parser import smart_parse

logger = logging.getLogger(__name__)


@dataclass
class BudgetAllocation:
    """
    Kết quả phân bổ token budget cho các thành phần.

    Attributes:
        instruction_budget: Tokens dành cho instructions + system prompt
        file_budget: Tokens dành cho file contents
        git_budget: Tokens dành cho git diffs/logs
        overhead_budget: Tokens overhead (XML tags, formatting)
        remaining: Tokens còn lại (buffer)
    """

    instruction_budget: int = 0
    file_budget: int = 0
    git_budget: int = 0
    overhead_budget: int = 0
    remaining: int = 0


@dataclass
class BudgetResult:
    """
    Kết quả sau khi fit content vào token budget.

    Attributes:
        file_contents: Map file_path -> content (đã optimize)
        total_tokens: Tổng tokens thực tế
        budget_used_pct: % budget đã sử dụng
        optimizations_applied: Danh sách các bước tối ưu đã áp dụng
        files_sliced: Danh sách files bị cắt
        files_smartified: Danh sách files chuyển sang Smart Context
    """

    file_contents: Dict[str, str] = field(default_factory=dict)
    total_tokens: int = 0
    budget_used_pct: float = 0.0
    optimizations_applied: List[str] = field(default_factory=list)
    files_sliced: List[str] = field(default_factory=list)
    files_smartified: List[str] = field(default_factory=list)


class TokenBudgetManager:
    """
    Quản lý token budget và tự động optimize content để fit.

    Áp dụng iterative strategy: thử full content trước,
    nếu vượt budget thì degrade từng bước cho đến khi fit.
    """

    def __init__(
        self,
        tokenization_service: "ITokenizationService",
        max_tokens: int,
    ) -> None:
        """
        Args:
            tokenization_service: Service đếm token (inject từ container)
            max_tokens: Giới hạn token tối đa
        """
        self._tok = tokenization_service
        self._max_tokens = max_tokens

    def fit_files_to_budget(
        self,
        primary_files: List[Path],
        dependency_files: List[Path],
        instructions: str,
        workspace_root: Path,
        relevant_symbols: Optional[Dict[str, Set[str]]] = None,
    ) -> BudgetResult:
        """
        Đọc files và tự động optimize để fit vào token budget.

        Strategy theo thứ tự ưu tiên:
        1. Đọc full content tất cả files
        2. Nếu vượt: chuyển dependency files sang Smart Context
        3. Nếu vẫn vượt: slice primary files theo relevant_symbols
        4. Nếu vẫn vượt: truncate files lớn nhất

        Args:
            primary_files: Files chính cần full content
            dependency_files: Files phụ thuộc (có thể degrade)
            instructions: User instructions
            workspace_root: Workspace root
            relevant_symbols: Optional map file -> symbols cần giữ

        Returns:
            BudgetResult với content đã optimize
        """
        relevant_symbols = relevant_symbols or {}

        # Quick estimate - neu estimate thap, thu doc full content
        estimated = self._quick_estimate(primary_files, dependency_files, instructions)
        if estimated <= self._max_tokens * 0.8:
            result = self._read_full_content(
                primary_files, dependency_files, instructions, workspace_root
            )
            # Verify actual tokens van nam trong budget
            # (quick_estimate co the sai vi dung heuristic 100 tokens/file)
            if result.total_tokens <= self._max_tokens:
                return result
            # Fall through to strategy chain neu actual vuot budget

        # Strategy 1: Full content
        result = self._try_full_content(
            primary_files, dependency_files, instructions, workspace_root
        )
        if result.total_tokens <= self._max_tokens:
            return result

        # Strategy 2: Smartify dependencies
        result = self._try_smartify_dependencies(
            primary_files, dependency_files, instructions, workspace_root
        )
        if result.total_tokens <= self._max_tokens:
            result.optimizations_applied.append("smartified_dependencies")
            return result

        # Strategy 3: Slice primary files
        result = self._try_slice_primary(
            primary_files,
            dependency_files,
            instructions,
            workspace_root,
            relevant_symbols,
        )
        if result.total_tokens <= self._max_tokens:
            result.optimizations_applied.extend(
                ["smartified_dependencies", "sliced_primary_files"]
            )
            return result

        # Strategy 4: Truncate largest files (hard limit enforced)
        result = self._try_truncate_largest(
            primary_files, dependency_files, instructions, workspace_root
        )
        result.optimizations_applied.extend(
            ["smartified_dependencies", "sliced_primary_files", "truncated_largest"]
        )
        return result

    def estimate_budget_allocation(
        self,
        instruction_text: str,
        file_count: int,
        include_git: bool = False,
    ) -> BudgetAllocation:
        """
        Ước tính phân bổ budget trước khi đọc files.

        Args:
            instruction_text: Nội dung instructions
            file_count: Số lượng files dự kiến
            include_git: Có bao gồm git diffs không

        Returns:
            BudgetAllocation với ước tính cho mỗi thành phần
        """
        instruction_tokens = self._tok.count_tokens(instruction_text)
        overhead = 500  # XML tags, formatting
        git_budget = 5000 if include_git else 0

        remaining = self._max_tokens - instruction_tokens - overhead - git_budget
        file_budget = max(0, remaining)

        return BudgetAllocation(
            instruction_budget=instruction_tokens,
            file_budget=file_budget,
            git_budget=git_budget,
            overhead_budget=overhead,
            remaining=max(0, remaining - file_budget),
        )

    def _quick_estimate(
        self, primary: List[Path], deps: List[Path], instructions: str
    ) -> int:
        """Quick estimate without reading files."""
        base = self._tok.count_tokens(instructions) + 500
        # Assume ~100 tokens per file on average
        return base + (len(primary) + len(deps)) * 100

    def _read_full_content(
        self,
        primary: List[Path],
        deps: List[Path],
        instructions: str,
        workspace_root: Path,
    ) -> BudgetResult:
        """Read full content for all files."""
        file_contents = {}
        total_tokens = self._tok.count_tokens(instructions) + 500

        for file_path in primary + deps:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                rel_path = file_path.relative_to(workspace_root).as_posix()
                file_contents[rel_path] = content
                total_tokens += self._tok.count_tokens(content)
            except Exception:
                pass

        return BudgetResult(
            file_contents=file_contents,
            total_tokens=total_tokens,
            budget_used_pct=(total_tokens / self._max_tokens) * 100,
        )

    def _try_full_content(
        self, primary: List[Path], deps: List[Path], instructions: str, ws: Path
    ) -> BudgetResult:
        """Strategy 1: Full content."""
        return self._read_full_content(primary, deps, instructions, ws)

    def _try_smartify_dependencies(
        self, primary: List[Path], deps: List[Path], instructions: str, ws: Path
    ) -> BudgetResult:
        """Strategy 2: Full primary, smart context cho deps.

        Đọc full content cho primary files, chuyển dependency files
        sang Smart Context (chỉ giữ signatures) để giảm tokens.
        Có logging khi smart_parse fail để dễ debug.
        """
        file_contents = {}
        total_tokens = self._tok.count_tokens(instructions) + 500
        smartified = []
        failed_deps = []

        # Full content cho primary files
        for file_path in primary:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                rel_path = file_path.relative_to(ws).as_posix()
                file_contents[rel_path] = content
                total_tokens += self._tok.count_tokens(content)
            except Exception:
                pass

        # Smart context cho dependency files
        for file_path in deps:
            rel_path = None
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                rel_path = file_path.relative_to(ws).as_posix()
                smart = smart_parse(str(file_path), content)
                if smart:
                    file_contents[rel_path] = smart
                    total_tokens += self._tok.count_tokens(smart)
                    smartified.append(rel_path)
                else:
                    logger.debug("smart_parse returned None for %s", rel_path)
                    failed_deps.append(rel_path)
            except UnicodeDecodeError:
                logger.debug("Binary file skipped: %s", rel_path or file_path)
            except Exception as e:
                logger.warning("Failed to smart_parse %s: %s", rel_path or file_path, e)
                if rel_path:
                    failed_deps.append(rel_path)

        if failed_deps and len(failed_deps) > len(deps) * 0.3:
            logger.warning(
                "smart_parse failed for %d/%d dependency files",
                len(failed_deps),
                len(deps),
            )

        return BudgetResult(
            file_contents=file_contents,
            total_tokens=total_tokens,
            budget_used_pct=(total_tokens / self._max_tokens) * 100,
            files_smartified=smartified,
        )

    def _try_slice_primary(
        self,
        primary: List[Path],
        deps: List[Path],
        instructions: str,
        ws: Path,
        relevant_symbols: Dict[str, Set[str]],
    ) -> BudgetResult:
        """Strategy 3: Slice primary files theo symbols, smart context cho deps.

        Enforce hard token limit - skip files nếu thêm vào sẽ vượt budget.
        """
        file_contents = {}
        total_tokens = self._tok.count_tokens(instructions) + 500
        sliced = []
        smartified = []

        # Slice primary files - enforce budget
        for file_path in primary:
            try:
                rel_path = file_path.relative_to(ws).as_posix()
                hints = relevant_symbols.get(rel_path, None)
                slice_result = auto_slice_file(file_path, hints, workspace_root=ws)
                content_tokens = self._tok.count_tokens(slice_result.content)

                # Enforce hard limit: skip nếu vượt budget
                if total_tokens + content_tokens > self._max_tokens:
                    continue

                file_contents[rel_path] = slice_result.content
                total_tokens += content_tokens
                if not slice_result.is_full_file:
                    sliced.append(rel_path)
            except Exception:
                pass

        # Smart context cho deps - enforce budget
        for file_path in deps:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                smart = smart_parse(str(file_path), content)
                if smart:
                    smart_tokens = self._tok.count_tokens(smart)

                    # Enforce hard limit: skip nếu vượt budget
                    if total_tokens + smart_tokens > self._max_tokens:
                        continue

                    rel_path = file_path.relative_to(ws).as_posix()
                    file_contents[rel_path] = smart
                    total_tokens += smart_tokens
                    smartified.append(rel_path)
            except Exception:
                pass

        return BudgetResult(
            file_contents=file_contents,
            total_tokens=total_tokens,
            budget_used_pct=(total_tokens / self._max_tokens) * 100,
            files_sliced=sliced,
            files_smartified=smartified,
        )

    def _try_truncate_largest(
        self, primary: List[Path], deps: List[Path], instructions: str, ws: Path
    ) -> BudgetResult:
        """Strategy 4: Truncate (slice) tất cả files + enforce hard token limit.

        Đây là strategy cuối cùng, mạnh tay nhất:
        - Slice mỗi file chỉ giữ 100 dòng đầu
        - Skip file nếu thêm vào sẽ vượt budget
        - Ưu tiên files nhỏ trước (sort ascending by size)
        """
        file_contents = {}
        total_tokens = self._tok.count_tokens(instructions) + 500

        # Combine tất cả files, sort ascending by size (files nhỏ trước)
        all_files = [(p, True) for p in primary] + [(p, False) for p in deps]
        all_files = [item for item in all_files if item[0].exists()]
        all_files.sort(key=lambda x: x[0].stat().st_size)

        for file_path, is_primary in all_files:
            try:
                rel_path = file_path.relative_to(ws).as_posix()
                slice_result = auto_slice_file(
                    file_path, max_lines=100, workspace_root=ws
                )
                content_tokens = self._tok.count_tokens(slice_result.content)

                # Enforce hard limit: skip nếu vượt budget
                if total_tokens + content_tokens > self._max_tokens:
                    continue

                file_contents[rel_path] = slice_result.content
                total_tokens += content_tokens
            except Exception:
                pass

        return BudgetResult(
            file_contents=file_contents,
            total_tokens=total_tokens,
            budget_used_pct=(total_tokens / self._max_tokens) * 100,
        )
