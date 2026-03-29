"""
PromptBuildService - Concrete implementation cua IPromptBuilder.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Set, Tuple, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from application.interfaces.tokenization_port import ITokenizationService
    from domain.relationships.port import IRelationshipGraphProvider

from domain.prompt.generator import (
    generate_file_map,
    generate_file_contents_xml,
    generate_file_contents_json,
    generate_file_contents_plain,
    OutputStyle,
)
from infrastructure.filesystem.file_utils import TreeItem
from shared.types.prompt_types_extra import BuildResult
from application.services.prompt_helpers import (
    count_per_file_tokens,
    calculate_prompt_breakdown,
    apply_context_trimming,
    build_smart_context_prompt,
    compute_semantic_index,
)


# Mapping output_format string -> OutputStyle enum
_FORMAT_TO_STYLE = {
    "xml": OutputStyle.XML,
    "json": OutputStyle.JSON,
    "plain": OutputStyle.PLAIN,
}

# Mapping output_format string -> content generator function
_FORMAT_TO_GENERATOR = {
    "xml": generate_file_contents_xml,
    "json": generate_file_contents_json,
    "plain": generate_file_contents_plain,
}


logger = logging.getLogger(__name__)


class PromptBuildService:
    """
    Build prompt tu file paths va settings.

    Khong co state internal - moi call doc lap.
    Thread-safe vi khong mutate state.
    """

    def __init__(
        self,
        tokenization_service: Optional["ITokenizationService"] = None,
        graph_service: Optional["IRelationshipGraphProvider"] = None,
    ):
        if tokenization_service is None:
            from infrastructure.adapters.encoder_registry import (
                get_tokenization_service,
            )

            tokenization_service = get_tokenization_service()
        self._tokenization_service = tokenization_service
        # GraphService de tinh project structure metadata (optional)
        self._graph_service = graph_service

    def build_prompt(
        self,
        file_paths: List[Path],
        workspace: Path,
        instructions: str,
        output_format: str,
        include_git_changes: bool,
        use_relative_paths: bool,
        tree_item: Optional[TreeItem] = None,
        selected_paths: Optional[Set[str]] = None,
        include_xml_formatting: bool = False,
        codemap_paths: Optional[Set[str]] = None,
        instructions_at_top: bool = False,
        full_tree: bool = False,
    ) -> Tuple[str, int, Dict[str, int]]:
        """
        Generate prompt theo output format (backward-compatible API).

        Gọi nội bộ build_prompt_full() và chuyển đổi kết quả
        về tuple 3 phần tử để tương thích với code cũ.

        Args:
            file_paths: Danh sách file paths đã resolve
            workspace: Workspace root path
            instructions: User instructions text
            output_format: "xml", "json", "plain", hoặc "smart"
            include_git_changes: Có include git diff không
            use_relative_paths: Có dùng relative paths không
            tree_item: Root TreeItem cho file map (optional)
            selected_paths: Set paths đã chọn cho file map (optional)
            include_xml_formatting: Có bao gồm OPX không
            codemap_paths: Optional set các file paths chỉ lấy AST signatures.
                           Các file trong set này sẽ được xuất dạng codemap
                           thay vì full content.
            instructions_at_top: Di chuyển instructions lên đầu

        Returns:
            Tuple (prompt_text, token_count, breakdown)
        """
        result = self.build_prompt_full(
            file_paths=file_paths,
            workspace=workspace,
            instructions=instructions,
            output_format=output_format,
            include_git_changes=include_git_changes,
            use_relative_paths=use_relative_paths,
            tree_item=tree_item,
            selected_paths=selected_paths,
            include_xml_formatting=include_xml_formatting,
            codemap_paths=codemap_paths,
            instructions_at_top=instructions_at_top,
            full_tree=full_tree,
        )
        return result.to_legacy_tuple()

    def build_prompt_full(
        self,
        file_paths: List[Path],
        workspace: Path,
        instructions: str,
        output_format: str,
        include_git_changes: bool,
        use_relative_paths: bool,
        tree_item: Optional[TreeItem] = None,
        selected_paths: Optional[Set[str]] = None,
        include_xml_formatting: bool = False,
        dependency_files: Optional[List[Path]] = None,
        profile: Optional[str] = None,
        max_tokens: Optional[int] = None,
        codemap_paths: Optional[Set[str]] = None,
        instructions_at_top: bool = False,
        full_tree: bool = False,
    ) -> BuildResult:
        """
        Generate prompt và trả về BuildResult đầy đủ với metadata.

        Đây là API chính cho multi-agent workflow. Trả về BuildResult
        bao gồm per-file token counts, breakdown, trim notes, và
        dependency graph metadata.

        Args:
            file_paths: Danh sách primary file paths đã resolve
            workspace: Workspace root path
            instructions: User instructions text
            output_format: "xml", "json", "plain", hoặc "smart"
            include_git_changes: Có include git diff không
            use_relative_paths: Có dùng relative paths không
            tree_item: Root TreeItem cho file map (optional)
            selected_paths: Set paths đã chọn cho file map (optional)
            include_xml_formatting: Có bao gồm OPX không
            dependency_files: Danh sách dependency file paths (Feature 3)
            profile: Tên profile đã áp dụng (Feature 1, chỉ để lưu metadata)
            max_tokens: Giới hạn token tối đa (None = không giới hạn)
            codemap_paths: Optional set các file paths chỉ lấy AST signatures.
                           Có thể là absolute paths. Các file này sẽ được render
                           dạng codemap (function/class signatures) thay vì full content.
                           Trong output_format="smart", tham số này không có tác dụng
                           vì smart format đã là codemap-only.
            instructions_at_top: Di chuyển instructions lên đầu
            full_tree: Nếu True, hiển thị toàn bộ sơ đồ thư mục của workspace.
                       Nếu False (mặc định), chỉ hiển thị các file được chọn.

        Returns:
            BuildResult voi tat ca metadata can thiet
        """
        # Gop tat ca files: primary + dependencies
        all_file_paths = list(file_paths)
        dep_path_set: set[str] = set()
        if dependency_files:
            for dp in dependency_files:
                if dp not in all_file_paths:
                    all_file_paths.append(dp)
                dep_path_set.add(str(dp))

        # Normalize codemap_paths: dam bao la set[str] cua absolute paths
        normalized_codemap: Optional[Set[str]] = None
        if codemap_paths:
            normalized_codemap = set()
            for cp in codemap_paths:
                cp_path = Path(cp)
                if cp_path.is_absolute():
                    cp_path = cp_path.resolve()
                else:
                    cp_path = (workspace / cp).resolve()
                normalized_codemap.add(str(cp_path))

        # Initialize variables de tranh loi uninitialized
        file_map = ""
        project_rules = ""
        git_diffs = None
        git_logs = None
        file_contents = ""
        semantic_index = ""
        output_style = _FORMAT_TO_STYLE["xml"]

        if output_format == "smart":
            prompt, smart_contents = build_smart_context_prompt(
                all_file_paths,
                workspace,
                instructions,
                include_git_changes,
                use_relative_paths,
                self._graph_service,
                tree_item,
                selected_paths,
                instructions_at_top=instructions_at_top,
                full_tree=full_tree,
            )
            self._last_smart_contents = smart_contents
        else:
            # 0. Fetch git data neu can
            if include_git_changes:
                from infrastructure.git.git_utils import get_git_diffs, get_git_logs

                git_diffs = get_git_diffs(workspace)
                git_logs = get_git_logs(workspace, max_commits=5)

            # 1. Generate file map
            if tree_item:
                _sel = selected_paths if selected_paths is not None else set()
                if output_format in ("xml", "json"):
                    from domain.prompt.generator import generate_file_structure_xml

                    file_map = generate_file_structure_xml(
                        tree_item,
                        _sel,
                        workspace_root=workspace,
                        use_relative_paths=use_relative_paths,
                        show_all=full_tree,
                    )
                else:
                    from domain.prompt.generator import generate_file_map

                    file_map = generate_file_map(
                        tree_item,
                        _sel,
                        workspace_root=workspace,
                        use_relative_paths=use_relative_paths,
                        show_all=full_tree,
                    )

            # 2. Load Project Rules
            from application.services.workspace_rules import get_rule_file_contents

            project_rules = get_rule_file_contents(workspace)

            # 3. Generate file contents
            all_path_strs = {str(p) for p in all_file_paths}
            content_gen = _FORMAT_TO_GENERATOR.get(
                output_format, _FORMAT_TO_GENERATOR["xml"]
            )
            file_contents = content_gen(
                selected_paths=all_path_strs,
                workspace_root=workspace,
                use_relative_paths=use_relative_paths,
                codemap_paths=normalized_codemap,
            )

            # 4. Assemble prompt
            output_style = _FORMAT_TO_STYLE.get(output_format, _FORMAT_TO_STYLE["xml"])
            semantic_index = compute_semantic_index(
                workspace, self._graph_service, output_format
            )

            from domain.prompt.generator import generate_prompt

            prompt = generate_prompt(
                file_map=file_map,
                file_contents=file_contents,
                user_instructions=instructions,
                output_style=output_style,
                include_xml_formatting=include_xml_formatting,
                git_diffs=git_diffs,
                git_logs=git_logs,
                project_rules=project_rules,
                workspace_root=workspace,
                instructions_at_top=instructions_at_top,
                semantic_index=semantic_index,
            )

        token_count = self._tokenization_service.count_tokens(prompt)

        # 5. Build breakdown
        breakdown = calculate_prompt_breakdown(
            instructions,
            file_map,
            project_rules,
            git_diffs,
            git_logs,
            file_contents,
            include_git_changes,
            include_xml_formatting,
            self._tokenization_service,
            output_format,
            token_count,
        )

        if output_format == "smart":
            breakdown["content_tokens"] = self._tokenization_service.count_tokens(
                getattr(self, "_last_smart_contents", "")
            )

        # 6. Per-file token counting
        per_file_tokens = count_per_file_tokens(
            all_file_paths,
            workspace,
            use_relative_paths,
            dep_path_set,
            self._tokenization_service,
            codemap_paths=normalized_codemap,
        )

        # 7. Auto-trim
        trimmed = False
        trimmed_notes: list[str] = []

        if max_tokens is not None and token_count > max_tokens:
            prompt_trimmed, notes = apply_context_trimming(
                max_tokens,
                all_file_paths,
                workspace,
                use_relative_paths,
                dep_path_set,
                instructions,
                project_rules,
                file_map,
                git_diffs,
                git_logs,
                breakdown,
                self._tokenization_service,
                output_format,
                include_xml_formatting,
                instructions_at_top,
                semantic_index,
                output_style,
            )
            if notes:
                trimmed = True
                trimmed_notes = notes
                prompt = prompt_trimmed
                token_count = self._tokenization_service.count_tokens(prompt)
                # Re-count per-file tokens after trimming
                per_file_tokens = count_per_file_tokens(
                    all_file_paths,
                    workspace,
                    use_relative_paths,
                    dep_path_set,
                    self._tokenization_service,
                    codemap_paths=normalized_codemap,
                )

        # Tao BuildResult day du
        return BuildResult(
            prompt_text=prompt,
            total_tokens=token_count,
            file_count=len(all_file_paths),
            format=output_format,
            profile=profile,
            trimmed=trimmed,
            trimmed_notes=trimmed_notes,
            breakdown=breakdown,
            files=per_file_tokens,
            dependency_graph=None,
        )

    def count_tokens(self, text: str) -> int:
        """Dem so luong tokens trong text."""
        return self._tokenization_service.count_tokens(text)

    def build_file_map(
        self,
        tree_item: TreeItem,
        selected_paths: Set[str],
        workspace: Optional[Path] = None,
        use_relative_paths: bool = False,
    ) -> str:
        """
        Generate file map tu TreeItem va selected paths.
        """

        return generate_file_map(
            tree_item,
            selected_paths,
            workspace_root=workspace,
            use_relative_paths=use_relative_paths,
        )
