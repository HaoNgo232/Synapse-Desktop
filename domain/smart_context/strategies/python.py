# PythonParseStrategy - Strategy cho Python
# Port tu Repomix's PythonParseStrategy.ts

import re
from typing import Optional

from core.smart_context.strategies.base import BaseParseStrategy
from core.smart_context.chunk_utils import check_and_add


class PythonParseStrategy(BaseParseStrategy):
    """
    Parse strategy cho Python.
    Extract class definitions, function signatures, decorators, docstrings.
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

        # Function definition
        if "definition.function" in capture_name or "definition.method" in capture_name:
            return self._parse_function(lines, start_row, processed)

        # Class definition
        if "definition.class" in capture_name:
            return self._parse_class(lines, start_row, processed)

        # Import statements
        if "definition.import" in capture_name:
            return self._parse_import(lines, start_row, end_row, processed)

        # Comments and docstrings
        if "comment" in capture_name or "docstring" in capture_name:
            return self._parse_comment(lines, start_row, end_row, processed)

        # Default: first line only
        return check_and_add(lines[start_row], processed)

    def _parse_function(
        self, lines: list[str], start_row: int, processed: set[str]
    ) -> Optional[str]:
        """
        Parse function definition.
        Lay decorators + signature (khong co body).
        """
        decorators = self.get_decorators(lines, start_row)
        signature = self._get_function_signature(lines, start_row)

        if not signature:
            return None

        full = "\n".join([*decorators, signature]) if decorators else signature
        return check_and_add(full, processed)

    def _parse_class(
        self, lines: list[str], start_row: int, processed: set[str]
    ) -> Optional[str]:
        """
        Parse class definition.
        Lay decorators + class line (khong co body).
        """
        decorators = self.get_decorators(lines, start_row)
        class_def = self._get_class_definition(lines, start_row)

        if not class_def:
            return None

        full = "\n".join([*decorators, class_def]) if decorators else class_def
        return check_and_add(full, processed)

    def _parse_import(
        self, lines: list[str], start_row: int, end_row: int, processed: set[str]
    ) -> Optional[str]:
        """Parse import statement - lay toan bo."""
        content = "\n".join(lines[start_row : end_row + 1])
        return check_and_add(content, processed)

    def _parse_comment(
        self, lines: list[str], start_row: int, end_row: int, processed: set[str]
    ) -> Optional[str]:
        """Parse comment/docstring - lay toan bo."""
        content = "\n".join(lines[start_row : end_row + 1])
        return check_and_add(content, processed)

    def _get_function_signature(
        self, lines: list[str], start_row: int
    ) -> Optional[str]:
        """
        Extract function signature khong co body.
        Ported from Repomix's PythonParseStrategy.getFunctionSignature().
        """
        line = lines[start_row]
        # Match: def name(...) -> ...:
        match = re.match(r"(\s*def\s+\w+\s*\(.*?\))(\s*->\s*[^:]+)?:", line)
        if match:
            return line.rstrip().rstrip(":")
        # Fallback: return line without trailing colon
        if "def " in line:
            return line.rstrip().rstrip(":")
        return None

    def _get_class_definition(self, lines: list[str], start_row: int) -> Optional[str]:
        """
        Extract class definition voi inheritance.
        Ported from Repomix's PythonParseStrategy.getClassInheritance().
        """
        line = lines[start_row]
        if "class " in line:
            return line.rstrip().rstrip(":")
        return None
