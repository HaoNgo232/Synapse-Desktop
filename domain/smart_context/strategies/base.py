# Base ParseStrategy - Abstract base class cho tat ca strategies
# Port tu Repomix's BaseParseStrategy.ts

from abc import ABC, abstractmethod
from typing import Optional


class BaseParseStrategy(ABC):
    """
    Abstract base class cho tat ca parse strategies.

    Moi ngon ngu se implement strategy rieng de extract code structure.
    Strategy instances la stateless - khong luu state giua cac file.
    """

    @abstractmethod
    def parse_capture(
        self,
        capture_name: str,
        lines: list[str],
        start_row: int,
        end_row: int,
        processed: set[str],
    ) -> Optional[str]:
        """
        Parse mot capture va tra ve extracted content.

        Args:
            capture_name: Ten capture tu tree-sitter query (e.g., 'definition.function')
            lines: Noi dung file chia theo dong
            start_row: Dong bat dau cua node
            end_row: Dong ket thuc cua node
            processed: Set cac content da xu ly (de dedup)

        Returns:
            Extracted content hoac None
        """
        pass

    # ========== HELPER METHODS (shared) ==========

    def get_decorators(self, lines: list[str], start_row: int) -> list[str]:
        """
        Extract decorators phia tren class/function definition.
        Ported from Repomix's PythonParseStrategy.getDecorators().

        Args:
            lines: Noi dung file chia theo dong
            start_row: Dong bat dau cua definition

        Returns:
            List cac dong decorator
        """
        decorators: list[str] = []
        current_row = start_row - 1

        while current_row >= 0:
            line = lines[current_row].strip()
            if line.startswith("@"):
                decorators.insert(0, lines[current_row])  # Giu indent goc
            else:
                break
            current_row -= 1

        return decorators

    def validate_line_exists(self, lines: list[str], row: int) -> bool:
        """Kiem tra dong co ton tai trong file khong."""
        return 0 <= row < len(lines)

    def extract_lines(
        self, lines: list[str], start_row: int, end_row: int
    ) -> Optional[list[str]]:
        """
        Extract cac dong tu start_row den end_row.

        Returns:
            List cac dong, hoac None neu invalid
        """
        if not self.validate_line_exists(lines, start_row):
            return None
        selected = lines[start_row : end_row + 1]
        return selected if selected else None
