from typing import Protocol, runtime_checkable


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
