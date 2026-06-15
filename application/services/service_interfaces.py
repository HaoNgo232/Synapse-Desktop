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
)
from pathlib import Path

# Re-export IClipboardService từ domain.ports để backward compatible
from domain.ports.clipboard_port import IClipboardService as IClipboardService

if TYPE_CHECKING:
    from domain.smart_context.tree_item import TreeItem


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
    ) -> Tuple[str, int, Dict[str, int]]:
        """
        Generate prompt tu danh sach file paths va settings.

        Args:
            file_paths: Danh sach file paths da resolve
            workspace: Workspace root path
            instructions: User instructions text
            output_format: Output format (xml, plain, compress)
            include_git_changes: Co include git changes khong
            use_relative_paths: Co dung relative paths khong
            tree_item: Root TreeItem cho file map (optional)
            selected_paths: Set paths da chon cho file map (optional)
            include_xml_formatting: Co bao gom OPX instructions khong

        Returns:
            Tuple (prompt_text, token_count, breakdown_dict)
        """
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
