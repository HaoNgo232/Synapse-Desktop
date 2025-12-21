# CssParseStrategy - Strategy cho CSS/SCSS/LESS
# Port tu Repomix's CssParseStrategy.ts

from typing import Optional

from core.smart_context.strategies.base import BaseParseStrategy
from core.smart_context.chunk_utils import check_and_add


class CssParseStrategy(BaseParseStrategy):
    """
    Parse strategy cho CSS, SCSS, LESS.
    Extract selectors, at-rules, comments.
    """

    def parse_capture(
        self,
        capture_name: str,
        lines: list[str],
        start_row: int,
        end_row: int,
        processed: set[str],
    ) -> Optional[str]:
        """Parse CSS capture."""

        if not self.validate_line_exists(lines, start_row):
            return None

        # Xac dinh loai capture
        is_comment = "comment" in capture_name
        is_selector = (
            "selector" in capture_name or "definition.selector" in capture_name
        )
        is_at_rule = "at_rule" in capture_name or "definition.at_rule" in capture_name

        if not (is_comment or is_selector or is_at_rule):
            return None

        # Comments - lay toan bo
        if is_comment:
            content = "\n".join(lines[start_row : end_row + 1])
        else:
            # Selectors va at-rules - chi lay dong dau tien
            content = lines[start_row]

        return check_and_add(content, processed)
