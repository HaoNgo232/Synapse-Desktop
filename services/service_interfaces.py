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
    TYPE_CHECKING,
)
from pathlib import Path

if TYPE_CHECKING:
    from core.utils.file_utils import TreeItem


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
    ) -> Tuple[str, int]:
        """
        Generate prompt tu danh sach file paths va settings.

        Args:
            file_paths: Danh sach file paths da resolve
            workspace: Workspace root path
            instructions: User instructions text
            output_format: Output format (xml, json, plain, smart)
            include_git_changes: Co include git changes khong
            use_relative_paths: Co dung relative paths khong
            tree_item: Root TreeItem cho file map (optional)
            selected_paths: Set paths da chon cho file map (optional)
            include_xml_formatting: Co bao gom OPX instructions khong

        Returns:
            Tuple (prompt_text, token_count)
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
