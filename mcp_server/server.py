"""
Synapse MCP Server - Cung cap cac tools cho AI clients (Cursor, Copilot, Antigravity).

Chay qua stdio transport, khong can UI. Su dung lai logic co san cua Synapse
de AI co the kham pha, doc, phan tich va build prompt tu workspace.

Cach chay:
    python main_window.py --run-mcp /path/to/workspace
    # Hoac voi AppImage:
    ./Synapse.AppImage --run-mcp /path/to/workspace
"""

import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from mcp.server.fastmcp import FastMCP

# Dam bao project root nam trong sys.path de import duoc cac module cua Synapse
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logger = logging.getLogger("synapse.mcp")

# Regex validate git ref name: chi cho phep ky tu an toan (branch, tag, commit hash).
# Khong cho phep bat dau bang '-' de chan git option injection (vi du: '--output=/tmp/pwned').
_SAFE_GIT_REF = re.compile(r"^[A-Za-z0-9_./@^~][A-Za-z0-9_./@^~\-]*$")
# Timeout cho moi lenh git subprocess (seconds). 15s la du cho local git operations.
_GIT_TIMEOUT = 15
# Regex cho find_references: loc string literals va inline comments truoc khi match symbol
_INLINE_COMMENT_RE = re.compile(r"(#|//).*$")
_STRING_LITERAL_RE: re.Pattern[str] = re.compile(
    r'"(?:[^"\\]|\\.)*"|' + r"'(?:[^'\\]|\\.)*'"
)

# Khoi tao MCP Server voi ten hien thi cho AI clients
mcp = FastMCP(
    "Synapse Desktop",
    instructions=(
        "Synapse Desktop - AI-powered codebase exploration toolkit with 15 tools.\n"
        "\n"
        "USE YOUR BUILT-IN TOOLS FOR BASIC OPERATIONS:\n"
        "  - Reading files -> use your native read_file, unless files are too large\n"
        "  - Listing directories -> use your native list_dir / ls\n"
        "  - Searching text -> use your native grep / search\n"
        "  - Running commands -> use your native terminal / bash\n"
        "\n"
        "USE SYNAPSE TOOLS FOR ADVANCED TASKS YOUR BUILT-IN TOOLS DON'T HAVE:\n"
        "  - get_codemap / get_symbols - Tree-sitter AST extraction (signatures without bodies)\n"
        "  - estimate_tokens - accurate LLM token counting\n"
        "  - get_imports_graph - cross-file dependency resolution\n"
        "  - diff_summary - function-level git change analysis\n"
        "  - build_prompt - structured prompt packaging\n"
        "  - get_project_structure - detect frameworks and codebase scale\n"
        "\n"
        "[CRITICAL] WORKFLOW:\n"
        "  1. Start with get_project_structure to understand the codebase\n"
        "  2. Use get_codemap BEFORE reading files to save tokens\n"
        "  3. Use estimate_tokens before generating a context package\n"
        "\n"
        "All tools have detailed docstrings explaining when to use them over your native tools."
    ),
)


# Ham start_session giup tu dong discover cau truc du an, cac framework va technical debt
@mcp.tool()
def start_session(workspace_path: str) -> str:
    """Start a new session by auto-discovering project structure, organization, and technical debt.

    WHY USE THIS OVER BUILT-IN: Combines 3 calls into one to give you an immediate high-level summary.
    However, you can also use your built-in tools recursively if you prefer.

    This is a convenience tool that runs the essential discovery sequence:
    1. get_project_structure - Understand scale, languages, frameworks
    2. list_directories - See folder organization
    3. find_todos - Check technical debt

    Call this FIRST when starting work on a new codebase or task.
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    try:
        # 1. Project structure
        structure = get_project_structure(workspace_path)

        # 2. Directory tree (depth 2 for quick overview)
        tree = list_directories(workspace_path, max_depth=2)

        # 3. Technical debt scan
        todos_result = find_todos(workspace_path, include_hack=True)
        # Truncate if too long
        todos_preview = (
            todos_result
            if len(todos_result) < 800
            else todos_result[:800] + "\n... (truncated)"
        )

        return (
            f"{'=' * 60}\n"
            f"SESSION INITIALIZED [OK]\n"
            f"{'=' * 60}\n\n"
            f"{structure}\n\n"
            f"{'=' * 60}\n"
            f"DIRECTORY STRUCTURE\n"
            f"{'=' * 60}\n"
            f"{tree}\n\n"
            f"{'=' * 60}\n"
            f"TECHNICAL DEBT\n"
            f"{'=' * 60}\n"
            f"{todos_preview}\n\n"
            f"{'=' * 60}\n"
            f"Next steps:\n"
            f"  - Use get_codemap to explore specific files\n"
            f"  - Use read_file when you need implementation details\n"
            f"  - Use get_imports_graph to understand module coupling\n"
            f"{'=' * 60}"
        )
    except Exception as e:
        logger.error("start_session error: %s", e)
        return f"Error initializing session: {e}"


# ===========================================================================
# Tool 2: list_files - Liet ke tat ca files trong workspace
# ===========================================================================
# Ham list_files liet ke tat ca file trong workspace, co ho tro filter theo extension
@mcp.tool()
def list_files(
    workspace_path: str,
    extensions: Optional[List[str]] = None,
) -> str:
    """List all files in the workspace, automatically respecting .gitignore and skipping hidden files.

    WHY USE THIS OVER BUILT-IN: Use YOUR BUILT-IN list_dir/ls for simple directories.
    Use this to get a flat list of ALL files recursively in the project, automatically
    respecting .gitignore, which is useful to feed into other tools.

    Returns one relative path per line. Use the `extensions` filter to narrow results
    (e.g., [".py", ".ts"] to find only Python and TypeScript files).

    When to use: You need to know exactly which files exist, find files by extension,
    or get a flat list to pass to other tools like read_file or get_codemap.

    Args:
        workspace_path: Absolute path to the workspace root directory.
        extensions: Optional list of extensions to filter by (e.g., [".py", ".js"]). None returns all files.
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    try:
        from services.workspace_index import collect_files_from_disk

        all_files = collect_files_from_disk(ws, workspace_path=ws)

        # Loc theo extension neu co yeu cau
        if extensions:
            ext_set = {
                e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions
            }
            all_files = [f for f in all_files if Path(f).suffix.lower() in ext_set]

        # Chuyen thanh duong dan tuong doi
        result_lines = []
        for f in sorted(all_files):
            try:
                rel = os.path.relpath(f, ws)
                result_lines.append(rel)
            except ValueError:
                result_lines.append(f)

        if not result_lines:
            return "No files found matching the criteria."

        return f"Found {len(result_lines)} files:\n" + "\n".join(result_lines)

    except Exception as e:
        logger.error("list_files error: %s", e)
        return f"Error listing files: {e}"


# Ham list_directories hien thi cau truc thu muc duoi dang cay (nhu lenh tree)
@mcp.tool()
def list_directories(
    workspace_path: str,
    max_depth: int = 3,
) -> str:
    """Show the directory tree structure of the workspace (similar to the `tree` command).

    WHY USE THIS OVER BUILT-IN: Use YOUR BUILT-IN list_dir/ls for simple exploration.
    Use this to see the overall shape of the project recursively up to max_depth.

    Quickly understand how a project is organized - folder hierarchy, module boundaries,
    and naming conventions - without listing every file.

    When to use: First step when exploring an unfamiliar codebase, or when you need to
    understand where specific modules/packages live before reading files.

    Args:
        workspace_path: Absolute path to the workspace root directory.
        max_depth: Maximum directory depth to display (default: 3, max: 10).
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    max_depth = min(max(1, max_depth), 10)

    # Danh sach thu muc can bo qua
    SKIP_DIRS = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        "dist",
        "build",
        ".tox",
        ".eggs",
        ".ruff_cache",
        ".next",
        ".nuxt",
    }

    lines: list[str] = [ws.name + "/"]

    def _walk(current: Path, prefix: str, depth: int) -> None:
        """De quy duyet cay thu muc voi ASCII connectors. Dung os.scandir de tranh tao Path objects thua."""
        if depth > max_depth:
            return

        try:
            # Fix #4: Dung os.scandir thay vi iterdir() de tranh tao DirEntry objects thua
            dirs = sorted(
                (
                    entry
                    for entry in os.scandir(current)
                    if entry.is_dir(follow_symlinks=False)
                    and entry.name not in SKIP_DIRS
                    and not entry.name.startswith(".")
                ),
                key=lambda e: e.name.lower(),
            )
        except PermissionError:
            return

        for i, d in enumerate(dirs):
            is_last = i == len(dirs) - 1
            connector = "--- " if is_last else "|-- "
            lines.append(f"{prefix}{connector}{d.name}/")

            new_prefix = prefix + ("    " if is_last else "|   ")
            _walk(Path(d.path), new_prefix, depth + 1)

    _walk(ws, "", 1)

    if len(lines) == 1:
        return f"{ws.name}/ (empty or all directories are ignored)"

    return "\n".join(lines)


# ===========================================================================
# Tool 3: read_file_range - Doc noi dung file voi line range support
# ===========================================================================
# Ham read_file_range doc noi dung file theo khoang dong tu chon
@mcp.tool()
def read_file_range(
    workspace_path: str,
    relative_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> str:
    """Read file contents with optional line range support (enhanced version).

    WHY USE THIS OVER BUILT-IN: Use YOUR BUILT-IN read_file for full files.
    Use this when you specifically need to read a small segment of a massive file
    to save token bandwidth, since some AI clients don't support line ranges natively.

    This is Synapse's enhanced file reader with line range support.
    Use this when you need to read specific sections of large files to save tokens.
    For simple full-file reads, use your client's built-in read_file tool.

    Args:
        workspace_path: Absolute path to the workspace root directory.
        relative_path: Relative path to the file from workspace root (e.g., "src/main.py").
        start_line: First line to read (1-indexed). Omit to start from beginning.
        end_line: Last line to read (1-indexed). Omit to read until end of file.
    """
    ws = Path(workspace_path).resolve()
    file_path = (ws / relative_path).resolve()

    # Fix #1: Dung is_relative_to() thay vi startswith() de chong path traversal dung cach
    if not file_path.is_relative_to(ws):
        return "Error: Path traversal detected. File must be within workspace."

    if not file_path.is_file():
        return f"Error: File not found: {relative_path}"

    try:
        file_size = file_path.stat().st_size

        # Cat theo khoang dong neu co yeu cau
        if start_line is not None or end_line is not None:
            with file_path.open("r", encoding="utf-8", errors="replace") as fh:
                all_lines = fh.readlines()
            total_lines = len(all_lines)
            s = max(1, start_line or 1) - 1
            e = min(total_lines, end_line or total_lines)
            content = "".join(all_lines[s:e])
            # Token estimate tu slice thuc te (slice nho nen encode() khong ton kem)
            estimated_tokens = len(content.encode("utf-8")) // 4
            line_info = f"Showing lines {s + 1}-{e} of {total_lines}"
        else:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            # Fix: dung splitlines() thay vi count("\n")+1 de tranh dem thua khi file ket thuc bang \n
            total_lines = len(content.splitlines())
            # Token estimate tu file size (tranh encode() toan bo content)
            estimated_tokens = file_size // 4
            line_info = f"Total lines: {total_lines}"

        header = f"File: {relative_path}\n{line_info} | ~{estimated_tokens:,} tokens\n{'=' * 60}\n"
        return header + content

    except Exception as e:
        logger.error("read_file error for %s: %s", relative_path, e)
        return f"Error reading file: {e}"


# Ham get_codemap dung Tree-sitter de trich xuat skeleton cua code (signatures, class defs) giup tiet kiem token
@mcp.tool()
def get_codemap(
    workspace_path: str,
    file_paths: List[str],
) -> str:
    """Extract code structure (function signatures, class definitions, imports) from files.

    WHY USE THIS OVER BUILT-IN: Your built-in read_file returns the ENTIRE file.
    get_codemap uses Tree-sitter AST parsing to extract only the API skeleton -
    function signatures, class declarations, type annotations - saving 70-90% tokens.
    No built-in tool can do this.

    Uses Tree-sitter to parse source code and return only the skeleton - function
    signatures, class declarations, and type information - WITHOUT implementation
    bodies. This gives you a complete understanding of module APIs while using
    a fraction of the tokens compared to reading full files.

    When to use: ALWAYS use this before read_file when exploring code. It lets you
    understand the shape of modules, find the right function to dig into, and map
    out dependencies - all at minimal token cost. Only use read_file after this
    when you need the actual implementation.

    Args:
        workspace_path: Absolute path to the workspace root directory.
        file_paths: List of relative file paths to analyze (e.g., ["src/auth.py", "src/db.py"]).
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    # Chuyen relative paths thanh absolute paths
    abs_paths: set[str] = set()
    for rp in file_paths:
        fp = (ws / rp).resolve()
        if not fp.is_relative_to(ws):
            return f"Error: Path traversal detected for: {rp}"
        if fp.is_file():
            abs_paths.add(str(fp))
        else:
            return f"Error: File not found: {rp}"

    if not abs_paths:
        return "Error: No valid files provided."

    try:
        from core.prompt_generator import generate_smart_context

        result = generate_smart_context(
            selected_paths=abs_paths,
            include_relationships=True,
            workspace_root=ws,
            use_relative_paths=True,
        )
        if not result or not result.strip():
            return "No code structure could be extracted from the provided files."
        return result

    except Exception as e:
        logger.error("get_codemap error: %s", e)
        return f"Error generating codemap: {e}"


# ===========================================================================
# Tool 5: get_project_structure - Tom tat tong quan du an
# ===========================================================================
# Ham get_project_structure phan tich tong quan du an nhu so luong file, kich thuoc va framework
@mcp.tool()
def get_project_structure(
    workspace_path: str,
) -> str:
    """Get a high-level summary of the project: total files, breakdown by file type, detected frameworks, and estimated token count.

    WHY USE THIS OVER BUILT-IN: Your built-in list_dir shows file names but can't
    detect frameworks (Django, Next.js, Rust, etc.), count total tokens, or give
    you a statistical breakdown. This gives you the big picture in one call.

    This is the fastest way to understand what kind of project you're working with,
    its scale, and which technologies are in use (Python/Django, Node.js/Next.js, Rust, etc.).

    When to use: ALWAYS call this first when starting work on a codebase. It takes
    milliseconds and tells you the project's language, framework, size, and complexity
    before you dive into any files.

    Args:
        workspace_path: Absolute path to the workspace root directory.
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    try:
        from services.workspace_index import collect_files_from_disk
        from collections import Counter

        all_files = collect_files_from_disk(ws, workspace_path=ws)
        total = len(all_files)

        if total == 0:
            return f"Project: {ws.name}\nNo files found (empty or fully ignored)."

        # Dem so luong file theo extension
        ext_counter: Counter[str] = Counter()
        # Fix #3: Dung os.path.getsize (nhanh hon Path.stat()) va try/except per-file
        total_bytes = 0
        for f in all_files:
            ext = Path(f).suffix.lower() or "(no extension)"
            ext_counter[ext] += 1
            try:
                total_bytes += os.path.getsize(f)
            except OSError:
                pass

        # Sap xep theo so luong giam dan
        ext_lines = []
        for ext, count in ext_counter.most_common(20):
            ext_lines.append(f"  {ext:<15} {count:>5} files")

        # Phat hien frameworks
        frameworks = _detect_frameworks(ws)
        fw_line = (
            f"Frameworks: {', '.join(frameworks)}"
            if frameworks
            else "Frameworks: (not detected)"
        )

        estimated_tokens = total_bytes // 4

        return (
            f"Project: {ws.name}\n"
            f"Total files: {total:,}\n"
            f"Total size: {total_bytes:,} bytes (~{estimated_tokens:,} tokens)\n"
            f"{fw_line}\n"
            f"\nFile types:\n" + "\n".join(ext_lines)
        )

    except Exception as e:
        logger.error("get_project_structure error: %s", e)
        return f"Error analyzing project: {e}"


def _detect_frameworks(ws: Path) -> list[str]:
    """Phat hien cac framework dua tren file cau hinh. Fix #6: Dung 1 listdir + set lookup thay vi 12 stat."""
    try:
        root_files = set(os.listdir(ws))
    except OSError:
        return []

    frameworks = []
    markers = {
        "requirements.txt": "Python",
        "pyproject.toml": "Python (modern)",
        "package.json": "Node.js",
        "Cargo.toml": "Rust",
        "go.mod": "Go",
        "pom.xml": "Java/Maven",
        "build.gradle": "Java/Gradle",
        "Gemfile": "Ruby",
        "composer.json": "PHP",
    }
    for filename, fw in markers.items():
        if filename in root_files:
            frameworks.append(fw)

    # Kiem tra them framework cu the
    if "manage.py" in root_files:
        frameworks.append("Django")
    if "next.config.js" in root_files or "next.config.mjs" in root_files:
        frameworks.append("Next.js")
    if "angular.json" in root_files:
        frameworks.append("Angular")

    return frameworks


# Ham manage_selection dung de quan ly danh sach cac file dang duoc chon de build prompt
@mcp.tool()
def manage_selection(
    workspace_path: str,
    action: str = "get",
    paths: Optional[List[str]] = None,
) -> str:
    """Manage the list of currently selected (ticked) files in the Synapse session.

    WHY USE THIS OVER BUILT-IN: When building prompts across multiple tool calls, this lets you
    incrementally add/remove files to a selection, then pass them all to build_prompt
    at once. Useful for complex multi-step context curation.

    This controls which files are included when building prompts. Use it to
    curate the exact set of files that should be part of the AI context.

    Actions:
      "get"   - Return the current selection list.
      "set"   - Replace the entire selection with the provided paths.
      "add"   - Add paths to the existing selection (skips duplicates).
      "clear" - Remove all files from the selection.

    When to use: Before calling build_prompt, use "set" or "add" to choose the
    right files. Use "get" to check what's currently selected. Use "clear" to
    start fresh.

    Args:
        workspace_path: Absolute path to the workspace root directory.
        action: Action to perform - "get", "set", "add", or "clear".
        paths: List of relative file paths (required for "set" and "add" actions).
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    session_file = ws / ".synapse_selection.json"

    if action == "get":
        return _selection_get(session_file, ws)
    elif action == "set":
        return _selection_set(session_file, ws, paths or [])
    elif action == "add":
        return _selection_add(session_file, ws, paths or [])
    elif action == "clear":
        return _selection_clear(session_file)
    else:
        return f"Error: Unknown action '{action}'. Use: get, set, add, clear."


def _selection_get(session_file: Path, ws: Path) -> str:
    """Doc danh sach file dang duoc chon tu file session."""
    import json

    if not session_file.exists():
        return "No selection found. Use action='set' to create one."
    try:
        data = json.loads(session_file.read_text(encoding="utf-8"))
        selected = data.get("selected_files", [])
        if not selected:
            return "Selection is empty."
        return f"Selected {len(selected)} files:\n" + "\n".join(selected)
    except Exception as e:
        return f"Error reading selection: {e}"


def _atomic_write(path: Path, data: str) -> None:
    """Ghi file du lieu theo kieu atomic de tranh mat du lieu khi ghi dong thoi."""
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=path.name,
        suffix=".tmp",
    )
    fd_owned = False
    try:
        f = os.fdopen(tmp_fd, "w", encoding="utf-8")
        fd_owned = True  # os.fdopen thanh cong, no se quan ly fd tu gio
        try:
            f.write(data)
        finally:
            f.close()
        os.replace(tmp_path, str(path))
    except Exception:
        if not fd_owned:
            # os.fdopen that bai truoc khi nhan quyen so huu fd
            try:
                os.close(tmp_fd)
            except OSError:
                pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _selection_set(session_file: Path, ws: Path, paths: list[str]) -> str:
    """Ghi de toan bo danh sach file duoc chon."""
    import json

    # Validate paths
    valid = []
    for rp in paths:
        fp = (ws / rp).resolve()
        if not fp.is_relative_to(ws):
            return f"Error: Path traversal detected for: {rp}"
        if not fp.is_file():
            return f"Error: File not found: {rp}"
        valid.append(rp)

    data = {"selected_files": valid}
    _atomic_write(session_file, json.dumps(data, indent=2))
    return f"Selection updated: {len(valid)} files selected."


def _selection_add(session_file: Path, ws: Path, paths: list[str]) -> str:
    """Them file vao danh sach hien tai."""
    import json

    existing: list[str] = []
    if session_file.exists():
        try:
            data = json.loads(session_file.read_text(encoding="utf-8"))
            existing = data.get("selected_files", [])
        except Exception:
            pass

    existing_set = set(existing)
    added = 0
    for rp in paths:
        fp = (ws / rp).resolve()
        if not fp.is_relative_to(ws):
            return f"Error: Path traversal detected for: {rp}"
        if not fp.is_file():
            return f"Error: File not found: {rp}"
        if rp not in existing_set:
            existing.append(rp)
            existing_set.add(rp)
            added += 1

    data = {"selected_files": existing}
    _atomic_write(session_file, json.dumps(data, indent=2))
    return f"Added {added} files. Total selection: {len(existing)} files."


def _selection_clear(session_file: Path) -> str:
    """Xoa toan bo selection."""
    import json

    data = {"selected_files": []}
    _atomic_write(session_file, json.dumps(data, indent=2))
    return "Selection cleared."


# ============================================================
# Helper: Resolve profile params voi nguyen tac uu tien
# explicit param > profile default > global default
# ============================================================
def _resolve_profile_params(
    profile_name: Optional[str],
    output_format: str,
    include_git_changes: bool,
    instructions: str,
    max_tokens: Optional[int],
    auto_expand_dependencies: bool,
) -> tuple[str, bool, str, Optional[int], bool, Optional[str]]:
    """
    Merge profile defaults vao params, explicit params luon thang.

    Tra ve tuple (output_format, include_git_changes, instructions,
    max_tokens, auto_expand_dependencies, resolved_profile_name).

    Args:
        profile_name: Ten profile (None = khong dung profile)
        output_format: Output format tu caller
        include_git_changes: Git changes flag tu caller
        instructions: User instructions tu caller
        max_tokens: Token limit tu caller
        auto_expand_dependencies: Dependency expansion flag tu caller

    Returns:
        Tuple cac params da resolve, profile_name da validate

    Raises:
        ValueError: Khi profile_name khong ton tai trong registry
    """
    if not profile_name:
        return (
            output_format,
            include_git_changes,
            instructions,
            max_tokens,
            auto_expand_dependencies,
            None,
        )

    from config.prompt_profiles import get_profile, list_profiles

    prof = get_profile(profile_name)
    if prof is None:
        available = ", ".join(list_profiles())
        raise ValueError(f"Unknown profile '{profile_name}'. Available: {available}")

    # Merge: chi ap dung profile default khi caller KHONG truyen explicit
    # Output format: "xml" la default global -> chi override khi caller giu default
    resolved_format = output_format
    if output_format == "xml" and prof.output_format is not None:
        resolved_format = prof.output_format

    # include_git_changes: False la default global -> chi override khi False
    resolved_git = include_git_changes
    if not include_git_changes and prof.include_git_changes is not None:
        resolved_git = prof.include_git_changes

    # Instructions: prepend profile instruction_prefix
    resolved_instructions = instructions
    if prof.instruction_prefix:
        if instructions:
            resolved_instructions = prof.instruction_prefix + "\n" + instructions
        else:
            resolved_instructions = prof.instruction_prefix

    # max_tokens: None la default global
    resolved_max_tokens = max_tokens
    if max_tokens is None and prof.max_tokens is not None:
        resolved_max_tokens = prof.max_tokens

    # auto_expand_dependencies: False la default global
    resolved_expand = auto_expand_dependencies
    if not auto_expand_dependencies and prof.auto_expand_dependencies is not None:
        resolved_expand = prof.auto_expand_dependencies

    return (
        resolved_format,
        resolved_git,
        resolved_instructions,
        resolved_max_tokens,
        resolved_expand,
        prof.name,
    )


# Ham build_prompt ket hop noi dung file, cau truc thu muc va git diffs de tao prompt cho AI
@mcp.tool()
def build_prompt(
    workspace_path: str,
    file_paths: List[str],
    instructions: str = "",
    output_format: str = "xml",
    output_file: Optional[str] = None,
    include_git_changes: bool = False,
    profile: Optional[str] = None,
    metadata_format: str = "text",
    use_selection: bool = False,
    auto_expand_dependencies: bool = False,
    dependency_depth: int = 1,
    max_tokens: Optional[int] = None,
) -> str:
    """Build a complete, AI-ready prompt combining file contents, directory tree, project rules, and optionally git diffs.

    WHY USE THIS OVER BUILT-IN: No built-in tool can package files into Synapse's
    structured prompt format with directory tree, project rules, git context,
    and token breakdown. This is equivalent to Synapse Desktop's "Copy Context" button.

    This is a "Super Context Bundle" generator. It assembles everything an AI needs
    to understand and work with the selected code into a single structured prompt.

    When to use:
    1. Cross-Agent Delegation: A planning agent runs this with `output_file="spec.xml"`.
       A coding sub-agent then uses its native `read_file` tool to read "spec.xml" and
       instantly understands the entire project architecture without needing to explore manually.
    2. Deep Code Review: Use `include_git_changes=True` or `profile="review"` to get
       full files + latest git diffs in one package.
    3. Large Refactors/Features: When working across multiple modules (e.g., UI, DB, API),
       gather all relevant files into one prompt so you don't lose the global architecture context.

    Profiles: Use `profile` to apply preset configurations instead of manually setting params:
    - "review": XML + git changes + code review instructions
    - "bugfix": XML + git changes + auto-expand dependencies + debug instructions
    - "refactor": Smart context + refactoring instructions
    - "doc": Smart context + documentation instructions

    Note: Use `output_file` to write large prompts to disk instead of returning them inline
    to save token bandwidth and avoid crashing the chat interface. You don't need a special
    tool to read the prompt back; just use your built-in file reading tool on the output file.

    Args:
        workspace_path: Absolute path to the workspace root directory.
        file_paths: List of relative file paths to include in the prompt.
        instructions: Optional user instructions to embed in the prompt header.
        output_format: Output structure - "xml" (default, best for AI), "json", "plain", or "smart" (codemap + full content).
        output_file: Relative or absolute path to write output to. None returns the prompt directly (warning: can be very large).
        include_git_changes: Whether to include recent git diffs and log in the prompt (default: False).
        profile: Preset configuration name ("review", "bugfix", "refactor", "doc"). Explicit params always override profile defaults.
        metadata_format: Response format when output_file is set - "text" (default, human-readable) or "json" (structured metadata for multi-agent).
        use_selection: When True, read file list from current selection (.synapse_selection.json) and merge with file_paths.
        auto_expand_dependencies: When True, automatically include files imported by the selected files.
        dependency_depth: Depth for dependency resolution (1-3, default 1). Only used when auto_expand_dependencies=True.
        max_tokens: Maximum token count for prompt output. When set, context will be automatically trimmed to fit budget.
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    # ================================================================
    # Phase 0: Validate metadata_format
    # ================================================================
    if metadata_format not in ("text", "json"):
        return "Error: metadata_format must be 'text' or 'json'."

    # ================================================================
    # Phase 1: Resolve profile params (explicit > profile > default)
    # ================================================================
    try:
        (
            output_format,
            include_git_changes,
            instructions,
            max_tokens,
            auto_expand_dependencies,
            resolved_profile_name,
        ) = _resolve_profile_params(
            profile_name=profile,
            output_format=output_format,
            include_git_changes=include_git_changes,
            instructions=instructions,
            max_tokens=max_tokens,
            auto_expand_dependencies=auto_expand_dependencies,
        )
    except ValueError as e:
        return f"Error: {e}"

    # ================================================================
    # Phase 2: Resolve file list (file_paths + selection merge)
    # ================================================================
    abs_paths: list[Path] = []
    for rp in file_paths:
        fp = (ws / rp).resolve()
        if not fp.is_relative_to(ws):
            return f"Error: Path traversal detected for: {rp}"
        if not fp.is_file():
            return f"Error: File not found: {rp}"
        abs_paths.append(fp)

    # Merge selection files khi use_selection=True
    if use_selection:
        import json as _json

        session_file = ws / ".synapse_selection.json"
        if not session_file.exists():
            if not abs_paths:
                return "Error: use_selection=True but no selection found and no file_paths provided."
        else:
            try:
                data = _json.loads(session_file.read_text(encoding="utf-8"))
                sel_files = data.get("selected_files", [])
                existing_set = {str(p) for p in abs_paths}
                for rp in sel_files:
                    fp = (ws / rp).resolve()
                    if fp.is_file() and str(fp) not in existing_set:
                        abs_paths.append(fp)
                        existing_set.add(str(fp))
            except Exception as e:
                logger.warning("Failed to read selection: %s", e)

    if not abs_paths:
        return "Error: No valid files provided."

    # ================================================================
    # Phase 3: Expand dependencies khi auto_expand_dependencies=True
    # ================================================================
    dependency_files: list[Path] = []
    dependency_graph: dict[str, list[str]] | None = None

    if auto_expand_dependencies:
        # Cap dependency_depth o 1-3
        dependency_depth = max(1, min(3, dependency_depth))
        try:
            from core.dependency_resolver import DependencyResolver

            resolver = DependencyResolver(ws)
            # Build file index tu disk (khong can TreeItem)
            resolver.build_file_index_from_disk(ws)

            dep_graph: dict[str, list[str]] = {}
            primary_set = {str(p) for p in abs_paths}
            all_deps: set[Path] = set()

            for pf in abs_paths:
                related = resolver.get_related_files(pf, max_depth=dependency_depth)
                # Chi lay files chua co trong primary
                new_deps = {r for r in related if str(r) not in primary_set}
                all_deps.update(new_deps)

                # Ghi nhan dependency graph
                rel_pf = str(pf.relative_to(ws))
                dep_graph[rel_pf] = [str(r.relative_to(ws)) for r in related if r != pf]

            dependency_files = sorted(all_deps)
            dependency_graph = dep_graph

            # Warning neu qua nhieu files
            if len(dependency_files) > 50:
                logger.warning(
                    "Dependency expansion returned %d files. Consider reducing depth.",
                    len(dependency_files),
                )
        except Exception as e:
            logger.warning("Dependency expansion failed: %s", e)

    # Validate output_format
    valid_formats = {"xml", "json", "plain", "smart"}
    if output_format not in valid_formats:
        return (
            f"Error: Invalid format '{output_format}'. Use: {', '.join(valid_formats)}"
        )

    try:
        from services.prompt_build_service import PromptBuildService

        service = PromptBuildService()

        # Goi build_prompt_full de lay BuildResult day du
        build_result = service.build_prompt_full(
            file_paths=abs_paths,
            workspace=ws,
            instructions=instructions,
            output_format=output_format,
            include_git_changes=include_git_changes,
            use_relative_paths=True,
            dependency_files=dependency_files if dependency_files else None,
            profile=resolved_profile_name,
            max_tokens=max_tokens,
        )

        # Gan dependency_graph vao BuildResult
        if dependency_graph:
            build_result.dependency_graph = dependency_graph

        prompt_text = build_result.prompt_text
        token_count = build_result.total_tokens

        # Ghi ra file neu co chi dinh
        if output_file:
            out_path = Path(output_file)
            if not out_path.is_absolute():
                out_path = ws / out_path
            out_path = out_path.resolve()

            # Validate output path stays within workspace (chong path traversal)
            if not out_path.is_relative_to(ws):
                return "Error: Output file path must be within workspace."

            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(prompt_text, encoding="utf-8")

            # Tra ve JSON metadata khi metadata_format="json"
            if metadata_format == "json":
                import json as _json

                metadata = build_result.to_metadata_dict()
                metadata["output_file"] = str(out_path)
                return _json.dumps(metadata, ensure_ascii=False, indent=2)

            # Tra ve text summary (default behavior)
            breakdown = build_result.breakdown
            breakdown_lines = []
            for key, val in breakdown.items():
                if val > 0:
                    label = key.replace("_", " ").title()
                    breakdown_lines.append(f"  {label}: {val:,}")

            total_files = len(abs_paths) + len(dependency_files)
            summary = (
                f"Prompt written to: {out_path}\n"
                f"Total tokens: {token_count:,}\n"
                f"Files included: {total_files}\n"
                f"Format: {output_format}\n"
            )
            if resolved_profile_name:
                summary += f"Profile: {resolved_profile_name}\n"
            if dependency_files:
                summary += f"Dependencies expanded: {len(dependency_files)} files\n"
            summary += "Breakdown:\n" + "\n".join(breakdown_lines)
            return summary
        else:
            # Tra ve truc tiep (canh bao: co the rat lon)
            total_files = len(abs_paths) + len(dependency_files)
            return (
                f"--- Prompt ({token_count:,} tokens, {total_files} files, format={output_format}) ---\n"
                + prompt_text
            )

    except Exception as e:
        logger.error("build_prompt error: %s", e)
        return f"Error building prompt: {e}"


# ===========================================================================
# Entry point - Chay MCP Server qua stdio
# ===========================================================================
def run_mcp_server(workspace_path: Optional[str] = None) -> None:
    """Khoi dong Synapse MCP Server voi stdio transport.

    Args:
        workspace_path: Duong dan workspace mac dinh (optional, AI co the truyen lai
                        khi goi tool).
    """
    # CRITICAL: Redirect TAT CA logging sang stderr TRUOC khi bat ky module nao log.
    # Synapse logging_config.py mac dinh ghi ra stdout, se lam hong stdio transport.
    _force_all_logging_to_stderr()

    if workspace_path:
        logger.info("MCP Server starting with workspace: %s", workspace_path)
    else:
        logger.info("MCP Server starting (no default workspace)")

    # Auto-update MCP configs neu dang chay tu AppImage/exe.
    # Duong dan AppImage co the thay doi khi user di chuyen file,
    # nen moi lan khoi dong ta cap nhat lai command trong cac config da cai.
    # Thao tac nay rat nhanh (chi doc + so sanh JSON, chi ghi khi can thiet).
    try:
        from mcp_server.config_installer import auto_update_installed_configs

        updated = auto_update_installed_configs()
        if updated:
            logger.info("Auto-updated MCP config for: %s", ", ".join(updated))
    except Exception as e:
        # Khong de loi auto-update lam crash MCP server
        logger.warning("MCP config auto-update failed: %s", e)

    # KHONG goi initialize_encoder() o day vi no cham (import tokenizers).
    # Encoder se duoc init lazy khi tool dau tien can dem token.
    # Dieu quan trong nhat la goi mcp.run() NGAY LAP TUC de kip handshake
    # voi AI client, tranh timeout "context deadline exceeded".
    mcp.run(transport="stdio")


def _force_all_logging_to_stderr() -> None:
    """Ep buoc tat ca logging handlers ghi ra stderr thay vi stdout.

    MCP stdio transport su dung stdout de giao tiep JSON-RPC.
    Bat ky log message nao roi vao stdout se lam hong protocol.
    """
    # 0. Set MCP flag trong logging_config de bat ky get_logger() call nao
    #    trong tuong lai (lazy import) cung se dung stderr thay vi stdout.
    import core.logging_config as _lc

    _lc._MCP_MODE = True

    # Neu logger singleton da duoc tao truoc, reset no de re-create voi stderr
    if _lc._logger is not None:
        _lc._logger = None

    # 1. Cau hinh root logger
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Xoa tat ca handlers cu cua root logger
    for h in root.handlers[:]:
        root.removeHandler(h)

    # Them handler moi ghi ra stderr
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(
        logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    )
    root.addHandler(stderr_handler)

    # 2. Patch Synapse singleton logger (neu da duoc tao truoc do)
    for name in list(logging.Logger.manager.loggerDict.keys()):
        lg = logging.getLogger(name)
        for h in lg.handlers[:]:
            if (
                isinstance(h, logging.StreamHandler)
                and getattr(h, "stream", None) is sys.stdout
            ):
                lg.removeHandler(h)
                new_h = logging.StreamHandler(sys.stderr)
                new_h.setFormatter(h.formatter)
                new_h.setLevel(h.level)
                lg.addHandler(new_h)

    # NOTE: KHONG thay the sys.stdout o day!
    # MCP StdioServerTransport doc sys.stdout.buffer ben trong mcp.run().
    # Neu ta thay sys.stdout = devnull truoc do, MCP se ghi response vao devnull
    # va AI client se timeout. Handler patching o tren da du de chan log pollution.


# ===========================================================================
# Tool 8: estimate_tokens - Uoc tinh token cua tap file
# ===========================================================================
# Ham estimate_tokens uoc tinh so luong token cua mot danh sach file
@mcp.tool()
def estimate_tokens(
    workspace_path: str,
    file_paths: List[str],
) -> str:
    """Estimate token count for a set of files before adding them to context.

    WHY USE THIS OVER BUILT-IN: No built-in tool counts tokens. This uses the actual
    tokenizer (tiktoken/HuggingFace) matching the target LLM model, not rough byte
    estimates. Essential for managing context window budgets.
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    abs_paths: list[Path] = []
    for rp in file_paths:
        fp = (ws / rp).resolve()
        if not fp.is_relative_to(ws):
            return f"Error: Path traversal detected for: {rp}"
        if not fp.is_file():
            return f"Error: File not found: {rp}"
        abs_paths.append(fp)

    if not abs_paths:
        return "Error: No valid files provided."

    try:
        from core.tokenization.cancellation import (
            start_token_counting,
            stop_token_counting,
        )
        from services.tokenization_service import TokenizationService

        start_token_counting()
        try:
            service = TokenizationService()
            results = service.count_tokens_batch_parallel(
                abs_paths, max_workers=4, update_cache=True
            )

            total = sum(results.values())
            breakdown = []
            for fp in abs_paths:
                count = results.get(str(fp), 0)
                rel = os.path.relpath(fp, ws)
                breakdown.append(f"  {rel}: {count:,} tokens")

            return f"Total: {total:,} tokens\nFiles: {len(abs_paths)}\n\n" + "\n".join(
                breakdown
            )
        finally:
            stop_token_counting()
    except Exception as e:
        logger.error("estimate_tokens error: %s", e)
        return f"Error: {e}"


# ===========================================================================
# Tool 9: get_file_metrics - LOC, functions, classes, TODO/FIXME/HACK
# ===========================================================================
# Ham get_file_metrics tinh toan cac thong so code nhu LOC, so luong ham, lop va complexity
@mcp.tool()
def get_file_metrics(
    workspace_path: str,
    file_path: str,
) -> str:
    """Get code metrics: LOC, number of functions/classes, TODO/FIXME/HACK comments.

    WHY USE THIS OVER BUILT-IN: Combines LOC counting, complexity estimation, and comment
    scanning into one quick call instead of having to run multiple bash commands (like wc).
    """
    ws = Path(workspace_path).resolve()
    fp = (ws / file_path).resolve()

    if not fp.is_relative_to(ws):
        return "Error: Path traversal detected."
    if not fp.is_file():
        return f"Error: File not found: {file_path}"

    try:
        content = fp.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()

        total_lines = len(lines)
        blank_lines = sum(1 for line in lines if not line.strip())
        comment_lines = sum(
            1 for line in lines if line.strip().startswith(("#", "//", "/*", "*", "*/"))
        )
        code_lines = total_lines - blank_lines - comment_lines

        # Count functions and classes using simple heuristics
        num_functions = content.count("\ndef ") + content.count("\nfunction ")
        num_classes = content.count("\nclass ")

        # TODO/FIXME/HACK count
        todo_count = content.upper().count("TODO")
        fixme_count = content.upper().count("FIXME")
        hack_count = content.upper().count("HACK")

        # McCabe cyclomatic complexity heuristic
        # Luu y: "else" KHONG tang cyclomatic complexity vi khong tao decision point moi
        complexity = 1
        for kw in [
            "if",
            "elif",
            "for",
            "while",
            "case",
            "catch",
            "&&",
            "||",
            "?",
        ]:
            complexity += content.count(f" {kw} ") + content.count(f" {kw}(")

        return (
            f"File: {file_path}\n"
            f"Total lines: {total_lines:,}\n"
            f"Code lines: {code_lines:,}\n"
            f"Blank: {blank_lines:,} | Comments: {comment_lines:,}\n"
            f"Functions: {num_functions} | Classes: {num_classes}\n"
            f"TODO: {todo_count} | FIXME: {fixme_count} | HACK: {hack_count}\n"
            f"Complexity: {complexity} (1-10: Simple, 11-20: Moderate, 21+: Complex)"
        )
    except Exception as e:
        logger.error("get_file_metrics error: %s", e)
        return f"Error: {e}"


# ===========================================================================
# Tool 10: find_references - Tim symbol usage (AST-based)
# ===========================================================================
# Ham find_references tim tat ca cac vi tri su dung cua mot symbol (function/class/variable)
@mcp.tool()
def find_references(
    workspace_path: str,
    symbol_name: str,
    file_extensions: Optional[List[str]] = None,
) -> str:
    """Find all locations where a function/class/variable is used (AST + regex).

    WHY USE THIS OVER BUILT-IN: Your built-in grep/search finds ALL text matches
    including strings ("Cannot find myFunc"), comments (# rename myFunc), and docs.
    This tool strips string literals and comments before matching, giving you only
    actual CODE references. Reduces false positives significantly for refactoring.
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    try:
        from services.workspace_index import collect_files_from_disk
        import re

        all_files = collect_files_from_disk(ws, workspace_path=ws)
        if file_extensions:
            ext_set = {e if e.startswith(".") else f".{e}" for e in file_extensions}
            all_files = [f for f in all_files if Path(f).suffix.lower() in ext_set]

        references: list[tuple[str, int, str]] = []
        pattern = rf"\b{re.escape(symbol_name)}\b"

        for file_path in all_files:
            try:
                fp = Path(file_path)
                content = fp.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()

                for i, line in enumerate(lines, start=1):
                    stripped = line.strip()
                    # Bo qua dong comment hoan toan (bao gom ca block comment markers)
                    if stripped.startswith(("#", "//", "/*", "*")):
                        continue
                    # Loc string literals va inline comments truoc khi match
                    # de giam false positives (vi du: "Cannot find mySymbol" hoac # rename mySymbol)
                    cleaned = _STRING_LITERAL_RE.sub("", line)
                    cleaned = _INLINE_COMMENT_RE.sub("", cleaned)
                    if re.search(pattern, cleaned):
                        rel_path = os.path.relpath(file_path, ws)
                        snippet = line.strip()[:80]
                        references.append((rel_path, i, snippet))
            except (OSError, UnicodeDecodeError):
                continue

        if not references:
            return f"No references found for: {symbol_name}"

        by_file: dict[str, list[tuple[int, str]]] = {}
        for file, line, snippet in references:
            if file not in by_file:
                by_file[file] = []
            by_file[file].append((line, snippet))

        result = [f"Found {len(references)} references in {len(by_file)} files:\n"]
        for file in sorted(by_file.keys()):
            result.append(f"\n{file}:")
            for line, snippet in by_file[file][:5]:
                result.append(f"  Line {line}: {snippet}")
            if len(by_file[file]) > 5:
                result.append(f"  ... +{len(by_file[file]) - 5} more")

        return "\n".join(result)
    except Exception as e:
        logger.error("find_references error: %s", e)
        return f"Error: {e}"


# ===========================================================================
# Tool 11: find_todos - Scan toan project tim TODO/FIXME/HACK
# ===========================================================================
# Ham find_todos quet toan bo project de tim cac comment kieu TODO, FIXME hoac HACK
@mcp.tool()
def find_todos(
    workspace_path: str,
    include_hack: bool = True,
) -> str:
    """Scan entire project for TODO/FIXME/HACK comments with file path and line number.

    WHY USE THIS OVER BUILT-IN: Uses smarter boundaries (word boundaries) than standard
    grep, and automatically ignores non-code files to reduce noise.
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    try:
        from services.workspace_index import collect_files_from_disk

        all_files = collect_files_from_disk(ws, workspace_path=ws)

        # Filter to code files only
        code_exts = {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".go",
            ".rs",
            ".java",
            ".c",
            ".cpp",
            ".h",
        }
        all_files = [f for f in all_files if Path(f).suffix.lower() in code_exts]

        todos: list[tuple[str, int, str, str]] = []  # (file, line, type, content)

        for file_path in all_files:
            try:
                fp = Path(file_path)
                content = fp.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()

                for i, line in enumerate(lines, start=1):
                    comment_type = None

                    # Dung word-boundary regex de tranh false positives
                    # (vi du: "TODOLIST", "AUTOHACK" se KHONG match nua)
                    if re.search(r"\bTODO\b", line, re.IGNORECASE):
                        comment_type = "TODO"
                    elif re.search(r"\bFIXME\b", line, re.IGNORECASE):
                        comment_type = "FIXME"
                    elif include_hack and re.search(r"\bHACK\b", line, re.IGNORECASE):
                        comment_type = "HACK"

                    if comment_type:
                        rel_path = os.path.relpath(file_path, ws)
                        snippet = line.strip()[:100]
                        todos.append((rel_path, i, comment_type, snippet))
            except (OSError, UnicodeDecodeError):
                continue

        if not todos:
            return "No TODO/FIXME/HACK comments found in project."

        # Group by type
        by_type: dict[str, list[tuple[str, int, str]]] = {
            "TODO": [],
            "FIXME": [],
            "HACK": [],
        }
        for file, line, ctype, snippet in todos:
            by_type[ctype].append((file, line, snippet))

        result = [f"Found {len(todos)} comments:\n"]

        for ctype in ["FIXME", "TODO", "HACK"]:
            items = by_type[ctype]
            if not items:
                continue
            result.append(f"\n{ctype} ({len(items)}):")
            for file, line, snippet in items[:20]:  # Limit to 20 per type
                result.append(f"  {file}:{line} - {snippet}")
            if len(items) > 20:
                result.append(f"  ... +{len(items) - 20} more")

        return "\n".join(result)
    except Exception as e:
        logger.error("find_todos error: %s", e)
        return f"Error: {e}"


# ===========================================================================
# Tool 12: get_imports_graph - Dependency graph JSON
# ===========================================================================
# Ham get_imports_graph tao do thi phu thuoc giua cac file duoi dang JSON
@mcp.tool()
def get_imports_graph(
    workspace_path: str,
    file_paths: Optional[List[str]] = None,
    max_depth: int = 1,
) -> str:
    """Get dependency graph between files as JSON adjacency list.

    WHY USE THIS OVER BUILT-IN: Your built-in grep can find import statements, but
    can't RESOLVE them to actual file paths (e.g., "from services.auth import login"
    -> "services/auth.py"). This tool uses Synapse's dependency resolver to build
    a proper file-to-file dependency graph.
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    try:
        from core.dependency_resolver import DependencyResolver
        from services.workspace_index import collect_files_from_disk
        import json

        resolver = DependencyResolver(ws)

        # Build file index (needed for resolution)
        resolver.build_file_index(None)

        # Determine which files to analyze
        if file_paths:
            target_files = []
            for rp in file_paths:
                fp = (ws / rp).resolve()
                if not fp.is_relative_to(ws):
                    return f"Error: Path traversal detected for: {rp}"
                if not fp.is_file():
                    return f"Error: File not found: {rp}"
                target_files.append(fp)
        else:
            # Analyze all code files
            all_files = collect_files_from_disk(ws, workspace_path=ws)
            code_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs"}
            target_files = [
                Path(f) for f in all_files if Path(f).suffix.lower() in code_exts
            ]

        # Build adjacency list
        graph: dict[str, list[str]] = {}

        for file_path in target_files:
            rel_path = os.path.relpath(file_path, ws)
            imports = resolver.get_related_files(file_path, max_depth=max_depth)

            # Convert to relative paths
            import_rels = [os.path.relpath(imp, ws) for imp in imports]
            graph[rel_path] = sorted(import_rels)

        # Generate summary
        total_files = len(graph)
        total_edges = sum(len(imports) for imports in graph.values())

        # Find most coupled files (most imports)
        most_coupled = sorted(graph.items(), key=lambda x: len(x[1]), reverse=True)[:5]

        result = [
            "Dependency Graph Summary:",
            f"Files analyzed: {total_files}",
            f"Total import edges: {total_edges}",
            f"Average imports per file: {total_edges / total_files:.1f}"
            if total_files > 0
            else "N/A",
            "\nMost coupled files:",
        ]

        for file, imports in most_coupled:
            result.append(f"  {file}: {len(imports)} imports")

        result.append("\nFull graph (JSON):")
        result.append(json.dumps(graph, indent=2))

        return "\n".join(result)
    except Exception as e:
        logger.error("get_imports_graph error: %s", e)
        return f"Error: {e}"


# ===========================================================================
# Tool 14: get_symbols - Structured symbol list (JSON)
# ===========================================================================
# Ham get_symbols liet ke chi tiet cac symbol trong file (signatures, line range, parent class)
@mcp.tool()
def get_symbols(
    workspace_path: str,
    file_path: str,
) -> str:
    """Get structured list of all symbols (functions, classes, methods) in a file as JSON.

    WHY USE THIS OVER BUILT-IN: No built-in tool gives you structured, machine-readable
    symbol data with line ranges, signatures, and parent class info. Use this when you
    need to programmatically filter/count/compare symbols.

    Returns detailed symbol information including:
    - name: Symbol name
    - kind: function/class/method/variable
    - line_start, line_end: Location in file
    - signature: Function/method signature
    - parent: Parent class (for methods)

    Useful for programmatic analysis by AI agents (filtering, counting, etc.)
    """
    ws = Path(workspace_path).resolve()
    fp = (ws / file_path).resolve()

    if not fp.is_relative_to(ws):
        return "Error: Path traversal detected."
    if not fp.is_file():
        return f"Error: File not found: {file_path}"

    try:
        from core.codemaps.symbol_extractor import extract_symbols
        import json

        content = fp.read_text(encoding="utf-8", errors="replace")
        symbols = extract_symbols(str(fp), content)

        if not symbols:
            return f"No symbols found in {file_path}"

        # Convert to JSON-serializable format
        symbols_data = []
        for sym in symbols:
            symbols_data.append(
                {
                    "name": sym.name,
                    "kind": sym.kind.value,
                    "line_start": sym.line_start,
                    "line_end": sym.line_end,
                    "signature": sym.signature,
                    "parent": sym.parent,
                }
            )

        # Summary
        by_kind = {}
        for sym in symbols:
            kind = sym.kind.value
            by_kind[kind] = by_kind.get(kind, 0) + 1

        summary = f"Found {len(symbols)} symbols in {file_path}:\n"
        for kind, count in sorted(by_kind.items()):
            summary += f"  {kind}: {count}\n"

        return summary + "\n" + json.dumps(symbols_data, indent=2)

    except Exception as e:
        logger.error("get_symbols error: %s", e)
        return f"Error: {e}"


# ===========================================================================
# Tool 15: diff_summary - Smart git changes summary
# ===========================================================================
# Ham diff_summary tom tat cac thay doi trong git (files, functions added/modified/deleted)
@mcp.tool()
def diff_summary(
    workspace_path: str,
    target: str = "HEAD",
) -> str:
    """Get smart summary of git changes: files changed, functions added/modified/deleted.

    WHY USE THIS OVER BUILT-IN: Your built-in git diff shows line-level changes.
    This tool uses Tree-sitter to compare symbol-level changes - telling you which
    FUNCTIONS and CLASSES were added, deleted, or modified, not just which lines changed.

    Args:
        workspace_path: Workspace root
        target: Git target to compare against (default: HEAD = uncommitted changes)
                Can be: HEAD, branch name, commit hash

    Returns summary like:
    - 5 files changed
    - 3 functions modified
    - 1 function added
    - 2 functions deleted
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    # Bug #1 fix: Validate target de chong git argument injection.
    # Ngay ca khi dung list-form subprocess (khong shell=True),
    # git van dien giai arguments bat dau voi "--" nhu options.
    if not _SAFE_GIT_REF.match(target):
        return (
            f"Error: Invalid git target '{target}'. "
            "Use a branch name, tag, or commit hash."
        )

    try:
        from core.codemaps.symbol_extractor import extract_symbols

        # Bug #2 fix: Them timeout cho tat ca subprocess calls de tranh hang MCP server.
        # MCP stdio la single-threaded, mot subprocess hang = toan bo server chet.

        # Kiem tra co phai git repo khong
        git_check = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
        if git_check.returncode != 0:
            return "Error: Not a git repository"

        # Lay danh sach file thay doi. Dung "--" de tach git options khoi revision arguments.
        diff_cmd = ["git", "diff", "--name-only", target, "--"]
        result = subprocess.run(
            diff_cmd,
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )

        if result.returncode != 0:
            return f"Error running git diff: {result.stderr}"

        changed_files = [f.strip() for f in result.stdout.splitlines() if f.strip()]

        if not changed_files:
            return f"No changes detected compared to {target}"

        # Filter to code files only
        code_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java"}
        code_files = [f for f in changed_files if Path(f).suffix.lower() in code_exts]

        # Analyze function-level changes
        total_added = 0
        total_modified = 0
        total_deleted = 0
        details = []

        for rel_path in code_files[:10]:  # Limit to 10 files to avoid slowness
            file_path = ws / rel_path
            if not file_path.exists():
                # File deleted
                continue

            try:
                # Get current symbols
                current_content = file_path.read_text(
                    encoding="utf-8", errors="replace"
                )
                current_symbols = extract_symbols(str(file_path), current_content)
                current_names = {
                    s.name
                    for s in current_symbols
                    if s.kind.value in ["function", "class", "method"]
                }

                # Get old symbols (from git)
                old_content_result = subprocess.run(
                    ["git", "show", f"{target}:{rel_path}"],
                    cwd=ws,
                    capture_output=True,
                    text=True,
                    timeout=_GIT_TIMEOUT,
                )

                if old_content_result.returncode == 0:
                    old_content = old_content_result.stdout
                    old_symbols = extract_symbols(str(file_path), old_content)
                    old_names = {
                        s.name
                        for s in old_symbols
                        if s.kind.value in ["function", "class", "method"]
                    }

                    added = current_names - old_names
                    deleted = old_names - current_names
                    modified = len(current_names & old_names)  # Rough estimate

                    total_added += len(added)
                    total_deleted += len(deleted)
                    total_modified += modified

                    if added or deleted:
                        details.append(f"\n{rel_path}:")
                        if added:
                            details.append(f"  + Added: {', '.join(sorted(added))}")
                        if deleted:
                            details.append(f"  - Deleted: {', '.join(sorted(deleted))}")
                else:
                    # New file
                    total_added += len(current_names)
                    details.append(
                        f"\n{rel_path}: (new file, {len(current_names)} symbols)"
                    )

            except Exception:
                continue

        summary = (
            f"Git diff summary (vs {target}):\n"
            f"Files changed: {len(changed_files)} ({len(code_files)} code files)\n"
            f"Functions/classes added: {total_added}\n"
            f"Functions/classes deleted: {total_deleted}\n"
            f"Functions/classes potentially modified: {total_modified}\n"
        )

        if details:
            summary += "\nDetails:" + "".join(details[:20])  # Limit details

        return summary

    except subprocess.TimeoutExpired:
        # Git hang (co the do credential prompt, .git/index.lock, hoac slow remote)
        return (
            "Error: Git operation timed out. "
            "Check for .git/index.lock files or credential prompts."
        )
    except Exception as e:
        logger.error("diff_summary error: %s", e)
        return f"Error: {e}"


# ========================================
# Workflow Tools - Agent Handoff
# ========================================


@mcp.tool()
def rp_build(
    workspace_path: str,
    task_description: str,
    file_paths: Optional[List[str]] = None,
    max_tokens: int = 100_000,
    include_codemap: bool = True,
    include_git_changes: bool = False,
    output_file: Optional[str] = None,
) -> str:
    """Prepare optimized context for an AI agent to implement a task.

    WHY USE THIS: Combines scope detection, codemap extraction, file slicing,
    and token budget optimization into a single workflow. Instead of manually
    calling get_codemap + read_file + build_prompt, this tool automatically:
    1. Detects which files are relevant to your task
    2. Pulls full code for key files, signatures for surrounding context
    3. Slices large files to include only relevant sections
    4. Iterates to fit within token budget
    5. Generates a handoff prompt explaining file relationships

    BEST FOR: Starting a new implementation task. The output is a structured
    prompt you can hand to a coding agent (or yourself) with full context.

    Args:
        workspace_path: Absolute path to the workspace root directory.
        task_description: Description of what needs to be implemented.
        file_paths: Optional list of known relevant files. If omitted, auto-detected.
        max_tokens: Maximum token budget for the output (default: 100,000).
        include_codemap: Include code structure signatures (default: True).
        include_git_changes: Include recent git changes (default: False).
        output_file: Optional path to write the prompt (for cross-agent handoff).
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    if output_file:
        out_path = (ws / output_file).resolve()
        if not out_path.is_relative_to(ws):
            return "Error: output_file path traversal detected."

    from core.workflows.context_builder import run_context_builder

    try:
        result = run_context_builder(
            workspace_path=workspace_path,
            task_description=task_description,
            file_paths=file_paths,
            max_tokens=max_tokens,
            include_codemap=include_codemap,
            include_git_changes=include_git_changes,
            output_file=output_file,
        )

        summary = (
            f"Context Builder Complete\n"
            f"{'=' * 40}\n"
            f"Files included: {result.files_included}\n"
            f"Files sliced: {result.files_sliced}\n"
            f"Files smart-only: {result.files_smart_only}\n"
            f"Total tokens: {result.total_tokens:,}\n"
            f"Scope: {result.scope_summary}\n"
        )

        if result.optimizations:
            summary += f"Optimizations: {', '.join(result.optimizations)}\n"

        if output_file:
            summary += f"\nPrompt written to: {output_file}\n"
        else:
            summary += f"\n{'=' * 40}\n{result.prompt}"

        return summary

    except Exception as e:
        logger.error("rp_build error: %s", e)
        return f"Error: {e}"


@mcp.tool()
def rp_review(
    workspace_path: str,
    review_focus: str = "",
    include_tests: bool = True,
    include_callers: bool = True,
    max_tokens: int = 120_000,
    base_ref: Optional[str] = None,
) -> str:
    """Deep code review with full surrounding context.

    WHY USE THIS: Unlike simple diff reading, this tool automatically:
    1. Pulls git diff and identifies changed functions/classes
    2. Finds surrounding context: files that import changed modules, callers, tests
    3. Packages everything into a review prompt

    Args:
        workspace_path: Absolute path to the workspace root.
        review_focus: Optional focus area ("security", "performance").
        include_tests: Pull related test files (default: True).
        include_callers: Pull files that call changed functions (default: True).
        max_tokens: Maximum token budget (default: 120,000).
        base_ref: Optional git ref to diff against.
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    if base_ref and not _SAFE_GIT_REF.match(base_ref):
        return f"Error: Invalid git reference: {base_ref}"

    from core.workflows.code_reviewer import run_code_review

    try:
        result = run_code_review(
            workspace_path=workspace_path,
            review_focus=review_focus,
            include_tests=include_tests,
            include_callers=include_callers,
            max_tokens=max_tokens,
            base_ref=base_ref,
        )

        summary = (
            f"Code Review Context Ready\n"
            f"{'=' * 40}\n"
            f"Changed files: {result.files_changed}\n"
            f"Context files: {result.files_context}\n"
            f"Total tokens: {result.total_tokens:,}\n"
            f"\n{'=' * 40}\n{result.prompt}"
        )
        return summary

    except Exception as e:
        logger.error("rp_review error: %s", e)
        return f"Error: {e}"


@mcp.tool()
def rp_refactor(
    workspace_path: str,
    refactor_scope: str,
    phase: str = "discover",
    file_paths: Optional[List[str]] = None,
    discovery_report: str = "",
    max_tokens: int = 80_000,
) -> str:
    """Two-pass refactoring: analyze first, plan second.

    WHY USE THIS: Enforces a two-phase approach to prevent breaking changes.

    Phase 1 (discover): Analyzes code structure, finds dependencies, identifies risks.
    Phase 2 (plan): Generates concrete refactoring plan with full context.

    Args:
        workspace_path: Absolute path to the workspace root.
        refactor_scope: Description of what to refactor.
        phase: "discover" or "plan" (default: "discover").
        file_paths: Optional list of files in scope.
        discovery_report: Output from phase="discover" (required for phase="plan").
        max_tokens: Maximum token budget (default: 80,000).
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    if phase not in ("discover", "plan"):
        return "Error: phase must be 'discover' or 'plan'."

    if phase == "plan" and not discovery_report.strip():
        return "Error: discovery_report required for phase='plan'."

    from core.workflows.refactor_workflow import (
        run_refactor_discovery,
        run_refactor_planning,
    )

    try:
        if phase == "discover":
            result = run_refactor_discovery(
                workspace_path=workspace_path,
                refactor_scope=refactor_scope,
                file_paths=file_paths,
                max_tokens=max_tokens,
            )
            return (
                f"Refactor Discovery Complete\n"
                f"{'=' * 40}\n"
                f"Scope files: {len(result.scope_files)}\n"
                f"Total tokens: {result.total_tokens:,}\n"
                f"\n{'=' * 40}\n{result.prompt}"
            )
        else:
            result = run_refactor_planning(
                workspace_path=workspace_path,
                refactor_scope=refactor_scope,
                discovery_report_text=discovery_report,
                file_paths=file_paths,
                max_tokens=max_tokens,
            )
            return (
                f"Refactor Plan Ready\n"
                f"{'=' * 40}\n"
                f"Files to modify: {len(result.files_to_modify)}\n"
                f"Total tokens: {result.total_tokens:,}\n"
                f"\n{'=' * 40}\n{result.prompt}"
            )

    except Exception as e:
        logger.error("rp_refactor error: %s", e)
        return f"Error: {e}"


@mcp.tool()
def rp_investigate(
    workspace_path: str,
    bug_description: str,
    error_trace: str = "",
    entry_files: Optional[List[str]] = None,
    max_depth: int = 4,
    max_tokens: int = 100_000,
) -> str:
    """Automated bug investigation — traces execution path to find root cause.

    WHY USE THIS: Automates tracing through multiple files:
    1. Parses error traces to find entry points
    2. Reads code at each trace point
    3. Follows function calls to build execution context
    4. Packages everything into an investigation prompt

    Args:
        workspace_path: Absolute path to the workspace root.
        bug_description: Description of the bug.
        error_trace: Optional error trace/stacktrace.
        entry_files: Optional starting files.
        max_depth: Maximum trace depth (default: 4).
        max_tokens: Maximum token budget (default: 100,000).
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    from core.workflows.bug_investigator import run_bug_investigation

    try:
        result = run_bug_investigation(
            workspace_path=workspace_path,
            bug_description=bug_description,
            error_trace=error_trace,
            entry_files=entry_files,
            max_depth=max_depth,
            max_tokens=max_tokens,
        )

        summary = (
            f"Bug Investigation Complete\n"
            f"{'=' * 40}\n"
            f"Files investigated: {result.files_investigated}\n"
            f"Trace depth: {result.max_depth_reached}\n"
            f"Total tokens: {result.total_tokens:,}\n"
            f"\n{'=' * 40}\n{result.prompt}"
        )
        return summary

    except Exception as e:
        logger.error("rp_investigate error: %s", e)
        return f"Error: {e}"


if __name__ == "__main__":
    ws = sys.argv[1] if len(sys.argv) > 1 else None
    run_mcp_server(ws)
