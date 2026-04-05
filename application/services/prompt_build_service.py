from typing import List, Optional, Set, Tuple, Dict, Any, TYPE_CHECKING
from pathlib import Path
import logging

if TYPE_CHECKING:
    from infrastructure.filesystem.file_utils import TreeItem
    from shared.types.prompt_types_extra import BuildResult

from application.services.service_interfaces import IPromptBuilder
from application.use_cases.build_prompt import BuildPromptUseCase
from domain.prompt.generator import (
    generate_file_map,
)

logger = logging.getLogger(__name__)


class PromptBuildService(IPromptBuilder):
    """
    [DEPRECATED] Legacy wrapper for BuildPromptUseCase.
    Use BuildPromptUseCase directly in new code.
    """

    def __init__(
        self,
        tokenization_service=None,
        graph_service=None,
    ):
        # Fallback to global container if not provided (legacy behavior)
        from infrastructure.di.service_container import ServiceContainer

        container = ServiceContainer.get_instance()
        self._use_case = BuildPromptUseCase(
            tokenization_service=tokenization_service or container.tokenization,
            graph_service=graph_service or container.graph_service,
            git_repo=container.git_repo,
        )

    @property
    def _tokenization_service(self):
        return self._use_case._tokenization_service

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
    ) -> "BuildResult":
        return self._use_case.build_prompt_full(
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
            dependency_files=dependency_files,
            profile=profile,
            **kwargs,
        )

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
        # Use locally imported functions to support legacy patches in tests
        return self._use_case.build_prompt(
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

    def build_file_map(
        self,
        tree_item: "TreeItem",
        selected_paths: Set[str],
        workspace: Optional[Path] = None,
        use_relative_paths: bool = False,
    ) -> str:
        # Use locally imported function to support legacy patches in tests
        return generate_file_map(
            tree_item, selected_paths, workspace, use_relative_paths
        )

    def count_tokens(self, text: str) -> int:
        return self._use_case.count_tokens(text)
