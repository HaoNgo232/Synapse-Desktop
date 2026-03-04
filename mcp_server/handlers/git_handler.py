"""
Git Handler - Xu ly cac tool lien quan den git operations.

Bao gom: diff_summary.
"""

import subprocess
from pathlib import Path

from mcp_server.core.constants import GIT_TIMEOUT, SAFE_GIT_REF, logger


def register_tools(mcp_instance) -> None:
    """Dang ky git tools voi MCP server.

    Args:
        mcp_instance: FastMCP server instance.
    """

    # Ham diff_summary tom tat cac thay doi trong git (files, functions added/modified/deleted)
    @mcp_instance.tool()
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

        # Validate target de chong git argument injection.
        # Ngay ca khi dung list-form subprocess (khong shell=True),
        # git van dien giai arguments bat dau voi "--" nhu options.
        if not SAFE_GIT_REF.match(target):
            return (
                f"Error: Invalid git target '{target}'. "
                "Use a branch name, tag, or commit hash."
            )

        try:
            from core.codemaps.symbol_extractor import extract_symbols

            # Kiem tra co phai git repo khong
            git_check = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=ws,
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT,
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
                timeout=GIT_TIMEOUT,
            )

            if result.returncode != 0:
                return f"Error running git diff: {result.stderr}"

            changed_files = [f.strip() for f in result.stdout.splitlines() if f.strip()]

            if not changed_files:
                return f"No changes detected compared to {target}"

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
            }
            code_files = [
                f for f in changed_files if Path(f).suffix.lower() in code_exts
            ]

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
                        timeout=GIT_TIMEOUT,
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
                                details.append(
                                    f"  - Deleted: {', '.join(sorted(deleted))}"
                                )
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
