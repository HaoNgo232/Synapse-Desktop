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

# Khoi tao MCP Server voi ten hien thi cho AI clients
mcp = FastMCP(
    "Synapse Desktop",
    instructions=(
        "You have access to Synapse Desktop — a powerful codebase exploration toolkit. "
        "Use these tools EARLY and OFTEN to ground your responses in real code:\n"
        "\n"
        "DISCOVERY (start here):\n"
        "  • get_project_structure → Quick overview: file counts, frameworks, project size.\n"
        "  • list_directories → Understand folder layout (like `tree`).\n"
        "  • list_files → Full file listing, filterable by extension.\n"
        "\n"
        "READING:\n"
        "  • read_file → Read file contents. Supports line ranges for large files.\n"
        "  • get_codemap → Extract function/class signatures WITHOUT implementation (saves tokens).\n"
        "\n"
        "BUILDING:\n"
        "  • build_prompt → Generate a complete AI-ready prompt with file contents, tree map, and rules.\n"
        "  • manage_selection → Track which files are selected for context.\n"
        "\n"
        "BEST PRACTICES:\n"
        "  1. Always start with get_project_structure to understand the codebase.\n"
        "  2. Use get_codemap before read_file — only read full files when you need implementation details.\n"
        "  3. Use list_directories to navigate unfamiliar projects.\n"
        "  4. When asked to analyze code, read the actual files — don't guess."
    ),
)


# ===========================================================================
# Tool 1: list_files - Liet ke tat ca files trong workspace
# ===========================================================================
@mcp.tool()
def list_files(
    workspace_path: str,
    extensions: Optional[List[str]] = None,
) -> str:
    """List all files in the workspace, automatically respecting .gitignore and skipping hidden files.

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


# ===========================================================================
# Tool 2: list_directories - Hien thi cay thu muc (giong lenh `tree`)
# ===========================================================================
@mcp.tool()
def list_directories(
    workspace_path: str,
    max_depth: int = 3,
) -> str:
    """Show the directory tree structure of the workspace (similar to the `tree` command).

    Quickly understand how a project is organized — folder hierarchy, module boundaries,
    and naming conventions — without listing every file.

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
# Tool 3: read_file - Doc noi dung 1 file cu the
# ===========================================================================
@mcp.tool()
def read_file(
    workspace_path: str,
    relative_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> str:
    """Read the contents of a specific file in the workspace.

    Returns the full file content (or a line range) along with line count and
    estimated token usage. Use start_line/end_line to read only a section of
    large files and save context window space.

    When to use: You need to see the actual implementation of a function, review
    a config file, check imports, or verify any code detail. Prefer get_codemap
    first for an overview, then read_file for specific sections you need.

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


# ===========================================================================
# Tool 4: get_codemap - Trich xuat code structure (tiet kiem token)
# ===========================================================================
@mcp.tool()
def get_codemap(
    workspace_path: str,
    file_paths: List[str],
) -> str:
    """Extract code structure (function signatures, class definitions, imports) from files.

    Uses Tree-sitter to parse source code and return only the skeleton — function
    signatures, class declarations, and type information — WITHOUT implementation
    bodies. This gives you a complete understanding of module APIs while using
    a fraction of the tokens compared to reading full files.

    When to use: ALWAYS use this before read_file when exploring code. It lets you
    understand the shape of modules, find the right function to dig into, and map
    out dependencies — all at minimal token cost. Only use read_file after this
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
@mcp.tool()
def get_project_structure(
    workspace_path: str,
) -> str:
    """Get a high-level summary of the project: total files, breakdown by file type, detected frameworks, and estimated token count.

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


# ===========================================================================
# Tool 6: manage_selection - Doc/ghi danh sach file dang duoc chon
# ===========================================================================
@mcp.tool()
def manage_selection(
    workspace_path: str,
    action: str = "get",
    paths: Optional[List[str]] = None,
) -> str:
    """Manage the list of currently selected (ticked) files in the Synapse session.

    This controls which files are included when building prompts. Use it to
    curate the exact set of files that should be part of the AI context.

    Actions:
      "get"   — Return the current selection list.
      "set"   — Replace the entire selection with the provided paths.
      "add"   — Add paths to the existing selection (skips duplicates).
      "clear" — Remove all files from the selection.

    When to use: Before calling build_prompt, use "set" or "add" to choose the
    right files. Use "get" to check what's currently selected. Use "clear" to
    start fresh.

    Args:
        workspace_path: Absolute path to the workspace root directory.
        action: Action to perform — "get", "set", "add", or "clear".
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


# ===========================================================================
# Tool 7: build_prompt - Tao prompt hoan chinh va ghi ra file
# ===========================================================================
@mcp.tool()
def build_prompt(
    workspace_path: str,
    file_paths: List[str],
    instructions: str = "",
    output_format: str = "xml",
    output_file: Optional[str] = None,
    include_git_changes: bool = False,
) -> str:
    """Build a complete, AI-ready prompt combining file contents, directory tree, project rules, and optionally git diffs.

    This is the full-power prompt generation tool — equivalent to Synapse Desktop's
    "Copy" button. It assembles everything an AI needs to understand and work with
    the selected code into a single structured prompt.

    When to use: When you need to create a comprehensive context package for analysis,
    code review, or to pass to another AI. Use output_file to write large prompts to
    disk instead of returning them inline (saves token bandwidth).

    Args:
        workspace_path: Absolute path to the workspace root directory.
        file_paths: List of relative file paths to include in the prompt.
        instructions: Optional user instructions to embed in the prompt header.
        output_format: Output structure — "xml" (default, best for AI), "json", "plain", or "smart" (codemap + full content).
        output_file: Relative or absolute path to write output to. None returns the prompt directly (warning: can be very large).
        include_git_changes: Whether to include recent git diffs and log in the prompt (default: False).
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    # Validate va chuyen paths thanh absolute
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

    # Validate output_format
    valid_formats = {"xml", "json", "plain", "smart"}
    if output_format not in valid_formats:
        return (
            f"Error: Invalid format '{output_format}'. Use: {', '.join(valid_formats)}"
        )

    try:
        from services.prompt_build_service import PromptBuildService

        service = PromptBuildService()
        prompt_text, token_count, breakdown = service.build_prompt(
            file_paths=abs_paths,
            workspace=ws,
            instructions=instructions,
            output_format=output_format,
            include_git_changes=include_git_changes,
            use_relative_paths=True,
        )

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

            # Tra ve thong tin tom tat thay vi toan bo prompt (tiet kiem token)
            breakdown_lines = []
            for key, val in breakdown.items():
                if val > 0:
                    label = key.replace("_", " ").title()
                    breakdown_lines.append(f"  {label}: {val:,}")

            return (
                f"Prompt written to: {out_path}\n"
                f"Total tokens: {token_count:,}\n"
                f"Files included: {len(abs_paths)}\n"
                f"Format: {output_format}\n"
                f"Breakdown:\n" + "\n".join(breakdown_lines)
            )
        else:
            # Tra ve truc tiep (canh bao: co the rat lon)
            return (
                f"--- Prompt ({token_count:,} tokens, {len(abs_paths)} files, format={output_format}) ---\n"
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


if __name__ == "__main__":
    # Cho phep chay truc tiep: python mcp_server/server.py [workspace_path]
    ws = sys.argv[1] if len(sys.argv) > 1 else None
    run_mcp_server(ws)
