# TypeScriptParseStrategy - Strategy cho TypeScript/JavaScript
# Port tu Repomix's TypeScriptParseStrategy.ts

import re
from typing import Optional

from core.smart_context.strategies.base import BaseParseStrategy
from core.smart_context.chunk_utils import check_and_add


class TypeScriptParseStrategy(BaseParseStrategy):
    """
    Parse strategy cho TypeScript va JavaScript.
    Extract function signatures, class definitions, interfaces, types, enums, imports.
    """

    # Pattern de lay function name tu const/let/var declarations
    FUNCTION_NAME_PATTERN = re.compile(
        r"(?:export\s+)?(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*="
    )

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

        # Function/Method definition
        if "definition.function" in capture_name or "definition.method" in capture_name:
            return self._parse_function(lines, start_row, end_row, processed)

        # Class definition
        if "definition.class" in capture_name:
            return self._parse_class(lines, start_row, end_row, processed)

        # Interface, Type, Enum, Import
        if any(
            t in capture_name
            for t in [
                "definition.interface",
                "definition.type",
                "definition.enum",
                "definition.import",
            ]
        ):
            return self._parse_type_or_import(lines, start_row, end_row, processed)

        # Comments
        if "comment" in capture_name:
            content = "\n".join(lines[start_row : end_row + 1])
            return content.strip()

        return None

    def _parse_function(
        self,
        lines: list[str],
        start_row: int,
        end_row: int,
        processed: set[str],
    ) -> Optional[str]:
        """
        Parse function definition.
        Tim signature end va clean up body markers.
        """
        # Track function name de dedup
        func_name = self._get_function_name(lines, start_row)
        if func_name and f"func:{func_name}" in processed:
            return None

        # Tim dong ket thuc cua signature
        sig_end_row = self._find_signature_end(lines, start_row, end_row)
        selected_lines = lines[start_row : sig_end_row + 1]
        cleaned = self._clean_function_signature(selected_lines)

        result = check_and_add(cleaned, processed)
        if result and func_name:
            processed.add(f"func:{func_name}")

        return result

    def _parse_class(
        self,
        lines: list[str],
        start_row: int,
        end_row: int,
        processed: set[str],
    ) -> Optional[str]:
        """
        Parse class definition.
        Bao gom extends/implements neu co.
        """
        selected_lines = [lines[start_row]]

        # Kiem tra dong tiep theo co extends/implements khong
        if start_row + 1 <= end_row and start_row + 1 < len(lines):
            next_line = lines[start_row + 1].strip()
            if "extends" in next_line or "implements" in next_line:
                selected_lines.append(next_line)

        # Clean up - bo { va phan sau
        cleaned_lines = [re.sub(r"\{.*$", "", line).strip() for line in selected_lines]
        definition = "\n".join(cleaned_lines).strip()

        return check_and_add(definition, processed)

    def _parse_type_or_import(
        self,
        lines: list[str],
        start_row: int,
        end_row: int,
        processed: set[str],
    ) -> Optional[str]:
        """Parse interface, type, enum, import - lay toan bo."""
        selected_lines = lines[start_row : end_row + 1]
        definition = "\n".join(selected_lines).strip()
        return check_and_add(definition, processed)

    def _get_function_name(self, lines: list[str], start_row: int) -> Optional[str]:
        """Lay function name tu dong."""
        line = lines[start_row]
        match = self.FUNCTION_NAME_PATTERN.match(line)
        return match.group(1) if match else None

    def _find_signature_end(
        self, lines: list[str], start_row: int, end_row: int
    ) -> int:
        """
        Tim dong ket thuc cua function signature.
        Signature ket thuc khi gap ) va sau do la { hoac => hoac ;
        """
        for i in range(start_row, min(end_row + 1, len(lines))):
            line = lines[i].strip()
            if ")" in line and (
                line.endswith("{") or line.endswith("=>") or line.endswith(";")
            ):
                return i
        return start_row

    def _clean_function_signature(self, lines: list[str]) -> str:
        """
        Clean function signature - bo { va => o cuoi.
        """
        result = list(lines)
        if not result:
            return ""

        last_idx = len(result) - 1
        last_line = result[last_idx]

        if "{" in last_line:
            result[last_idx] = last_line[: last_line.index("{")].strip()
        elif "=>" in last_line:
            result[last_idx] = last_line[: last_line.index("=>")].strip()

        return "\n".join(result).strip()
