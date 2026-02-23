"""
OPX (Overwrite Patch XML) Parser

Port truc tiep tu: /home/hao/Desktop/labs/overwrite/src/utils/xml-parser.ts
Giu nguyen tat ca regex patterns va logic de dam bao behavior giong het.

OPX-only: accepts <edit ...> (optionally wrapped in <opx>...</opx>)

op mapping:
- new     -> create (requires <put>)
- patch   -> modify (requires <find> and <put>)
- replace -> rewrite (requires <put>)
- remove  -> delete (no children)
- move    -> rename (requires <to file="..."/>)
"""

import re
from dataclasses import dataclass, field
from typing import Optional, Union, Literal


@dataclass
class ChangeBlock:
    """Mot thay doi trong file action"""

    description: str
    content: str
    search: Optional[str] = None  # Chi dung cho modify action
    occurrence: Optional[Union[Literal["first", "last"], int]] = (
        None  # Disambiguator cho modify
    )


@dataclass
class FileAction:
    """Mot file action duoc parse tu OPX"""

    path: str
    action: Literal["create", "rewrite", "modify", "delete", "rename"]
    new_path: Optional[str] = None  # Cho rename action
    root: Optional[str] = None  # Optional workspace root name cho multi-root
    changes: list[ChangeBlock] = field(default_factory=list)


@dataclass
class ParseResult:
    """Ket qua parse OPX"""

    file_actions: list[FileAction] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    plan: Optional[str] = None  # OPX khong define plan, giu de tuong thich
    memory_block: Optional[str] = None  # Luu tru Continuous Context Memory


@dataclass
class ParsedEdit:
    """Mot edit element da duoc parse"""

    index: int
    attrs: dict[str, str]
    body: Optional[str]


# ============================================================================
# REGEX PATTERNS - COPY NGUYEN TU TYPESCRIPT
# ============================================================================

# Self-closing edit: <edit ... />
SELF_CLOSING_REGEX = re.compile(r"<\s*edit\b([^>]*)/>", re.IGNORECASE)

# Paired edit: <edit ...>...</edit>
PAIRED_REGEX = re.compile(
    r"<\s*edit\b([^>]*)>([\s\S]*?)<\s*/\s*edit\s*>", re.IGNORECASE
)

# Attribute parser: key="value" or key='value'
ATTR_REGEX = re.compile(r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')')

# Tag patterns
TO_TAG_REGEX = re.compile(r"<\s*to\b([^>]*)/>", re.IGNORECASE)
PUT_TAG_REGEX = re.compile(r"<\s*put\s*>([\s\S]*?)<\s*/\s*put\s*>", re.IGNORECASE)
FIND_TAG_REGEX = re.compile(
    r"<\s*find\b([^>]*)>([\s\S]*?)<\s*/\s*find\s*>", re.IGNORECASE
)
WHY_TAG_REGEX = re.compile(r"<\s*why\s*>([\s\S]*?)<\s*/\s*why\s*>", re.IGNORECASE)

# Memory block pattern
MEMORY_TAG_REGEX = re.compile(
    r"<\s*synapse_memory\s*>([\s\S]*?)<\s*/\s*synapse_memory\s*>", re.IGNORECASE
)


def parse_opx_response(xml_content: str) -> ParseResult:
    """
    Parse OPX response va return unified FileAction list.

    Args:
        xml_content: Raw XML/OPX string tu LLM response

    Returns:
        ParseResult chua file_actions va errors
    """
    result = ParseResult()

    try:
        # Input validation
        if xml_content is None:
            return ParseResult(errors=["Input is None"])

        if not isinstance(xml_content, str):
            return ParseResult(
                errors=[f"Invalid input type: {type(xml_content).__name__}"]
            )

        cleaned = _sanitize_response(xml_content)

        # Extract memory block FIRST (before it gets sanitized out if it's outside OPX)
        # We can extract it from the original xml_content to be safe
        memory_match = MEMORY_TAG_REGEX.search(xml_content)
        if memory_match:
            result.memory_block = memory_match.group(1).strip()

        if not cleaned:
            return ParseResult(errors=["Empty input after sanitization"])

        edits = _collect_edits(cleaned)
        if not edits:
            return ParseResult(errors=["No <edit> elements found (expecting OPX)"])

        for idx, edit in enumerate(edits, start=1):
            action, error = _build_file_action(edit, idx)
            if action:
                result.file_actions.append(action)
            elif error:
                result.errors.append(error)

    except Exception as e:
        result.errors.append(f"Failed to parse OPX: {e}")

    return result


def _collect_edits(xml: str) -> list[ParsedEdit]:
    """Thu thap tat ca <edit> elements tu XML string"""
    edits: list[ParsedEdit] = []

    # Self-closing edits: <edit ... />
    for match in SELF_CLOSING_REGEX.finditer(xml):
        edits.append(
            ParsedEdit(
                index=match.start(),
                attrs=_parse_attributes(match.group(1) or ""),
                body=None,
            )
        )

    # Paired edits: <edit ...>...</edit>
    for match in PAIRED_REGEX.finditer(xml):
        edits.append(
            ParsedEdit(
                index=match.start(),
                attrs=_parse_attributes(match.group(1) or ""),
                body=match.group(2) or "",
            )
        )

    # Sort theo vi tri xuat hien trong XML
    return sorted(edits, key=lambda e: e.index)


def _build_file_action(
    edit: ParsedEdit, display_index: int
) -> tuple[Optional[FileAction], Optional[str]]:
    """Xay dung FileAction tu ParsedEdit"""
    file_path = edit.attrs.get("file")
    op = (edit.attrs.get("op") or "").lower()

    if file_path and op:
        action_type = _map_op_to_action(op)
        if not action_type:
            return None, f'Edit #{display_index}: unknown op="{op}"'

        file_action = FileAction(
            path=file_path, action=action_type, root=edit.attrs.get("root"), changes=[]
        )

        try:
            _apply_op_handler(op, edit, file_action)
            return file_action, None
        except Exception as e:
            return None, f"Edit #{display_index} ({file_path}): {e}"

    # Missing required attributes
    attrs_str = " ".join(f'{k}="{v}"' for k, v in edit.attrs.items())
    missing = []
    if not file_path:
        missing.append("file")
    if not op:
        missing.append("op")
    return (
        None,
        f'Edit #{display_index}: missing required attribute(s): {" ".join(missing)}. attrs="{attrs_str}"',
    )


def _apply_op_handler(op: str, edit: ParsedEdit, file_action: FileAction) -> None:
    """Apply handler cu the cho tung loai operation"""
    body = edit.body or ""

    if op == "move":
        _handle_move(body, file_action)
    elif op == "remove":
        pass  # Remove khong can body
    elif op in ("new", "replace"):
        _handle_create_or_replace(body, op, file_action)
    elif op == "patch":
        _handle_patch(body, file_action)


def _handle_move(body: str, file_action: FileAction) -> None:
    """Xu ly op="move" - rename/move file"""
    match = TO_TAG_REGEX.search(body)
    if not match:
        raise ValueError('Missing <to file="..."/> for move')

    to_attrs = _parse_attributes(match.group(1) or "")
    new_path = to_attrs.get("file")
    if not new_path:
        raise ValueError('Missing <to file="..."/> for move')

    file_action.new_path = new_path


def _handle_create_or_replace(body: str, op: str, file_action: FileAction) -> None:
    """Xu ly op="new" (create) hoac op="replace" (rewrite)"""
    match = PUT_TAG_REGEX.search(body)
    if not match:
        raise ValueError("Missing <put> block")

    content = _extract_between_markers(match.group(1) or "", "<<<", ">>>") or ""
    description = _extract_why(body) or (
        "Create file" if op == "new" else "Replace file"
    )

    file_action.changes.append(ChangeBlock(description=description, content=content))


def _handle_patch(body: str, file_action: FileAction) -> None:
    """Xu ly op="patch" - search and replace"""
    find_match = FIND_TAG_REGEX.search(body)
    put_match = PUT_TAG_REGEX.search(body)

    if not find_match or not put_match:
        raise ValueError("Missing <find> or <put> for patch")

    find_attrs = _parse_attributes(find_match.group(1) or "")
    occurrence = _normalize_occurrence(find_attrs.get("occurrence"))

    search = _extract_between_markers(find_match.group(2) or "", "<<<", ">>>")
    if not search:
        raise ValueError("Empty or missing marker block in <find>")

    content = _extract_between_markers(put_match.group(1) or "", "<<<", ">>>") or ""
    description = _extract_why(body) or "Patch region"

    file_action.changes.append(
        ChangeBlock(
            description=description,
            search=search,
            content=content,
            occurrence=occurrence,
        )
    )


def _normalize_occurrence(
    occurrence_raw: Optional[str],
) -> Optional[Union[Literal["first", "last"], int]]:
    """Chuyen doi occurrence attribute thanh typed value"""
    if not occurrence_raw:
        return None

    normalized = occurrence_raw.lower()
    if normalized in ("first", "last"):
        return normalized  # type: ignore

    try:
        numeric = int(normalized)
        if numeric > 0:
            return numeric
    except ValueError:
        pass

    return None


def _extract_why(body: str) -> Optional[str]:
    """Extract description tu <why> tag neu co"""
    match = WHY_TAG_REGEX.search(body)
    if match:
        return match.group(1).strip()
    return None


def _extract_between_markers(text: str, start: str, end: str) -> Optional[str]:
    """
    Extract content between <<< and >>> markers.

    Bao gom auto-heal cho truong hop chat/markdown truncate markers:
    - < hoac << tren mot dong -> coi nhu <<<
    - > hoac >> tren mot dong -> coi nhu >>>
    """
    s = text.strip()

    # Auto-heal truncated markers (giu nguyen logic tu TypeScript)
    s = re.sub(r"^[ \t]*<\s*$", "<<<", s, flags=re.MULTILINE)
    s = re.sub(r"^[ \t]*<<\s*$", "<<<", s, flags=re.MULTILINE)
    s = re.sub(r"^[ \t]*>\s*$", ">>>", s, flags=re.MULTILINE)
    s = re.sub(r"^[ \t]*>>\s*$", ">>>", s, flags=re.MULTILINE)

    first = s.find(start)
    if first == -1:
        return None

    last = s.rfind(end)
    if last == -1 or last <= first:
        return None

    # Skip whitespace sau start marker
    start_idx = first + len(start)
    while start_idx < len(s) and s[start_idx] in " \t\r\n":
        start_idx += 1

    # Skip whitespace truoc end marker
    end_idx = last - 1
    while end_idx >= 0 and s[end_idx] in " \t\r\n":
        end_idx -= 1

    if end_idx < start_idx:
        return ""

    return s[start_idx : end_idx + 1]


def _sanitize_response(raw: str) -> str:
    """
    Strip leading/trailing noise: code fences, chat preambles/epilogues.
    Giu lai slice tu first <edit|opx> den last </edit|/opx>.
    """
    s = raw.strip()
    if not s:
        return ""

    # Remove triple backtick fences
    if s.startswith("```"):
        s = re.sub(r"^```[\w-]*\s*\n?", "", s)
    if s.endswith("```"):
        s = re.sub(r"\n?```\s*$", "", s)

    # Tim start position (opx hoac edit, cai nao den truoc)
    opx_start = s.find("<opx")
    edit_start = s.find("<edit ")

    start_options = [i for i in [opx_start, edit_start] if i >= 0]
    if start_options:
        start_idx = min(start_options)
        s = s[start_idx:]

    # Tim end position (last closing tag)
    last_close_edit = s.rfind("</edit>")
    last_close_opx = s.rfind("</opx>")
    last_close = max(last_close_edit, last_close_opx)

    if last_close > -1:
        is_opx = s[last_close:].lower().startswith("</opx>")
        tag_len = 6 if is_opx else 7
        end = last_close + tag_len
        s = s[:end]

    return s.strip()


def _parse_attributes(attr_string: str) -> dict[str, str]:
    """Parse attributes tu tag string thanh dict"""
    attrs: dict[str, str] = {}

    for match in ATTR_REGEX.finditer(attr_string):
        key = match.group(1).lower()
        value = match.group(2) if match.group(2) is not None else match.group(3) or ""
        attrs[key] = value

    return attrs


def _map_op_to_action(
    op: str,
) -> Optional[Literal["create", "rewrite", "modify", "delete", "rename"]]:
    """Map OPX op attribute sang FileAction action type"""
    mapping = {
        "new": "create",
        "patch": "modify",
        "replace": "rewrite",
        "remove": "delete",
        "move": "rename",
    }
    return mapping.get(op)  # type: ignore
