"""
OPX (Overwrite Patch XML) Parser

Port truc tiep tu: src/utils/xml-parser.ts
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
# Sử dụng negative lookahead (?:(?!<\s*edit\b)[\s\S])*? trong thân tag
# để ngăn regex nhảy qua thẻ <edit> kế tiếp khi block trước thiếu thẻ đóng </edit>.
PAIRED_REGEX = re.compile(
    r"<\s*edit\b((?:[^/>]|/[^>])*?)>\s*((?:(?!<\s*edit\b)[\s\S])*?)<\s*/\s*edit\s*>",
    re.IGNORECASE,
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
    # Collect positions to prevent PAIRED_REGEX from double-matching
    self_closing_positions: set[int] = set()
    for match in SELF_CLOSING_REGEX.finditer(xml):
        edits.append(
            ParsedEdit(
                index=match.start(),
                attrs=_parse_attributes(match.group(1) or ""),
                body=None,
            )
        )
        self_closing_positions.add(match.start())

    # Paired edits: <edit ...>...</edit>
    # Skip positions already claimed by self-closing matches to avoid duplicates.
    # This prevents PAIRED_REGEX's [^>]* from matching the / in self-closing />
    # and producing a spurious paired edit that spans to the next </edit>.
    for match in PAIRED_REGEX.finditer(xml):
        if match.start() not in self_closing_positions:
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

    content = _extract_between_markers(match.group(1) or "", "<<<", ">>>")
    if content is None:
        raise ValueError("Missing <<< >>> marker block in <put>")
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

    content = _extract_between_markers(put_match.group(1) or "", "<<<", ">>>")
    if content is None:
        raise ValueError("Missing <<< >>> marker block in <put>")
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


def _trim_content(s: str, content_start: int, content_end: int) -> str:
    """
    Extract va trim whitespace tu content giua hai vi tri boundary.

    Args:
        s: Text buffer goc (KHONG bi modify)
        content_start: Vi tri bat dau content (ngay sau start marker)
        content_end: Vi tri ket thuc content (ngay truoc end marker)

    Returns:
        Trimmed content string, hoac "" neu rong
    """
    # Skip leading whitespace
    while content_start < len(s) and s[content_start] in " \t\r\n":
        content_start += 1

    # Skip trailing whitespace
    end_idx = content_end - 1
    while end_idx >= 0 and s[end_idx] in " \t\r\n":
        end_idx -= 1

    if end_idx < content_start:
        return ""

    return s[content_start : end_idx + 1]


def _extract_between_markers(text: str, start: str, end: str) -> Optional[str]:
    """
    Extract content between <<< and >>> markers.

    Two-phase strategy:
    1. Fast path: tim <<< va >>> truc tiep, KHONG modify text.
       Content duoc giu nguyen 100%. Xu ly 99% truong hop.
    2. Slow path: neu marker khong tim thay, dung position-based detection
       tim lone < hoac > nhu truncated marker. Text buffer KHONG BAO GIO
       bi modify — chi xac dinh vi tri boundary.

    Viec KHONG dung re.sub global la critical: tranh corrupt code content
    chua > hoac < tren dong rieng (HTML closing bracket, XML template, etc.)
    """
    s = text.strip()

    # ── Fast path: standard markers ──────────────────────────────────
    first = s.find(start)
    last = s.rfind(end)

    if first != -1 and last != -1 and last > first:
        # Ca hai marker tim thay — extract truc tiep, zero modification
        return _trim_content(s, first + len(start), last)

    # ── Slow path: position-based auto-heal ──────────────────────────
    # Chi chay khi standard markers thieu.
    # KHONG BAO GIO modify text buffer — chi tim vi tri boundary.

    # Xac dinh start boundary
    if first != -1:
        content_start_pos = first + len(start)
    else:
        # Tim lone < tren mot dong nhu truncated <<<
        m = re.search(r"^[ \t]*<\s*$", s, flags=re.MULTILINE)
        if not m:
            return None
        first = m.start()
        content_start_pos = m.end()  # Content bat dau ngay sau lone <

    # Xac dinh end boundary
    if last != -1 and last > first:
        content_end_pos = last
    else:
        # Tim lone > CUOI CUNG tren mot dong sau content_start_pos
        end_pos = -1
        for m in re.finditer(r"^[ \t]*>\s*$", s, flags=re.MULTILINE):
            if m.start() > content_start_pos:
                end_pos = m.start()
        if end_pos == -1:
            return None
        content_end_pos = end_pos

    return _trim_content(s, content_start_pos, content_end_pos)


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


# ============================================================================
# SEARCH/REPLACE (AIDER-STYLE) PARSER IMPLEMENTATION
# ============================================================================

# SR block regex: <<<<<<< SEARCH filename\n...\n=======\n...\n>>>>>>> REPLACE
# Group 1: File path
# Group 2: Optional description
# Group 3: Search block content
# Group 4: Replace block content
_SR_BLOCK_RE = re.compile(
    r"^<{7}[ \t]+SEARCH[ \t]+(\S+)(?:[ \t]+-[ \t]+([^\n\r]*))?[^\n\r]*\r?\n(.*?)^={7}[ \t]*\r?\n(.*?)^>{7}[ \t]+REPLACE[^\n\r]*$",
    re.MULTILINE | re.DOTALL,
)

# SR delete regex: <<<<<<< DELETE filename\n=======\n>>>>>>> DELETE
# Group 1: File path
_SR_DELETE_RE = re.compile(
    r"^<{7}\s+DELETE\s+(\S+)[^\n]*(?:\n={7}\s*)?\n>{7}\s+DELETE[^\n]*$",
    re.MULTILINE,
)

# SR rename regex: <<<<<<< RENAME old_filename\n=======\nnew_filename\n>>>>>>> RENAME
# Group 1: Old file path
# Group 2: Content between RENAME and ======= (usually empty/description)
# Group 3: New file path
_SR_RENAME_RE = re.compile(
    r"^<{7}\s+RENAME\s+(\S+)[^\n]*\n(.*?)^={7}\s*\n(.*?)^>{7}\s+RENAME[^\n]*$",
    re.MULTILINE | re.DOTALL,
)


def parse_search_replace_response(text: str) -> ParseResult:
    """
    Phân tích phản hồi chứa các khối Search/Replace (Aider-style).

    Hàm này duyệt qua văn bản, trích xuất tất cả các khối được phân cách bởi
    <<<<<<< SEARCH, <<<<<<< DELETE, hoặc <<<<<<< RENAME, gom nhóm chúng theo đường dẫn file
    và tạo ra danh sách FileAction tương thích với hệ thống.
    """
    result = ParseResult()

    try:
        if text is None:
            return ParseResult(errors=["Input is None"])

        # Trích xuất memory block từ phản hồi thô (trước khi clean)
        memory_match = MEMORY_TAG_REGEX.search(text)
        if memory_match:
            result.memory_block = memory_match.group(1).strip()

        # Chuẩn hóa dòng xuống để tránh lỗi do carriage return (\r\n) trên Windows
        cleaned = text.replace("\r\n", "\n")

        actions_by_path: dict[str, FileAction] = {}
        found_any = False

        # 1. Parse SEARCH/REPLACE blocks (create hoặc modify)
        for match in _SR_BLOCK_RE.finditer(cleaned):
            found_any = True
            path = match.group(1).strip()

            # Bỏ tiền tố file:// nếu có
            if path.startswith("file://"):
                path = path[7:]

            comment_desc = match.group(2)
            if comment_desc:
                comment_desc = comment_desc.strip()

            search_text = match.group(3)
            replace_text = match.group(4)

            # Theo chuẩn định dạng: SEARCH block trống nghĩa là tạo file mới
            is_create = search_text.strip() == ""
            action_type = "create" if is_create else "modify"

            if path not in actions_by_path:
                actions_by_path[path] = FileAction(
                    path=path, action=action_type, changes=[]
                )

            desc = (
                comment_desc
                if comment_desc
                else ("Create file" if is_create else "Search/Replace patch")
            )

            block = ChangeBlock(
                description=desc,
                content=replace_text.rstrip("\n"),
                search=None if is_create else search_text.rstrip("\n"),
            )
            actions_by_path[path].changes.append(block)

        # 2. Parse DELETE blocks
        for match in _SR_DELETE_RE.finditer(cleaned):
            found_any = True
            path = match.group(1).strip()

            if path.startswith("file://"):
                path = path[7:]

            actions_by_path[path] = FileAction(path=path, action="delete", changes=[])

        # 3. Parse RENAME/MOVE blocks
        for match in _SR_RENAME_RE.finditer(cleaned):
            found_any = True
            path = match.group(1).strip()

            if path.startswith("file://"):
                path = path[7:]

            new_path = match.group(3).strip()
            if new_path.startswith("file://"):
                new_path = new_path[7:]

            actions_by_path[path] = FileAction(
                path=path, action="rename", new_path=new_path, changes=[]
            )

        if not found_any:
            result.errors.append("Không tìm thấy khối Search/Replace hợp lệ nào.")
        else:
            result.file_actions = list(actions_by_path.values())

    except Exception as e:
        result.errors.append(f"Lỗi khi parse Search/Replace: {e}")

    return result


def _looks_like_opx(text: str) -> bool:
    """Kiểm tra nhanh xem văn bản có chứa cấu trúc thẻ OPX/XML hay không"""
    return bool(re.search(r"<\s*edit\b|<\s*opx\b", text, re.IGNORECASE))


def _looks_like_search_replace(text: str) -> bool:
    """Kiểm tra nhanh xem văn bản có chứa cấu trúc SEARCH, DELETE hoặc RENAME của Search/Replace hay không"""
    return bool(re.search(r"^<{7}\s+(?:SEARCH|DELETE|RENAME)\b", text, re.MULTILINE))


def parse_any_response(text: str) -> ParseResult:
    """
    Điểm nhận diện và phân tích cú pháp chung (Unified entry point).
    Tự động phát hiện xem chuỗi phản hồi dùng định dạng OPX hay Search/Replace.
    """
    if text is None:
        return ParseResult(errors=["Input is None"])
    if not isinstance(text, str):
        return ParseResult(errors=[f"Invalid input type: {type(text).__name__}"])

    cleaned = text.strip()

    is_opx = _looks_like_opx(cleaned)
    is_sr = _looks_like_search_replace(cleaned)

    if is_opx:
        result = parse_opx_response(cleaned)
        if result.file_actions:
            return result

    if is_sr:
        result = parse_search_replace_response(cleaned)
        if result.file_actions:
            return result

    # Fallback: Nếu không parse được gì thành công, trả về kết quả lỗi của định dạng khớp nhất
    if is_opx:
        return parse_opx_response(cleaned)
    if is_sr:
        return parse_search_replace_response(cleaned)

    return ParseResult(
        errors=["Không nhận dạng được định dạng OPX hoặc Search/Replace hợp lệ"]
    )
