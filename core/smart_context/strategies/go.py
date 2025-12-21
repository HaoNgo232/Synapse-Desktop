# GoParseStrategy - Strategy cho Go
# Port tu Repomix's GoParseStrategy.ts

import re
from typing import Optional

from core.smart_context.strategies.base import BaseParseStrategy
from core.smart_context.chunk_utils import check_and_add


class GoParseStrategy(BaseParseStrategy):
    """
    Parse strategy cho Go.
    Extract package, imports, types, interfaces, structs, functions, methods.
    """

    def parse_capture(
        self,
        capture_name: str,
        lines: list[str],
        start_row: int,
        end_row: int,
        processed: set[str],
    ) -> Optional[str]:
        """Parse capture based on type."""

        if not self.validate_line_exists(lines, start_row):
            return None

        # Comments
        if "comment" in capture_name:
            return self._parse_block(lines, start_row, end_row, processed)

        # Package declarations
        if "definition.package" in capture_name or "definition.module" in capture_name:
            return self._parse_simple(lines, start_row, processed)

        # Import declarations
        if "definition.import" in capture_name:
            if "(" in lines[start_row]:
                return self._parse_block(lines, start_row, end_row, processed)
            return self._parse_simple(lines, start_row, processed)

        # Type definitions (type, interface, struct)
        if any(
            t in capture_name
            for t in [
                "definition.type",
                "definition.interface",
                "definition.struct",
            ]
        ):
            return self._parse_type(lines, start_row, end_row, processed)

        # Function declarations
        if "definition.function" in capture_name:
            return self._parse_function(
                lines, start_row, end_row, processed, is_method=False
            )

        # Method declarations
        if "definition.method" in capture_name:
            return self._parse_function(
                lines, start_row, end_row, processed, is_method=True
            )

        return None

    def _parse_simple(
        self, lines: list[str], start_row: int, processed: set[str]
    ) -> Optional[str]:
        """Parse simple single-line declaration."""
        declaration = lines[start_row].strip()
        return check_and_add(declaration, processed)

    def _parse_block(
        self,
        lines: list[str],
        start_row: int,
        end_row: int,
        processed: set[str],
    ) -> Optional[str]:
        """Parse block declaration (may span multiple lines)."""
        # Tim dong ket thuc cua block
        block_end = end_row
        if "(" in lines[start_row]:
            block_end = self._find_closing(lines, start_row, end_row, ")")

        declaration = "\n".join(lines[start_row : block_end + 1])
        return check_and_add(declaration, processed)

    def _parse_function(
        self,
        lines: list[str],
        start_row: int,
        end_row: int,
        processed: set[str],
        is_method: bool,
    ) -> Optional[str]:
        """Parse function or method - chi lay signature, bo body."""
        key = "method" if is_method else "func"
        name = (
            self._get_method_name(lines, start_row)
            if is_method
            else self._get_func_name(lines, start_row)
        )

        # Skip neu da processed
        if name and f"{key}:{name}" in processed:
            return None

        # Tim dong chua { va lay signature
        sig_end = self._find_closing(lines, start_row, end_row, "{")
        signature = "\n".join(lines[start_row : sig_end + 1]).strip()

        # Clean - bo { va phan sau
        clean_sig = signature.split("{")[0].strip()

        result = check_and_add(clean_sig, processed)
        if result and name:
            processed.add(f"{key}:{name}")

        return result

    def _parse_type(
        self,
        lines: list[str],
        start_row: int,
        end_row: int,
        processed: set[str],
    ) -> Optional[str]:
        """Parse type definition (type, struct, interface)."""
        # Tim dong ket thuc - neu co { thi tim }
        if "{" in lines[start_row]:
            type_end = self._find_closing(lines, start_row, end_row, "}")
        else:
            type_end = end_row

        definition = "\n".join(lines[start_row : type_end + 1])
        return check_and_add(definition, processed)

    def _get_func_name(self, lines: list[str], start_row: int) -> Optional[str]:
        """Get function name from 'func funcName(' pattern."""
        line = lines[start_row]
        match = re.search(r"func\s+([A-Za-z0-9_]+)\s*\(", line)
        return match.group(1) if match else None

    def _get_method_name(self, lines: list[str], start_row: int) -> Optional[str]:
        """Get method name from 'func (r ReceiverType) methodName(' pattern."""
        line = lines[start_row]
        match = re.search(r"func\s+\([^)]+\)\s+([A-Za-z0-9_]+)\s*\(", line)
        return match.group(1) if match else None

    def _find_closing(
        self, lines: list[str], start_row: int, end_row: int, token: str
    ) -> int:
        """Tim dong chua closing token."""
        for i in range(start_row, min(end_row + 1, len(lines))):
            if token in lines[i]:
                return i
        return start_row
