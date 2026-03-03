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
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from services.interfaces.tokenization_service import ITokenizationService

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
        """Shortcut dem token cua mot doan text."""
        if not text:
            return 0
        return self._tok.count_tokens(text)

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

        # Tinh tong token hien tai
        current_total = self._estimate_total(components)
        result.actual_tokens = current_total

        # Level 0: Da fit, khong can trim
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

        # Level 1: Xoa dependency files, trim git
        result = self._trim_level1(result)
        if result.actual_tokens <= self._max_tokens:
            result.levels_applied = 1
            return result

        # Level 2: Smart degrade primary files (full -> truncated)
        result = self._trim_level2(result)
        if result.actual_tokens <= self._max_tokens:
            result.levels_applied = 2
            return result

        # Level 3: Truncate cac files lon nhat
        result = self._trim_level3(result)
        result.levels_applied = 3
        return result

    def _estimate_total(self, comp: PromptComponents) -> int:
        """
        Uoc tinh tong token cua tat ca components.

        Cong tong cac thanh phan rieng le + overhead.
        Nhanh hon count_tokens(full_prompt) vi khong can assemble lai.

        Args:
            comp: PromptComponents chua cac thanh phan

        Returns:
            Tong so token uoc tinh
        """
        total = comp.structure_overhead
        total += self._count(comp.instructions)
        total += self._count(comp.project_rules)
        total += self._count(comp.file_map)
        total += self._count(comp.git_diffs_text)
        total += self._count(comp.git_logs_text)
        for content in comp.file_contents.values():
            total += self._count(content)
        return total

    def _trim_level1(self, result: TrimResult) -> TrimResult:
        """
        Level 1: Xoa dependency files truoc, sau do trim git logs roi diffs.

        Dependency files co uu tien thap nhat nen bi cat truoc tien.
        Git logs bi cat truoc git diffs vi diffs huu ich hon cho context.

        Args:
            result: TrimResult hien tai

        Returns:
            TrimResult da cap nhat
        """
        comp = result.components

        # 1a. Xoa dependency files
        dep_paths = comp.dependency_paths
        if dep_paths:
            removed_deps = []
            for dp in list(dep_paths):
                if dp in comp.file_contents:
                    del comp.file_contents[dp]
                    removed_deps.append(dp)
            if removed_deps:
                result.notes.append(
                    f"Removed {len(removed_deps)} dependency files to fit budget: "
                    + ", ".join(removed_deps[:5])
                    + ("..." if len(removed_deps) > 5 else "")
                )
                comp.dependency_paths.clear()

        result.actual_tokens = self._estimate_total(comp)
        if result.actual_tokens <= self._max_tokens:
            return result

        # 1b. Trim git logs
        if comp.git_logs_text:
            result.notes.append("Removed git logs to fit budget.")
            comp.git_logs_text = ""

        result.actual_tokens = self._estimate_total(comp)
        if result.actual_tokens <= self._max_tokens:
            return result

        # 1c. Trim git diffs
        if comp.git_diffs_text:
            result.notes.append("Removed git diffs to fit budget.")
            comp.git_diffs_text = ""

        result.actual_tokens = self._estimate_total(comp)
        return result

    def _trim_level2(self, result: TrimResult) -> TrimResult:
        """
        Level 2: Cat ngan noi dung primary files (giu 30% dau + note).

        Ap dung tu file lon nhat truoc (greedy by token savings).
        Moi file bi cat giam se co dong ghi chu de AI biet context khong day du.

        Args:
            result: TrimResult hien tai

        Returns:
            TrimResult da cap nhat
        """
        comp = result.components

        # Sap xep files theo token count giam dan
        file_sizes: list[tuple[str, int]] = []
        for path, content in comp.file_contents.items():
            tokens = self._count(content)
            file_sizes.append((path, tokens))
        file_sizes.sort(key=lambda x: x[1], reverse=True)

        for path, original_tokens in file_sizes:
            if result.actual_tokens <= self._max_tokens:
                break

            content = comp.file_contents[path]
            # Giu 30% dau cua file
            keep_chars = max(200, len(content) // 3)
            truncated = content[:keep_chars]
            truncated += (
                f"\n\n[NOTE: File content trimmed to ~30% ({keep_chars} chars) to fit token budget. "
                f"Use read_file for full content.]"
            )
            comp.file_contents[path] = truncated

            new_tokens = self._count(truncated)
            saved = original_tokens - new_tokens
            result.notes.append(
                f"Trimmed {path}: {original_tokens:,} -> {new_tokens:,} tokens (saved {saved:,})"
            )

            result.actual_tokens = self._estimate_total(comp)

        return result

    def _trim_level3(self, result: TrimResult) -> TrimResult:
        """
        Level 3: Truncate manh hon - chi giu 100 ky tu dau + note.

        Day la muc cuoi cung. Neu van khong fit thi append warning note.

        Args:
            result: TrimResult hien tai

        Returns:
            TrimResult da cap nhat
        """
        comp = result.components

        for path in list(comp.file_contents.keys()):
            if result.actual_tokens <= self._max_tokens:
                break

            content = comp.file_contents[path]
            if len(content) <= 200:
                continue  # Da nho, skip

            truncated = content[:100]
            truncated += (
                f"\n[NOTE: File severely truncated to fit {self._max_tokens:,} token budget. "
                f"Use read_file to get full content.]"
            )
            comp.file_contents[path] = truncated
            result.notes.append(f"Severely truncated {path} to fit budget.")
            result.actual_tokens = self._estimate_total(comp)

        # Warning neu van vuot budget
        if result.actual_tokens > self._max_tokens:
            result.notes.append(
                f"WARNING: Could not fit within {self._max_tokens:,} token budget. "
                f"Current: {result.actual_tokens:,} tokens. "
                f"Consider reducing file count or increasing budget."
            )

        return result
