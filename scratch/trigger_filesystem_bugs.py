import os
import sys
import tempfile
import threading
from pathlib import Path

# Add project root to sys.path so we can import from infrastructure
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.filesystem.file_utils import (
    scan_directory,
    is_binary_file,
)
from infrastructure.filesystem.file_actions import (
    _resolve_path,
)
from infrastructure.filesystem.ignore_engine import IgnoreEngine


def test_issue_1_gitignore_negation():
    """
    Demonstrates Issue 1: Nested gitignore negation precedence bug.
    If a parent gitignore ignores '*.log' and a nested gitignore negates '!important.log',
    the scanner erroneously ignores 'important.log' because it processes the parent PathSpec first,
    matches '*.log', and breaks early before checking the nested PathSpec.
    """
    print("\n--- Test Issue 1: Gitignore Negation Precedence Bug ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "repo"
        repo.mkdir()

        # Parent gitignore
        (repo / ".gitignore").write_text("*.log\n")

        # Nested directory with its own gitignore negating important.log
        sub = repo / "sub"
        sub.mkdir()
        (sub / ".gitignore").write_text("!important.log\n")

        # Files
        (sub / "important.log").write_text("critical data")
        (sub / "other.log").write_text("debug log")
        (sub / "normal.txt").write_text("normal text")

        engine = IgnoreEngine()
        tree = scan_directory(repo, engine)

        # Flatten tree to find loaded files
        def get_all_files(item):
            files = []
            if not item.is_dir:
                files.append(item.path)
            for child in item.children:
                files.extend(get_all_files(child))
            return files

        found_files = [os.path.basename(f) for f in get_all_files(tree)]
        print("Files found on disk: ['important.log', 'other.log', 'normal.txt']")
        print(f"Files scanned by ignore engine: {found_files}")

        # Expected git behavior: 'important.log' and 'normal.txt' should be scanned, 'other.log' ignored.
        # Actual behavior: both 'important.log' and 'other.log' are ignored.
        if "important.log" not in found_files:
            print(
                "❌ BUG CONFIRMED: 'important.log' was ignored despite nested negation '!important.log'!"
            )
        else:
            print("✅ 'important.log' was correctly included.")


def test_issue_2_parent_root_relative_pattern():
    """
    Demonstrates Issue 2: Parent gitignore root-relative pattern inheritance bug.
    A pattern like '/build' in the git root gitignore should only ignore 'git_root/build'.
    But when scanning a subdirectory, the engine appends parent gitignore patterns to the subdirectory's
    patterns list and compiles it as root-relative to the subdirectory, causing it to incorrectly ignore
    'git_root/subdir/build'.
    """
    print(
        "\n--- Test Issue 2: Parent Gitignore Root-Relative Pattern Inheritance Bug ---"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "repo"
        repo.mkdir()

        # Git root gitignore
        (repo / ".gitignore").write_text("/build\n")
        (repo / ".git").mkdir()  # Make it a git root

        # Subdirectory
        subdir = repo / "subdir"
        subdir.mkdir()

        # 'build' folders at git root vs subdirectory
        root_build = repo / "build"
        root_build.mkdir()
        (root_build / "file1.txt").write_text("root build file")

        sub_build = subdir / "build"
        sub_build.mkdir()
        (sub_build / "file2.txt").write_text("subdir build file")

        (subdir / "normal.txt").write_text("normal file")

        engine = IgnoreEngine()

        # Scan the subdirectory directly (simulating opening a subdirectory as workspace root)
        tree = scan_directory(subdir, engine, use_default_ignores=False)

        def get_all_files(item):
            files = []
            if not item.is_dir:
                files.append(item.path)
            for child in item.children:
                files.extend(get_all_files(child))
            return files

        found_files = [os.path.relpath(f, subdir) for f in get_all_files(tree)]
        print("Files found on disk in subdir: ['build/file2.txt', 'normal.txt']")
        print(f"Files scanned by engine in subdir: {found_files}")

        # Expected git behavior: 'build/file2.txt' should be scanned because '/build' only ignores root-level 'build'.
        # Actual behavior: 'build/file2.txt' is ignored because '/build' was inherited and anchored to 'subdir'.
        if "build/file2.txt" not in found_files:
            print(
                "❌ BUG CONFIRMED: 'subdir/build/file2.txt' was incorrectly ignored due to inherited root-relative pattern!"
            )
        else:
            print("✅ 'subdir/build/file2.txt' was correctly included.")


def test_issue_3_fifo_hang():
    """
    Demonstrates Issue 3: FIFO/Named Pipe Hang Hazard in is_binary_file.
    If a named pipe (FIFO) is present in the workspace, is_binary_file will open it
    without non-blocking mode, which blocks the scanner thread indefinitely.
    """
    print("\n--- Test Issue 3: FIFO/Named Pipe Hang Hazard ---")
    if not hasattr(os, "mkfifo"):
        print("Skipped: os.mkfifo is not supported on this platform.")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        fifo_path = Path(tmpdir) / "test_fifo"
        os.mkfifo(fifo_path)

        print("Created FIFO at:", fifo_path)
        print(
            "Calling is_binary_file on the FIFO in a background thread to check for hang..."
        )

        is_hang = [True]

        def call_is_binary():
            try:
                # This will try to open(fifo_path, "rb") and block
                is_binary_file(fifo_path)
                is_hang[0] = False
            except Exception as e:
                print("is_binary_file raised exception:", e)
                is_hang[0] = False

        t = threading.Thread(target=call_is_binary, daemon=True)
        t.start()

        # Wait 2 seconds to see if it blocks
        t.join(timeout=2.0)

        if is_hang[0]:
            print("❌ BUG CONFIRMED: is_binary_file is HANGING on the named pipe!")
        else:
            print("✅ is_binary_file did not hang.")


def test_issue_4_path_traversal_empty_workspace_roots():
    """
    Demonstrates Issue 4: Path traversal bypass when workspace_roots is empty or None.
    If workspace_roots is empty or None, _resolve_path will not perform any security check
    and will happily return absolute or traversal paths.
    """
    print("\n--- Test Issue 4: Path Traversal Bypass on Empty/None workspace_roots ---")

    malicious_path = "/etc/passwd"

    # Try resolving with workspace_roots=None
    try:
        resolved = _resolve_path(malicious_path, None, None)
        print(f"Resolved path with empty workspace_roots: {resolved}")
        if str(resolved) == malicious_path:
            print(
                "❌ BUG CONFIRMED: Path traversal check is completely bypassed when workspace_roots is empty/None!"
            )
        else:
            print("✅ Path traversal was blocked.")
    except Exception as e:
        print(f"✅ Blocked with exception: {e}")


if __name__ == "__main__":
    test_issue_1_gitignore_negation()
    test_issue_2_parent_root_relative_pattern()
    test_issue_3_fifo_hang()
    test_issue_4_path_traversal_empty_workspace_roots()
