"""
Service Interfaces cho ContextView decomposition.

Dinh nghia cac Protocol interfaces de tach logic tu CopyActionsMixin
thanh cac service doc lap, testable, va co the thay the.

Interfaces:
- IPromptBuilder: Build prompt tu selected files + settings
- IClipboardService: Copy text ra clipboard
"""

from typing import (
    Protocol,
    runtime_checkable,
    List,
    Optional,
    Set,
    Tuple,
    Dict,
    TYPE_CHECKING,
    Any,
)
from pathlib import Path

if TYPE_CHECKING:
    from infrastructure.filesystem.file_utils import TreeItem
    from shared.types.prompt_types_extra import BuildResult


@runtime_checkable
class IPromptBuilder(Protocol):
    """
    Interface cho prompt building pipeline.

    Tach rieng logic generate prompt tu UI concerns.
    Input: files + settings -> Output: prompt string + token count.
    """

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
        """Legacy tuple-based prompt building."""
        ...

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
        """Full result-based prompt building."""
        ...

    def build_file_map(
        self,
        tree_item: "TreeItem",
        selected_paths: Set[str],
        workspace: Optional[Path] = None,
        use_relative_paths: bool = False,
    ) -> str:
        """
        Generate file map (tree structure) tu file paths.

        Args:
            tree_item: Root TreeItem
            selected_paths: Set paths da chon
            workspace: Workspace root path (optional)
            use_relative_paths: Co dung relative paths khong

        Returns:
            File map string (tree format)
        """
        ...

    def count_tokens(self, text: str) -> int:
        """
        Dem so luong tokens trong text.

        Dam bao cung tokenizer instance duoc su dung cho tat ca operations.

        Args:
            text: Noi dung can dem tokens

        Returns:
            So luong tokens
        """
        ...


@runtime_checkable
class IClipboardService(Protocol):
    """Interface cho clipboard operations."""

    def copy_to_clipboard(self, text: str) -> tuple[bool, str]:
        """
        Copy text ra system clipboard.

        Args:
            text: Noi dung can copy

        Returns:
            (success, error_message): (True, "") neu thanh cong,
            (False, error_msg) neu that bai
        """
        ...
