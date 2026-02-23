"""
AST Parser - Trich xuat outline (Class, Function, Method) tu source code.

Tao "Repo Map" tuong tu Aider (https://aider.chat/docs/repomap.html):
thay vi gui toan bo code cho LLM, chi gui cau truc (signatures).
Tiet kiem 90%+ tokens so voi nhet raw source code.

Ho tro:
- Python: Dung built-in `ast` module (chinh xac 100%)
- JS/TS/JSX/TSX: Regex heuristic bat class, function, const arrow
- Go/Rust/Java/C#/C/C++/Ruby/PHP/Kotlin/Swift: Regex heuristic co ban

Output format:
    path/to/file.py:
      class AuthManager:
        def login(self, username, password)
        def verify_token(self, token)
      def helper_func(x, y)

Usage:
    from core.utils.ast_parser import generate_repo_map
    repo_map = generate_repo_map(file_paths, workspace_root)
"""

import ast
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Map file extension -> parser function name
_PYTHON_EXTENSIONS = {".py", ".pyw"}
_JS_TS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
_GO_EXTENSIONS = {".go"}
_RUST_EXTENSIONS = {".rs"}
_JAVA_EXTENSIONS = {".java"}
_CSHARP_EXTENSIONS = {".cs"}
_C_CPP_EXTENSIONS = {".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx"}
_RUBY_EXTENSIONS = {".rb"}
_PHP_EXTENSIONS = {".php"}
_KOTLIN_EXTENSIONS = {".kt", ".kts"}
_SWIFT_EXTENSIONS = {".swift"}


def generate_repo_map(
    file_paths: list[str],
    workspace_root: Optional[Path] = None,
    max_files: int = 500,
) -> str:
    """
    Tao Repo Map tu danh sach file paths.

    Quyet toan bo files, trich xuat outline (class/function signatures),
    va gop thanh mot chuoi text gon gang de gui cho LLM.

    Args:
        file_paths: Danh sach absolute paths cua cac source files
        workspace_root: Thu muc goc de tao relative paths
        max_files: Gioi han so file parse (tranh OOM voi repo qua lon)

    Returns:
        Chuoi Repo Map, moi file 1 block voi cac signatures indented
    """
    lines: list[str] = []
    parsed_count = 0

    for file_path_str in sorted(file_paths):
        if parsed_count >= max_files:
            lines.append(f"\n... and {len(file_paths) - max_files} more files")
            break

        file_path = Path(file_path_str)

        # Chi parse files co extension duoc ho tro
        ext = file_path.suffix.lower()
        if not _is_supported_extension(ext):
            continue

        # Trich xuat outline cho file nay
        outline = extract_file_outline(file_path)
        if not outline:
            continue

        # Hien thi relative path neu co workspace root
        if workspace_root:
            try:
                display_path = file_path.relative_to(workspace_root)
            except ValueError:
                display_path = file_path
        else:
            display_path = file_path

        lines.append(f"{display_path}:")
        for item in outline:
            lines.append(f"  {item}")
        lines.append("")  # Blank line giua cac files
        parsed_count += 1

    return "\n".join(lines)


def extract_file_outline(file_path: Path) -> list[str]:
    """
    Trich xuat outline (signatures) cua mot file duy nhat.

    Tu dong chon parser phu hop theo extension.

    Args:
        file_path: Duong dan toi file can parse

    Returns:
        List cac signature strings (co indent cho methods trong class)
    """
    ext = file_path.suffix.lower()

    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, IOError) as e:
        logger.debug("Cannot read file %s: %s", file_path, e)
        return []

    # Gioi han kich thuoc file: bo qua files qua lon (> 500KB)
    if len(source) > 500_000:
        return []

    if ext in _PYTHON_EXTENSIONS:
        return _extract_python_outline(source, file_path)

    # Tat ca ngon ngu khac dung regex heuristics
    return _extract_regex_outline(source, ext)


def _is_supported_extension(ext: str) -> bool:
    """Kiem tra file extension co duoc ho tro hay khong."""
    all_extensions = (
        _PYTHON_EXTENSIONS
        | _JS_TS_EXTENSIONS
        | _GO_EXTENSIONS
        | _RUST_EXTENSIONS
        | _JAVA_EXTENSIONS
        | _CSHARP_EXTENSIONS
        | _C_CPP_EXTENSIONS
        | _RUBY_EXTENSIONS
        | _PHP_EXTENSIONS
        | _KOTLIN_EXTENSIONS
        | _SWIFT_EXTENSIONS
    )
    return ext in all_extensions


# === Python Parser (built-in ast) ===


def _extract_python_outline(source: str, file_path: Path) -> list[str]:
    """
    Parse Python source code bang built-in ast module.

    Chinh xac 100% cho Python syntax. Trich xuat:
    - Top-level functions: def func_name(args)
    - Classes: class ClassName(bases)
    - Methods trong class: def method(self, args)

    Args:
        source: Noi dung file Python
        file_path: Duong dan file (de log warning)

    Returns:
        List signatures, methods duoc indent them 2 spaces
    """
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        logger.debug("Syntax error parsing %s, falling back to regex", file_path)
        return _extract_regex_outline(source, ".py")

    items: list[str] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            # Top-level function
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            args_str = _format_python_args(node.args)
            items.append(f"{prefix} {node.name}({args_str})")

        elif isinstance(node, ast.ClassDef):
            # Class + methods
            bases = ", ".join(_format_python_expr(b) for b in node.bases)
            class_sig = f"class {node.name}({bases})" if bases else f"class {node.name}"
            items.append(f"{class_sig}:")

            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                    prefix = (
                        "async def"
                        if isinstance(child, ast.AsyncFunctionDef)
                        else "def"
                    )
                    args_str = _format_python_args(child.args)
                    items.append(f"  {prefix} {child.name}({args_str})")

    return items


def _format_python_args(args: ast.arguments) -> str:
    """
    Format function arguments thanh chuoi gon.

    Chi lay ten arguments, bo qua default values va annotations
    de giu Repo Map nhe nhat co the.

    Args:
        args: ast.arguments node

    Returns:
        Chuoi arguments, vd: "self, username, password"
    """
    parts: list[str] = []

    for arg in args.args:
        parts.append(arg.arg)

    if args.vararg:
        parts.append(f"*{args.vararg.arg}")
    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")

    return ", ".join(parts)


def _format_python_expr(node: ast.expr) -> str:
    """Format mot AST expression node thanh chuoi don gian."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_format_python_expr(node.value)}.{node.attr}"
    if isinstance(node, ast.Constant):
        return repr(node.value)
    return "..."


# === Regex Heuristic Parser (JS/TS/Go/Rust/Java/C#/etc.) ===

# Regex patterns cho cac ngon ngu khac nhau
# Moi pattern bat co ban: class/interface/struct/enum declarations va function signatures

_REGEX_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    # JS/TS: class, function, const arrow, export default
    "js_ts": [
        re.compile(
            r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(\w+)",
            re.MULTILINE,
        ),
        re.compile(
            r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)\s*\(",
            re.MULTILINE,
        ),
        re.compile(
            r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(",
            re.MULTILINE,
        ),
        re.compile(r"^\s*(?:export\s+)?interface\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*(?:export\s+)?(?:const\s+)?enum\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*(?:export\s+)?type\s+(\w+)\s*=", re.MULTILINE),
    ],
    # Go
    "go": [
        re.compile(r"^\s*type\s+(\w+)\s+struct\s*\{", re.MULTILINE),
        re.compile(r"^\s*type\s+(\w+)\s+interface\s*\{", re.MULTILINE),
        re.compile(r"^\s*func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(", re.MULTILINE),
    ],
    # Rust
    "rust": [
        re.compile(r"^\s*(?:pub\s+)?struct\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*(?:pub\s+)?enum\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*(?:pub\s+)?trait\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*impl(?:\s*<.*?>)?\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", re.MULTILINE),
    ],
    # Java / C#
    "java_csharp": [
        re.compile(
            r"^\s*(?:public|private|protected|internal)?\s*(?:static\s+)?(?:abstract\s+)?class\s+(\w+)",
            re.MULTILINE,
        ),
        re.compile(
            r"^\s*(?:public|private|protected)?\s*interface\s+(\w+)", re.MULTILINE
        ),
        re.compile(r"^\s*(?:public|private|protected)?\s*enum\s+(\w+)", re.MULTILINE),
        re.compile(
            r"^\s*(?:public|private|protected|internal)?\s*(?:static\s+)?(?:async\s+)?(?:virtual\s+)?(?:override\s+)?\w+(?:<.*?>)?\s+(\w+)\s*\(",
            re.MULTILINE,
        ),
    ],
    # C/C++
    "c_cpp": [
        re.compile(r"^\s*(?:class|struct)\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*(?:enum)\s+(?:class\s+)?(\w+)", re.MULTILINE),
        re.compile(
            r"^\s*(?:static\s+)?(?:inline\s+)?(?:virtual\s+)?(?:const\s+)?\w+[\w\s\*&:<>]*\s+(\w+)\s*\(",
            re.MULTILINE,
        ),
    ],
    # Ruby
    "ruby": [
        re.compile(r"^\s*class\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*module\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*def\s+(\w+)", re.MULTILINE),
    ],
    # PHP
    "php": [
        re.compile(r"^\s*(?:abstract\s+)?class\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*interface\s+(\w+)", re.MULTILINE),
        re.compile(
            r"^\s*(?:public|private|protected)?\s*function\s+(\w+)", re.MULTILINE
        ),
    ],
    # Kotlin
    "kotlin": [
        re.compile(r"^\s*(?:data\s+)?class\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*interface\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*(?:fun|suspend\s+fun)\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*object\s+(\w+)", re.MULTILINE),
    ],
    # Swift
    "swift": [
        re.compile(r"^\s*(?:public\s+|private\s+|open\s+)?class\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*(?:public\s+)?struct\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*(?:public\s+)?protocol\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*(?:public\s+|private\s+)?func\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*(?:public\s+)?enum\s+(\w+)", re.MULTILINE),
    ],
}

# Map extension -> pattern group key
_EXT_TO_PATTERN_GROUP: dict[str, str] = {}
for ext in _JS_TS_EXTENSIONS:
    _EXT_TO_PATTERN_GROUP[ext] = "js_ts"
for ext in _GO_EXTENSIONS:
    _EXT_TO_PATTERN_GROUP[ext] = "go"
for ext in _RUST_EXTENSIONS:
    _EXT_TO_PATTERN_GROUP[ext] = "rust"
for ext in _JAVA_EXTENSIONS:
    _EXT_TO_PATTERN_GROUP[ext] = "java_csharp"
for ext in _CSHARP_EXTENSIONS:
    _EXT_TO_PATTERN_GROUP[ext] = "java_csharp"
for ext in _C_CPP_EXTENSIONS:
    _EXT_TO_PATTERN_GROUP[ext] = "c_cpp"
for ext in _RUBY_EXTENSIONS:
    _EXT_TO_PATTERN_GROUP[ext] = "ruby"
for ext in _PHP_EXTENSIONS:
    _EXT_TO_PATTERN_GROUP[ext] = "php"
for ext in _KOTLIN_EXTENSIONS:
    _EXT_TO_PATTERN_GROUP[ext] = "kotlin"
for ext in _SWIFT_EXTENSIONS:
    _EXT_TO_PATTERN_GROUP[ext] = "swift"
# Python fallback (chi dung khi ast.parse fail)
for ext in _PYTHON_EXTENSIONS:
    _EXT_TO_PATTERN_GROUP[ext] = "ruby"  # Python syntax tuong tu Ruby cho regex


def _extract_regex_outline(source: str, ext: str) -> list[str]:
    """
    Trich xuat outline bang regex heuristics.

    Khong chinh xac 100% nhung du tot de cung cap thong tin
    structural cho LLM. Muc dich: "better than nothing".

    Args:
        source: Noi dung source code
        ext: File extension (vd: ".ts", ".go")

    Returns:
        List cac symbol names tim thay
    """
    group_key = _EXT_TO_PATTERN_GROUP.get(ext)
    if not group_key:
        return []

    patterns = _REGEX_PATTERNS.get(group_key, [])
    if not patterns:
        return []

    seen: set[str] = set()
    items: list[str] = []

    for pattern in patterns:
        for match in pattern.finditer(source):
            name = match.group(1)
            if name and name not in seen:
                seen.add(name)
                # Lay dong chua match va trim de co full signature
                line = match.group(0).strip()
                # Cat bo phan body (chi giu signature)
                line = line.rstrip("{").strip()
                items.append(line)

    return items
