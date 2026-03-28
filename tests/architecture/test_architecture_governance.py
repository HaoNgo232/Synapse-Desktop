"""Architecture governance regression test."""

import subprocess
import sys
from pathlib import Path


def test_architecture_no_new_violations() -> None:
    """Dam bao khong phat sinh vi pham kien truc moi so voi baseline."""
    root = Path(__file__).resolve().parents[2]
    checker = root / "tools" / "architecture" / "check_architecture.py"

    proc = subprocess.run(
        [sys.executable, str(checker), "--strict"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    assert proc.returncode == 0, output
