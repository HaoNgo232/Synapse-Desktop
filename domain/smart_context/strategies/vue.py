# VueParseStrategy - Strategy cho Vue SFC
# Port tu Repomix's VueParseStrategy.ts
# Vue SFC don gian - lay toan bo content cua moi capture

from typing import Optional

from core.smart_context.strategies.base import BaseParseStrategy


class VueParseStrategy(BaseParseStrategy):
    """
    Parse strategy cho Vue Single File Components.
    Lay toan bo content cua moi capture, dedup bang capture_name:start_row.
    """

    def parse_capture(
        self,
        capture_name: str,
        lines: list[str],
        start_row: int,
        end_row: int,
        processed: set[str],
    ) -> Optional[str]:
        """Parse Vue capture - lay toan bo content."""

        selected = self.extract_lines(lines, start_row, end_row)
        if not selected:
            return None

        chunk = "\n".join(selected)

        # Dedup bang unique ID
        chunk_id = f"{capture_name}:{start_row}"
        if chunk_id in processed:
            return None

        processed.add(chunk_id)
        return chunk
