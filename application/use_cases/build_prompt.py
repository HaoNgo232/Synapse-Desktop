from pathlib import Path
from typing import List, Optional, Set, Tuple, Dict, Any, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from application.interfaces.tokenization_port import ITokenizationService
    from domain.relationships.port import IRelationshipGraphProvider
    from domain.ports.git import IGitRepository
    from infrastructure.filesystem.file_utils import TreeItem

# Domain functions are imported locally inside methods to facilitate patching in legacy tests
from shared.types.prompt_types_extra import BuildResult
from application.services.prompt_helpers import (
    count_per_file_tokens,
    calculate_prompt_breakdown,
    apply_context_trimming,
    compute_semantic_index,
)
from application.services.workspace_rules import get_rule_file_contents

from domain.prompt.generator import (
    generate_prompt,
    generate_file_map,
)

logger = logging.getLogger(__name__)


class BuildPromptUseCase:
    """
    Use Case cho việc xây dựng prompt.
    Implement IPromptBuilder protocol để đảm bảo tính hoán đổi.
    """

    def __init__(
        self,
        tokenization_service: "ITokenizationService",
        graph_service: "IRelationshipGraphProvider",
        git_repo: "IGitRepository",
    ):
        self._tokenization_service = tokenization_service
        self._graph_service = graph_service
        self._git_repo = git_repo

    def build_prompt(
        self,
        file_paths: List[Path],
        workspace: Path,
        instructions: str,
        output_format: str,
        include_git_changes: bool,
        use_relative_paths: bool,
        tree_item: Optional["TreeItem"] = None,
        selected_paths: Optional[Set[str]] = None,
        include_xml_formatting: bool = False,
        codemap_paths: Optional[Set[str]] = None,
        instructions_at_top: bool = False,
        full_tree: bool = False,
        semantic_index: bool = True,
        max_tokens: Optional[int] = None,
    ) -> Tuple[str, int, Dict[str, int]]:
        """
        Thực thi quy trình build prompt và trả về kết quả dưới dạng Legacy Tuple.
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
            semantic_index=semantic_index,
            max_tokens=max_tokens,
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
        tree_item: Optional["TreeItem"] = None,
        selected_paths: Optional[Set[str]] = None,
        include_xml_formatting: bool = False,
        codemap_paths: Optional[Set[str]] = None,
        instructions_at_top: bool = False,
        full_tree: bool = False,
        semantic_index: bool = True,
        max_tokens: Optional[int] = None,
        dependency_files: Optional[List[Path]] = None,
        profile: Optional[str] = None,
        **kwargs: Any,
    ) -> BuildResult:
        # 0. Fetch git data
        git_diffs = None
        git_logs = None
        if include_git_changes:
            from infrastructure.git.git_utils import get_git_diffs, get_git_logs

            git_diffs = get_git_diffs(workspace)
            git_logs = get_git_logs(workspace, max_commits=5)

        # 1. Generate file map
        from domain.prompt.generator import (
            generate_file_structure_xml,
        )

        file_map = ""
        if tree_item:
            _sel = selected_paths if selected_paths is not None else set()
            if output_format in ("xml", "json"):
                file_map = generate_file_structure_xml(
                    tree_item,
                    _sel,
                    workspace_root=workspace,
                    use_relative_paths=use_relative_paths,
                    show_all=full_tree,
                )
            else:
                file_map = generate_file_map(
                    tree_item,
                    _sel,
                    workspace_root=workspace,
                    use_relative_paths=use_relative_paths,
                    show_all=full_tree,
                )

        # 2. Load Project Rules
        project_rules = get_rule_file_contents(workspace)

        # 3. Generate file contents
        from domain.prompt.generator import generate_smart_context

        all_path_strs = {str(p) for p in file_paths}
        file_contents = ""
        if output_format == "smart":
            file_contents = generate_smart_context(
                selected_paths=all_path_strs,
                workspace_root=workspace,
                use_relative_paths=use_relative_paths,
                include_relationships=semantic_index,
            )
        else:
            from domain.prompt.generator import (
                generate_file_contents_xml,
                generate_file_contents_json,
                generate_file_contents_plain,
            )

            generators = {
                "xml": generate_file_contents_xml,
                "json": generate_file_contents_json,
                "plain": generate_file_contents_plain,
            }
            content_gen = generators.get(output_format, generate_file_contents_xml)
            file_contents = content_gen(
                selected_paths=all_path_strs,
                workspace_root=workspace,
                use_relative_paths=use_relative_paths,
                codemap_paths=codemap_paths,
            )

        # 4. Semantic Index
        if self._graph_service and semantic_index:
            try:
                self._graph_service.ensure_built(workspace)
            except Exception as e:
                logger.warning("Failed to ensure graph built: %s", e)

        semantic_index_text = ""
        if semantic_index:
            semantic_index_text = compute_semantic_index(
                workspace, self._graph_service, output_format
            )

        # 5. Assemble prompt
        from domain.prompt.generator import (
            OutputStyle,
            build_smart_prompt,
        )

        style_map = {
            "xml": OutputStyle.XML,
            "json": OutputStyle.JSON,
            "plain": OutputStyle.PLAIN,
        }
        if output_format == "smart":
            prompt_text = build_smart_prompt(
                smart_contents=file_contents,
                file_map=file_map,
                user_instructions=instructions,
                git_diffs=git_diffs,
                git_logs=git_logs,
                project_rules=project_rules,
                workspace_root=workspace,
                instructions_at_top=instructions_at_top,
                semantic_index=semantic_index_text,
            )
        else:
            prompt_text = generate_prompt(
                file_map=file_map,
                file_contents=file_contents,
                user_instructions=instructions,
                output_style=style_map.get(output_format, OutputStyle.XML),
                include_xml_formatting=include_xml_formatting,
                git_diffs=git_diffs,
                git_logs=git_logs,
                project_rules=project_rules,
                workspace_root=workspace,
                instructions_at_top=instructions_at_top,
                semantic_index=semantic_index_text,
            )

        token_count = self._tokenization_service.count_tokens(prompt_text)

        # 6. Breakdown & Per-file
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

        per_file_tokens = count_per_file_tokens(
            file_paths,
            workspace,
            use_relative_paths,
            set(),
            self._tokenization_service,
            codemap_paths=codemap_paths,
        )

        # 7. Auto-trim
        trimmed = False
        trimmed_notes = []
        if max_tokens is not None and token_count > max_tokens:
            prompt_trimmed, notes = apply_context_trimming(
                max_tokens,
                file_paths,
                workspace,
                use_relative_paths,
                set(),
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
                semantic_index_text,
                style_map.get(output_format, OutputStyle.XML),
            )
            if notes:
                trimmed = True
                trimmed_notes = notes
                prompt_text = prompt_trimmed
                token_count = self._tokenization_service.count_tokens(prompt_text)

        return BuildResult(
            prompt_text=prompt_text,
            total_tokens=token_count,
            file_count=len(file_paths),
            format=output_format,
            trimmed=trimmed,
            trimmed_notes=trimmed_notes,
            breakdown=breakdown,
            files=per_file_tokens,
        )

    def build_file_map(
        self,
        tree_item: "TreeItem",
        selected_paths: Set[str],
        workspace: Optional[Path] = None,
        use_relative_paths: bool = False,
    ) -> str:

        return generate_file_map(
            tree_item,
            selected_paths,
            workspace_root=workspace,
            use_relative_paths=use_relative_paths,
        )

    def count_tokens(self, text: str) -> int:
        return self._tokenization_service.count_tokens(text)
