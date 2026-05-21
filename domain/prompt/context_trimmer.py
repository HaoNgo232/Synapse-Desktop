"""
Context Trimmer - Tu dong cat giam context khi prompt vuot token budget.

Module nay implement chien luoc trim theo thu tu uu tien ro rang:
1. Instructions + Project Rules + Structure tokens: LUON giu nguyen
2. Primary file contents: Uu tien cao
3. Git diffs/logs: Co the cat khi can
4. Dependency file contents: Uu tien thap nhat, cat truoc tien

Cac muc degrade:
- Level 0 (Full): Giu nguyen tat ca
- Level 1 (Trim deps + git): Loai bo dependency files, trim git logs/diffs
- Level 2 (Smart degrade): Chuyen primary files tu full -> signatures only
- Level 3 (Truncate): Cat bot files it quan trong nhat

Su dung: ContextTrimmer duoc goi tu PromptBuildService khi max_tokens set
va prompt vuot budget.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from application.interfaces.tokenization_port import ITokenizationService

logger = logging.getLogger(__name__)


@dataclass
class PromptComponents:
    """
    Cac thanh phan rieng le cua prompt truoc khi assemble.

    Tach prompt ra thanh tung phan de co the trim tung muc doc lap.

    Attributes:
        instructions: User instructions + profile prefix
        project_rules: Noi dung rules tu workspace
        file_map: Cau truc cay thu muc
        file_contents: Dict mapping display_path -> noi dung file
        git_diffs_text: Noi dung git diffs da format
        git_logs_text: Noi dung git logs da format
        structure_overhead: Token overhead cua XML tags va assembly
        dependency_paths: Set cac display_path la dependency files
    """

    instructions: str = ""
    project_rules: str = ""
    file_map: str = ""
    file_contents: Dict[str, str] = field(default_factory=dict)
    git_diffs_text: str = ""
    git_logs_text: str = ""
    structure_overhead: int = 0
    dependency_paths: set[str] = field(default_factory=set)
    protected_paths: set[str] = field(default_factory=set)
    """Paths that must never be removed or truncated regardless of token pressure."""


@dataclass
class TrimResult:
    """
    Ket qua sau khi trim context.

    Attributes:
        components: PromptComponents da duoc trim
        notes: Danh sach ghi chu mo ta nhung gi bi cat
        actual_tokens: So token uoc tinh sau trim
        levels_applied: So muc degrade da ap dung (0-3)
    """

    components: PromptComponents
    notes: List[str] = field(default_factory=list)
    actual_tokens: int = 0
    levels_applied: int = 0


class ContextTrimmer:
    """
    Tu dong cat giam context de prompt vua voi token budget.

    Su dung TokenizationService (DI) de dem token chinh xac.
    Ap dung chien luoc trim theo thu tu uu tien:
    dependencies -> git logs -> git diffs -> smart degrade primary files.
    """

    def __init__(
        self,
        tokenization_service: "ITokenizationService",
        max_tokens: int,
    ):
        """
        Khoi tao ContextTrimmer.

        Args:
            tokenization_service: Service dem token (inject tu ngoai)
            max_tokens: Gioi han token toi da cho prompt output
        """
        self._tok = tokenization_service
        self._max_tokens = max_tokens

    def _count(self, text: str) -> int:
        """Shortcut đếm token của một đoạn text."""
        if not text:
            return 0
        return self._tok.count_tokens(text)

    def _build_file_token_cache(self, comp: PromptComponents) -> Dict[str, int]:
        """
        Xây dựng cache token count cho từng file trong file_contents.
        Mỗi file chỉ được đếm một lần duy nhất để tránh O(N²).

        Args:
            comp: PromptComponents chứa file_contents

        Returns:
            Dict mapping display_path -> token count
        """
        return {
            path: self._count(content) for path, content in comp.file_contents.items()
        }

    def trim(self, components: PromptComponents) -> TrimResult:
        """
        Trim context de vua voi max_tokens budget.

        Ap dung cac level degrade tuan tu cho den khi fit:
        - Level 0: Khong trim (da fit)
        - Level 1: Xoa dependency files, trim git logs roi diffs
        - Level 2: Chuyen primary files sang signatures only
        - Level 3: Truncate cac files lon nhat

        Args:
            components: PromptComponents chua toan bo thanh phan prompt

        Returns:
            TrimResult voi components da trim va ghi chu
        """
        result = TrimResult(components=components)

        # Xây dựng cache token count một lần duy nhất - O(N)
        file_cache: Dict[str, int] = self._build_file_token_cache(components)

        # Tính tổng token hiện tại
        current_total = self._estimate_total(components, file_cache)
        result.actual_tokens = current_total

        # Level 0: Đã fit, không cần trim
        if current_total <= self._max_tokens:
            logger.info(
                "Context fits budget: %d <= %d tokens", current_total, self._max_tokens
            )
            return result

        logger.info(
            "Context exceeds budget: %d > %d tokens. Starting trim...",
            current_total,
            self._max_tokens,
        )

        # Level 1: Xóa dependency files, trim git
        result = self._trim_level1(result, file_cache)
        if result.actual_tokens <= self._max_tokens:
            result.levels_applied = 1
            return result

        # Level 2: Smart degrade primary files (full -> truncated)
        result = self._trim_level2(result, file_cache)
        if result.actual_tokens <= self._max_tokens:
            result.levels_applied = 2
            return result

        # Level 3: Truncate cac files lon nhat
        result = self._trim_level3(result, file_cache)
        result.levels_applied = 3
        return result

    def _estimate_total(
        self, comp: PromptComponents, file_token_cache: Optional[Dict[str, int]] = None
    ) -> int:
        """
        Ước tính tổng token của tất cả components.

        Nếu file_token_cache được cung cấp, sử dụng giá trị đã cache thay vì đếm lại.
        Điều này giảm độ phức tạp từ O(N) xuống O(1) khi cache hợp lệ.

        Args:
            comp: PromptComponents chứa các thành phần
            file_token_cache: Optional dict cache token count của từng file

        Returns:
            Tổng số token ước tính
        """
        total = comp.structure_overhead
        total += self._count(comp.instructions)
        total += self._count(comp.project_rules)
        total += self._count(comp.file_map)
        total += self._count(comp.git_diffs_text)
        total += self._count(comp.git_logs_text)
        if file_token_cache is not None:
            # Sử dụng cache - chỉ cộng các file còn lại trong file_contents
            for path in comp.file_contents:
                total += file_token_cache.get(path, 0)
        else:
            for content in comp.file_contents.values():
                total += self._count(content)
        return total

    def _trim_level1(
        self, result: TrimResult, file_cache: Dict[str, int]
    ) -> TrimResult:
        """
        Level 1: Xóa dependency files trước, sau đó trim git logs rồi diffs.
        Cập nhật file_cache khi xóa file để tránh đếm lại.

        Args:
            result: TrimResult hiện tại
            file_cache: Dict cache token count từng file

        Returns:
            TrimResult đã cập nhật
        """
        comp = result.components

        # 1a. Xóa dependency files
        dep_paths = comp.dependency_paths
        if dep_paths:
            removed_deps = []
            for dp in list(dep_paths):
                if dp in comp.protected_paths:
                    continue  # Never remove explicitly selected (protected) files
                if dp in comp.file_contents:
                    del comp.file_contents[dp]
                    file_cache.pop(dp, None)  # Cập nhật cache
                    removed_deps.append(dp)
            if removed_deps:
                result.notes.append(
                    f"Removed {len(removed_deps)} dependency files to fit budget: "
                    + ", ".join(removed_deps[:5])
                    + ("..." if len(removed_deps) > 5 else "")
                )
                comp.dependency_paths.clear()

        result.actual_tokens = self._estimate_total(comp, file_cache)
        if result.actual_tokens <= self._max_tokens:
            return result

        # 1b. Trim git logs
        if comp.git_logs_text:
            result.notes.append("Removed git logs to fit budget.")
            comp.git_logs_text = ""

        result.actual_tokens = self._estimate_total(comp, file_cache)
        if result.actual_tokens <= self._max_tokens:
            return result

        # 1c. Trim git diffs
        if comp.git_diffs_text:
            result.notes.append("Removed git diffs to fit budget.")
            comp.git_diffs_text = ""

        result.actual_tokens = self._estimate_total(comp, file_cache)
        return result

    def _trim_level2(
        self, result: TrimResult, file_cache: Dict[str, int]
    ) -> TrimResult:
        """
        Level 2: Chuyển primary files sang Smart Context (AST signatures) thay vì cắt text mù.
        Cập nhật file_cache sau mỗi lần degrade để tránh đếm lại O(N).

        Args:
            result: TrimResult hiện tại
            file_cache: Dict cache token count từng file

        Returns:
            TrimResult đã cập nhật
        """
        from pathlib import Path as _Path
        from domain.smart_context import smart_parse, is_supported

        comp = result.components

        # Sắp xếp files theo token count giảm dần (dùng cache đã có)
        file_sizes: list[tuple[str, int]] = [
            (path, file_cache.get(path, self._count(content)))
            for path, content in comp.file_contents.items()
        ]
        file_sizes.sort(key=lambda x: x[1], reverse=True)

        for path, original_tokens in file_sizes:
            if result.actual_tokens <= self._max_tokens:
                break

            if path in comp.protected_paths:
                continue  # Skip files marked as protected — never degrade them

            content = comp.file_contents[path]
            ext = _Path(path).suffix.lstrip(".")

            # Thử smart context trước (AST signatures - giữ logic nghiệp vụ)
            if is_supported(ext):
                try:
                    smart_content = smart_parse(
                        path, content, include_relationships=False
                    )
                    if smart_content:
                        new_content = (
                            smart_content
                            + "\n\n[NOTE: Converted to Smart Context (AST signatures only) to fit token budget.]"
                        )
                        comp.file_contents[path] = new_content
                        new_tokens = self._count(new_content)
                        file_cache[path] = new_tokens  # Cập nhật cache
                        result.notes.append(
                            f"Smart Context {path}: {original_tokens:,} -> {new_tokens:,} tokens"
                        )
                        result.actual_tokens = self._estimate_total(comp, file_cache)
                        continue
                except Exception:
                    pass  # Fallback về truncate

            # Fallback: Giữ 30% đầu của file
            keep_chars = max(200, len(content) // 3)
            truncated = content[:keep_chars]
            truncated += (
                f"\n\n[NOTE: File content trimmed to ~30% ({keep_chars} chars) to fit token budget. "
                f"Use read_file for full content.]"
            )
            comp.file_contents[path] = truncated

            new_tokens = self._count(truncated)
            file_cache[path] = new_tokens  # Cập nhật cache
            saved = original_tokens - new_tokens
            result.notes.append(
                f"Trimmed {path}: {original_tokens:,} -> {new_tokens:,} tokens (saved {saved:,})"
            )

            result.actual_tokens = self._estimate_total(comp, file_cache)

        return result

    def _trim_level3(
        self, result: TrimResult, file_cache: Dict[str, int]
    ) -> TrimResult:
        """
        Level 3: Truncate mạnh hơn - chỉ giữ 800 ký tự đầu + note.
        Cập nhật file_cache sau mỗi lần truncate.

        Args:
            result: TrimResult hiện tại
            file_cache: Dict cache token count từng file

        Returns:
            TrimResult đã cập nhật
        """
        comp = result.components

        for path in list(comp.file_contents.keys()):
            if result.actual_tokens <= self._max_tokens:
                break

            if path in comp.protected_paths:
                continue  # Skip files marked as protected — last resort still respects them

            content = comp.file_contents[path]
            if len(content) <= 200:
                continue  # Đã nhỏ, skip

            truncated = content[:800]
            truncated += (
                f"\n[NOTE: File severely truncated to fit {self._max_tokens:,} token budget. "
                f"Use read_file to get full content.]"
            )
            comp.file_contents[path] = truncated
            new_tokens = self._count(truncated)
            file_cache[path] = new_tokens  # Cập nhật cache
            result.notes.append(f"Severely truncated {path} to fit budget.")
            result.actual_tokens = self._estimate_total(comp, file_cache)

        # Warning nếu vẫn vượt budget
        if result.actual_tokens > self._max_tokens:
            result.notes.append(
                f"WARNING: Could not fit within {self._max_tokens:,} token budget. "
                f"Current: {result.actual_tokens:,} tokens. "
                f"Consider reducing file count or increasing budget."
            )

        return result
