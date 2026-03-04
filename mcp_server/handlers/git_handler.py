"""
Git Handler - Xu ly cac tool lien quan den git operations.

Bao gom: diff_summary.
"""

import subprocess
from typing import Optional

from mcp.server.fastmcp import Context

from mcp_server.core.constants import GIT_TIMEOUT, SAFE_GIT_REF, logger
from mcp_server.core.workspace_manager import WorkspaceManager


def register_tools(mcp_instance) -> None:
    """Dang ky git tools voi MCP server."""

    @mcp_instance.tool()
    async def diff_summary(
        target: str = "HEAD",
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Get summary of git changes: files added, modified, and deleted.

        Provides a concise categorized overview of changed files compared
        to a git target (branch, commit, or HEAD).

        Args:
            target: Git target to compare against (default: HEAD = uncommitted changes)
            workspace_path: Workspace root. Auto-detected if omitted.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        if not SAFE_GIT_REF.match(target):
            return f"Error: Invalid git ref '{target}'. Use alphanumeric, -, _, /, or HEAD."

        try:
            result = subprocess.run(
                ["git", "diff", "--name-status", target],
                cwd=ws,
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT,
                check=False,
            )

            if result.returncode != 0:
                if "not a git repository" in result.stderr.lower():
                    return "Error: Not a git repository."
                return f"Error: git diff failed: {result.stderr.strip()}"

            lines = result.stdout.strip().split("\n")
            if not lines or not lines[0]:
                return "No changes detected."

            changes = {"added": [], "modified": [], "deleted": []}
            for line in lines:
                parts = line.split("\t", 1)
                if len(parts) != 2:
                    continue
                status, filepath = parts[0], parts[1]
                if status == "A":
                    changes["added"].append(filepath)
                elif status == "M":
                    changes["modified"].append(filepath)
                elif status == "D":
                    changes["deleted"].append(filepath)

            total = sum(len(v) for v in changes.values())
            summary = [
                f"Git diff summary ({target}):",
                f"Total files changed: {total}\n",
            ]

            if changes["added"]:
                summary.append(f"Added ({len(changes['added'])}):")
                for f in changes["added"][:10]:
                    summary.append(f"  + {f}")
                if len(changes["added"]) > 10:
                    summary.append(f"  ... +{len(changes['added']) - 10} more")

            if changes["modified"]:
                summary.append(f"\nModified ({len(changes['modified'])}):")
                for f in changes["modified"][:10]:
                    summary.append(f"  M {f}")
                if len(changes["modified"]) > 10:
                    summary.append(f"  ... +{len(changes['modified']) - 10} more")

            if changes["deleted"]:
                summary.append(f"\nDeleted ({len(changes['deleted'])}):")
                for f in changes["deleted"][:10]:
                    summary.append(f"  - {f}")
                if len(changes["deleted"]) > 10:
                    summary.append(f"  ... +{len(changes['deleted']) - 10} more")

            return "\n".join(summary)

        except subprocess.TimeoutExpired:
            return f"Error: git diff timed out after {GIT_TIMEOUT}s."
        except Exception as e:
            logger.error("diff_summary error: %s", e)
            return f"Error: {e}"
