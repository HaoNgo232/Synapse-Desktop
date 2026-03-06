# DefaultParseStrategy - Fallback strategy cho cac ngon ngu chua co strategy rieng
# Lay dong dau tien cua moi definition

from typing import Optional

from core.smart_context.strategies.base import BaseParseStrategy
from core.smart_context.chunk_utils import check_and_add


class DefaultParseStrategy(BaseParseStrategy):
    """
    Default fallback strategy.
    Dung cho cac ngon ngu chua co strategy rieng.
    Chi lay dong dau tien cua moi definition.
    """

    def parse_capture(
        self,
        capture_name: str,
        lines: list[str],
        start_row: int,
        end_row: int,
        processed: set[str],
    ) -> Optional[str]:
        """Parse capture - lay dong dau tien hoac toan bo tuy loai."""

        if not self.validate_line_exists(lines, start_row):
            return None

        # Comments - lay toan bo
        if "comment" in capture_name:
            content = "\n".join(lines[start_row : end_row + 1])
            return check_and_add(content, processed)

        # Imports - lay toan bo
        if "import" in capture_name:
            content = "\n".join(lines[start_row : end_row + 1])
            return check_and_add(content, processed)

        # Definitions - chi lay dong dau tien
        if "definition." in capture_name:
            return check_and_add(lines[start_row].rstrip(), processed)

        # Default
        return check_and_add(lines[start_row], processed)
