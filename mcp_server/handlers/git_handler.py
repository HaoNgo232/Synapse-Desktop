"""
Git Handler - Xu ly cac tool lien quan den git operations.

Bao gom: diff_summary.
"""

import asyncio
import subprocess
from typing import Annotated, Optional

from mcp.server.fastmcp import Context
from pydantic import Field

from mcp_server.core.constants import GIT_TIMEOUT, SAFE_GIT_REF, logger
from mcp_server.core.workspace_manager import WorkspaceManager


def register_tools(mcp_instance) -> None:
    """Dang ky git tools voi MCP server."""

    @mcp_instance.tool()
    async def diff_summary(
        target: Annotated[
            str,
            Field(
                description='Git ref to compare against (e.g., "HEAD", "main", "HEAD~3", a commit hash). Default: "HEAD" (unstaged changes).'
            ),
        ] = "HEAD",
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted."
            ),
        ] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Get a summary of git changes: files added, modified, deleted, and renamed.

        Groups results by change type with file counts. Useful for understanding the scope of recent work before a code review.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        if not SAFE_GIT_REF.match(target):
            return f"Error: Invalid git ref '{target}'. Use alphanumeric, -, _, /, or HEAD."

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "diff", "--name-status", target, "--"],
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

            changes = {"added": [], "modified": [], "deleted": [], "renamed": []}
            for line in lines:
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                status = parts[0]
                if status == "A":
                    changes["added"].append(parts[1])
                elif status == "M":
                    changes["modified"].append(parts[1])
                elif status == "D":
                    changes["deleted"].append(parts[1])
                elif status.startswith("R"):
                    if len(parts) >= 3:
                        changes["renamed"].append(f"{parts[1]} -> {parts[2]}")
                    else:
                        changes["renamed"].append(parts[1])
                elif status.startswith("C"):
                    if len(parts) >= 3:
                        changes["added"].append(f"{parts[2]} (copied from {parts[1]})")
                    else:
                        changes["added"].append(parts[1])

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

            if changes["renamed"]:
                summary.append(f"\nRenamed ({len(changes['renamed'])}):")
                for f in changes["renamed"][:10]:
                    summary.append(f"  R {f}")
                if len(changes["renamed"]) > 10:
                    summary.append(f"  ... +{len(changes['renamed']) - 10} more")

            return "\n".join(summary)

        except subprocess.TimeoutExpired:
            return f"Error: git diff timed out after {GIT_TIMEOUT}s."
        except Exception as e:
            logger.error("diff_summary error: %s", e)
            return f"Error: {e}"
