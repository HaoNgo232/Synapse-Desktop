import subprocess
import platform
from pathlib import Path
from typing import Optional, List

from domain.ports.git import IGitRepository


class PyGitAdapter(IGitRepository):
    """
    Adapter cho Git, sử dụng subprocess để gọi các lệnh git hệ thống.
    """

    def _run_git(self, command: List[str], workspace: Path) -> Optional[str]:
        try:
            creationflags = 0
            if platform.system() == "Windows":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

            result = subprocess.run(
                ["git"] + command,
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=creationflags,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def get_current_branch(self, workspace: Path) -> Optional[str]:
        return self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], workspace)

    def is_repo(self, path: Path) -> bool:
        res = self._run_git(["rev-parse", "--is-inside-work-tree"], path)
        return res == "true"

    def get_diff(self, workspace: Path) -> str:
        res = self._run_git(["diff", "HEAD"], workspace)
        return res if res else ""

    def get_changed_files(self, workspace: Path) -> List[str]:
        res = self._run_git(["diff", "--name-only", "HEAD"], workspace)
        if res:
            return res.splitlines()
        return []
