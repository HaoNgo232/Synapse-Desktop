"""
PromptBuildService - Concrete implementation cua IPromptBuilder.

Tach logic prompt building ra khoi CopyActionsMixin thanh service doc lap.
Delegate den core.prompt_generator cho logic thuc su,
nhung wrap lai trong mot API don gian va testable.

Note: build_prompt() la high-level API nhan file_paths va settings,
noi bo se goi cac functions cu the tu core.prompt_generator theo
dung signatures cua chung.

build_prompt_full() la API mo rong tra ve BuildResult voi metadata day du
(per-file token counts, trim notes, dependency graph) phuc vu multi-agent workflow.
"""

import logging
from pathlib import Path
from typing import List, Optional, Set, Tuple, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from application.interfaces.tokenization_port import ITokenizationService

from domain.prompt.generator import (
    generate_file_map,
    generate_file_contents_xml,
    generate_file_contents_json,
    generate_file_contents_plain,
    generate_prompt,
    generate_smart_context,
    build_smart_prompt,
    OutputStyle,
)
from domain.prompt.file_collector import collect_files
from infrastructure.filesystem.file_utils import TreeItem
from infrastructure.git.git_utils import get_git_diffs, get_git_logs
from shared.types.prompt_types_extra import BuildResult, FileTokenInfo


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


class PromptBuildService:
    """
    Build prompt tu file paths va settings.

    Khong co state internal - moi call doc lap.
    Thread-safe vi khong mutate state.
    """

    def __init__(
        self,
        tokenization_service: Optional["ITokenizationService"] = None,
    ):
        if tokenization_service is None:
            from infrastructure.adapters.encoder_registry import (
                get_tokenization_service,
            )

            tokenization_service = get_tokenization_service()
        self._tokenization_service = tokenization_service

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

        # Initialize variables de tranh loi uninitialized trong breakdown
        file_map = ""
        project_rules = ""
        git_diffs = None
        git_logs = None
        file_contents = ""

        if output_format == "smart":
            prompt = self._build_smart(
                all_file_paths,
                workspace,
                instructions,
                include_git_changes,
                use_relative_paths,
                tree_item,
                selected_paths,
                instructions_at_top=instructions_at_top,
                full_tree=full_tree,
            )
        else:
            # 0. Fetch git data neu can
            if include_git_changes:
                git_diffs = get_git_diffs(workspace)
                git_logs = get_git_logs(workspace, max_commits=5)

            # 1. Generate file map (with all paths including rules)
            if tree_item:
                _sel = selected_paths if selected_paths is not None else set()
                if output_format == "xml":
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

            # 2. Load Project Rules from workspace
            from application.services.workspace_rules import get_rule_file_contents

            project_rules = get_rule_file_contents(workspace)

            # 3. Generate file contents using all selected paths
            #    Truyen codemap_paths de tach full vs codemap-only
            all_path_strs = {str(p) for p in all_file_paths}

            content_gen = _FORMAT_TO_GENERATOR.get(
                output_format, generate_file_contents_xml
            )
            file_contents = content_gen(
                selected_paths=all_path_strs,
                workspace_root=workspace,
                use_relative_paths=use_relative_paths,
                codemap_paths=normalized_codemap,
            )

            # 4. Assemble prompt voi git data va xml formatting
            output_style = _FORMAT_TO_STYLE.get(output_format, OutputStyle.XML)
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
            )

        token_count = self._tokenization_service.count_tokens(prompt)

        # Build breakdown dict
        breakdown = {
            "instruction_tokens": self._tokenization_service.count_tokens(instructions)
            if instructions
            else 0,
            "tree_tokens": self._tokenization_service.count_tokens(file_map)
            if file_map
            else 0,
            "rule_tokens": self._tokenization_service.count_tokens(project_rules)
            if project_rules
            else 0,
            "diff_tokens": (
                self._tokenization_service.count_tokens(
                    (git_diffs.work_tree_diff + git_diffs.staged_diff)
                    if git_diffs
                    else ""
                )
                + self._tokenization_service.count_tokens(
                    git_logs.log_content if git_logs else ""
                )
            )
            if include_git_changes
            else 0,
        }

        if output_format == "smart":
            # Smart context dung build_smart_prompt, khong co OPX
            breakdown["content_tokens"] = self._tokenization_service.count_tokens(
                getattr(self, "_last_smart_contents", "")
            )
            breakdown["opx_tokens"] = 0
        else:
            breakdown["content_tokens"] = self._tokenization_service.count_tokens(
                file_contents
            )
            opx_t = 0
            if include_xml_formatting:
                try:
                    from domain.prompt.opx_instruction import (
                        XML_FORMATTING_INSTRUCTIONS,
                    )

                    opx_t = self._tokenization_service.count_tokens(
                        XML_FORMATTING_INSTRUCTIONS
                    )
                except ImportError:
                    opx_t = 0
            breakdown["opx_tokens"] = opx_t

        # Tinh structure tokens (overhead cua tags va assembly)
        sum_parts = sum(breakdown.values())
        breakdown["structure_tokens"] = max(0, token_count - sum_parts)

        # ====================================================================
        # Per-file token counting - dem token cho tung file rieng le
        # ====================================================================
        per_file_tokens = self._count_per_file_tokens(
            all_file_paths,
            workspace,
            use_relative_paths,
            dep_path_set,
            codemap_paths=normalized_codemap,
        )

        # ====================================================================
        # Auto-trim: cat giam context khi vuot max_tokens budget
        # ====================================================================
        trimmed = False
        trimmed_notes: list[str] = []

        if max_tokens is not None and token_count > max_tokens:
            from domain.prompt.context_trimmer import (
                ContextTrimmer,
                PromptComponents,
            )

            # Thu thap per-file contents de trimmer xu ly
            file_content_dict: Dict[str, str] = {}
            dep_display_paths: set[str] = set()
            entries = collect_files(
                selected_paths={str(p) for p in all_file_paths},
                workspace_root=workspace,
                use_relative_paths=use_relative_paths,
            )
            protected_display_paths: set[str] = set()
            for entry in entries:
                if entry.content is not None:
                    file_content_dict[entry.display_path] = entry.content
                    if str(entry.path) in dep_path_set:
                        dep_display_paths.add(entry.display_path)
                    else:
                        # File explicitly selected by user — protect from trimming
                        protected_display_paths.add(entry.display_path)

            git_diffs_text = ""
            git_logs_text = ""
            if git_diffs:
                git_diffs_text = (git_diffs.work_tree_diff or "") + (
                    git_diffs.staged_diff or ""
                )
            if git_logs:
                git_logs_text = git_logs.log_content or ""

            components = PromptComponents(
                instructions=instructions,
                project_rules=project_rules,
                file_map=file_map,
                file_contents=file_content_dict,
                git_diffs_text=git_diffs_text,
                git_logs_text=git_logs_text,
                structure_overhead=breakdown.get("structure_tokens", 0)
                + breakdown.get("opx_tokens", 0),
                dependency_paths=dep_display_paths,
                protected_paths=protected_display_paths,
            )

            trimmer = ContextTrimmer(self._tokenization_service, max_tokens)
            trim_result = trimmer.trim(components)

            if trim_result.levels_applied > 0:
                trimmed = True
                trimmed_notes = trim_result.notes

                # Re-assemble prompt tu trimmed components
                trimmed_comp = trim_result.components
                if output_format == "smart":
                    prompt = self._build_smart(
                        all_file_paths,
                        workspace,
                        trimmed_comp.instructions,
                        bool(trimmed_comp.git_diffs_text),
                        use_relative_paths,
                        tree_item,
                        selected_paths,
                        instructions_at_top=instructions_at_top,
                    )
                else:
                    output_style = _FORMAT_TO_STYLE.get(output_format, OutputStyle.XML)
                    # Re-format trimmed in-memory data
                    file_contents = self._reconstruct_file_contents(
                        trimmed_comp.file_contents, output_format
                    )

                    prompt = generate_prompt(
                        file_map=trimmed_comp.file_map,
                        file_contents=file_contents,
                        user_instructions=trimmed_comp.instructions,
                        output_style=output_style,
                        include_xml_formatting=include_xml_formatting,
                        git_diffs=git_diffs if trimmed_comp.git_diffs_text else None,
                        git_logs=git_logs if trimmed_comp.git_logs_text else None,
                        project_rules=trimmed_comp.project_rules,
                        workspace_root=workspace,
                        instructions_at_top=instructions_at_top,
                    )

                # Append trimmed notes section vao prompt
                if trimmed_notes:
                    notes_section = "\n<trimmed_context_notes>\n"
                    for note in trimmed_notes:
                        notes_section += f"- {note}\n"
                    notes_section += "</trimmed_context_notes>\n"
                    prompt += notes_section

                token_count = self._tokenization_service.count_tokens(prompt)

                # Re-count per-file tokens
                per_file_tokens = self._count_per_file_tokens(
                    all_file_paths,
                    workspace,
                    use_relative_paths,
                    dep_path_set,
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
            dependency_graph=None,  # Feature 3 se cap nhat tu MCP layer
        )

    def _reconstruct_file_contents(
        self, trimmed_contents: Dict[str, str], output_format: str
    ) -> str:
        """
        Re-format trimmed dictionary content vao string theo output_format.
        (Thay vi doc lai tu disk).
        """
        if not trimmed_contents:
            return ""

        parts = []
        if output_format == "xml":
            for path, content in trimmed_contents.items():
                parts.append(f'<file path="{path}">\n{content}\n</file>')
            return "\n\n".join(parts)
        elif output_format == "json":
            import json as _json

            arr = []
            for path, content in trimmed_contents.items():
                arr.append({"path": path, "content": content})
            return _json.dumps(arr, indent=2)
        else:
            # plain
            for path, content in trimmed_contents.items():
                parts.append(f"{path}\n" + "-" * len(path) + f"\n{content}")
            return "\n\n".join(parts)

    def _count_per_file_tokens(
        self,
        file_paths: List[Path],
        workspace: Path,
        use_relative_paths: bool,
        dep_path_set: set[str],
        codemap_paths: Optional[Set[str]] = None,
    ) -> List[FileTokenInfo]:
        """
        Dem token cho tung file rieng le de cung cap metadata chi tiet.

        Args:
            file_paths: Tat ca file paths (primary + dependency)
            workspace: Workspace root path
            use_relative_paths: Co dung relative paths khong
            dep_path_set: Set cac dependency file paths (str) de danh dau is_dependency
            codemap_paths: Set cac file paths la codemap-only

        Returns:
            List[FileTokenInfo] voi token count per file
        """
        entries = collect_files(
            selected_paths={str(p) for p in file_paths},
            workspace_root=workspace,
            use_relative_paths=use_relative_paths,
        )

        codemap_set = codemap_paths or set()

        result: list[FileTokenInfo] = []
        for entry in entries:
            # Normalize entry.path to absolute for comparison
            entry_path_abs = str(entry.path)
            if not Path(entry_path_abs).is_absolute():
                entry_path_abs = str((workspace / entry_path_abs).resolve())

            is_codemap_file = entry_path_abs in codemap_set
            tokens = 0

            if is_codemap_file and entry.content:
                # Count tokens on codemap content (AST only)
                from domain.smart_context import smart_parse, is_supported

                ext = Path(str(entry.path)).suffix.lstrip(".")
                if is_supported(ext):
                    smart = smart_parse(
                        str(entry.path), entry.content, include_relationships=False
                    )
                    if smart:
                        tokens = self._tokenization_service.count_tokens(smart)
                    else:
                        tokens = self._tokenization_service.count_tokens(entry.content)
                else:
                    tokens = self._tokenization_service.count_tokens(entry.content)
            elif entry.content:
                tokens = self._tokenization_service.count_tokens(entry.content)

            result.append(
                FileTokenInfo(
                    path=entry.display_path,
                    tokens=tokens,
                    is_dependency=str(entry.path) in dep_path_set,
                    was_trimmed=False,
                    is_codemap=is_codemap_file,
                )
            )

        return result

    def count_tokens(self, text: str) -> int:
        """Dem so luong tokens trong text.

        Delegate sang TokenizationService singleton de dam bao
        cung tokenizer instance duoc su dung cho tat ca operations.

        Args:
            text: Noi dung can dem tokens

        Returns:
            So luong tokens
        """
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

        Args:
            tree_item: Root TreeItem
            selected_paths: Set paths da chon
            workspace: Workspace root (optional)
            use_relative_paths: Co dung relative paths khong

        Returns:
            File map string (tree format)
        """
        return generate_file_map(
            tree_item,
            selected_paths,
            workspace_root=workspace,
            use_relative_paths=use_relative_paths,
        )

    def _build_smart(
        self,
        file_paths: List[Path],
        workspace: Path,
        instructions: str,
        include_git_changes: bool,
        use_relative_paths: bool,
        tree_item: Optional[TreeItem] = None,
        selected_paths: Optional[Set[str]] = None,
        instructions_at_top: bool = False,
        full_tree: bool = False,
    ) -> str:
        """
        Build smart context prompt với code maps và relationships.

        Args:
            file_paths: Danh sách file paths
            workspace: Workspace root
            instructions: User instructions
            include_git_changes: Có include git không
            use_relative_paths: Có dùng relative paths không
            tree_item: Root TreeItem cho file map
            selected_paths: Set paths đã chọn
            instructions_at_top: Di chuyển instructions lên đầu
        """
        # Convert paths to string set cho generate_smart_context
        path_strs = {str(p) for p in file_paths}

        # Load Project Rules from workspace
        from application.services.workspace_rules import get_rule_file_contents

        project_rules = get_rule_file_contents(workspace)

        smart_contents = generate_smart_context(
            selected_paths=path_strs,
            include_relationships=True,  # Giu nguyen behavior truoc refactor
            workspace_root=workspace,
            use_relative_paths=use_relative_paths,
        )
        # Store for breakdown calculation
        self._last_smart_contents = smart_contents

        # Generate file map
        file_map = ""
        if tree_item and selected_paths:
            file_map = generate_file_map(
                tree_item,
                selected_paths,
                workspace_root=workspace,
                use_relative_paths=use_relative_paths,
                show_all=full_tree,
            )

        # Fetch git data neu can
        git_diffs = None
        git_logs = None
        if include_git_changes:
            git_diffs = get_git_diffs(workspace)
            git_logs = get_git_logs(workspace, max_commits=5)

        return build_smart_prompt(
            smart_contents=smart_contents,
            file_map=file_map,
            user_instructions=instructions,
            git_diffs=git_diffs,
            git_logs=git_logs,
            project_rules=project_rules,
            workspace_root=workspace,
            instructions_at_top=instructions_at_top,
        )


logger = logging.getLogger(__name__)


class QtClipboardService:
    """
    Clipboard service su dung Qt QApplication.clipboard().

    Phu thuoc Qt runtime nen chi dung trong app context.
    """

    def copy_to_clipboard(self, text: str) -> tuple[bool, str]:
        """
        Copy text ra system clipboard qua Qt.

        Returns:
            (success, error_message): (True, "") if success, (False, error_msg) if failed
        """
        try:
            from PySide6.QtWidgets import QApplication

            clipboard = QApplication.clipboard()
            if clipboard is None:
                msg = "QApplication.clipboard() returned None"
                logger.warning(msg)
                return False, msg

            clipboard.setText(text)
            return True, ""
        except Exception as e:
            msg = f"Clipboard error: {e}"
            logger.warning("Failed to copy to clipboard: %s", e)
            return False, msg
