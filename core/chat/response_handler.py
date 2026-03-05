"""
Response Handler - Parse LLM response cho chat.

Module nay xu ly response tu LLM:
- Detect va extract OPX blocks (de hien thi Apply button)
- Extract <synapse_memory> blocks (de luu vao memory)
- Phan loai response: pure text, contains OPX, hoac mixed

OPX detection chay sau khi stream hoan tat (khong parse partial XML),
dam bao chat flow khong bi block boi OPX parsing.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from core.opx_parser import ParseResult, parse_opx_response

logger = logging.getLogger(__name__)

# Pattern detect OPX content trong response
_OPX_DETECT_PATTERN = re.compile(r"<\s*(?:opx|edit)\b", re.IGNORECASE)

# Pattern detect memory block
_MEMORY_DETECT_PATTERN = re.compile(r"<\s*synapse_memory\s*>", re.IGNORECASE)


@dataclass
class ParsedResponse:
    """
    Ket qua parse LLM response.

    Attributes:
        raw_content: Noi dung goc tu LLM
        text_parts: Cac phan text thuan (khong phai OPX)
        opx_result: Ket qua parse OPX neu co (None neu khong co OPX)
        memory_block: Noi dung memory block neu co
        has_opx: True neu response chua OPX blocks
        has_memory: True neu response chua memory block
    """

    raw_content: str
    text_parts: List[str] = field(default_factory=list)
    opx_result: Optional[ParseResult] = None
    memory_block: Optional[str] = None
    has_opx: bool = False
    has_memory: bool = False

    @property
    def display_text(self) -> str:
        """Lay text hien thi cho user (loai bo OPX va memory blocks)."""
        return self.raw_content

    @property
    def has_actionable_opx(self) -> bool:
        """True neu co OPX blocks hop le co the apply."""
        return (
            self.has_opx
            and self.opx_result is not None
            and len(self.opx_result.file_actions) > 0
        )


def parse_chat_response(content: str) -> ParsedResponse:
    """
    Parse LLM response va extract OPX, memory blocks.

    Chi goi sau khi stream hoan tat de tranh parse partial XML.

    Args:
        content: Full response string tu LLM

    Returns:
        ParsedResponse voi cac extracted blocks
    """
    result = ParsedResponse(raw_content=content)

    # Detect OPX blocks
    if _OPX_DETECT_PATTERN.search(content):
        result.has_opx = True
        try:
            parse_result = parse_opx_response(content)
            result.opx_result = parse_result
            # Extract memory block tu OPX parser (co the da detect)
            if parse_result.memory_block:
                result.memory_block = parse_result.memory_block
                result.has_memory = True
        except Exception as e:
            logger.warning("OPX parsing failed: %s", e)

    # Detect memory block ngay ca khi khong co OPX
    if not result.has_memory and _MEMORY_DETECT_PATTERN.search(content):
        result.has_memory = True
        try:
            from core.opx_parser import MEMORY_TAG_REGEX

            match = MEMORY_TAG_REGEX.search(content)
            if match:
                result.memory_block = match.group(1).strip()
        except Exception as e:
            logger.warning("Memory block extraction failed: %s", e)

    return result
