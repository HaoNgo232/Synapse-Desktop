"""
File Handler - Xu ly cac tool lien quan den file operations.

Bao gom: read_file_range, get_file_metrics.
"""

from pathlib import Path
from typing import Optional

from mcp_server.core.constants import logger


def register_tools(mcp_instance) -> None:
    """Dang ky file tools voi MCP server.

    Args:
        mcp_instance: FastMCP server instance.
    """

    # Ham read_file_range doc noi dung file theo khoang dong tu chon
    @mcp_instance.tool()
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

        # Dung is_relative_to() de chong path traversal dung cach
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
                # Dung splitlines() thay vi count("\n")+1 de tranh dem thua
                total_lines = len(content.splitlines())
                # Token estimate tu file size (tranh encode() toan bo content)
                estimated_tokens = file_size // 4
                line_info = f"Total lines: {total_lines}"

            header = f"File: {relative_path}\n{line_info} | ~{estimated_tokens:,} tokens\n{'=' * 60}\n"
            return header + content

        except Exception as e:
            logger.error("read_file error for %s: %s", relative_path, e)
            return f"Error reading file: {e}"

    # Ham get_file_metrics tinh toan cac thong so code nhu LOC, so luong ham, lop va complexity
    @mcp_instance.tool()
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
                1
                for line in lines
                if line.strip().startswith(("#", "//", "/*", "*", "*/"))
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
