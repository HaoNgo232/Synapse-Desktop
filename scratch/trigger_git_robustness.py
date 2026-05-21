import sys
import shutil
import subprocess
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from infrastructure.git.git_utils import get_diff_only
from infrastructure.git.git_remote_parse import parse_github_url


def test_branch_flag_injection():
    print(
        "=== Testing Scenario 1: Ref starting with hyphen (Flag/Argument Injection) ==="
    )
    url = "https://github.com/owner/repo/tree/-c=help"
    repo_info = parse_github_url(url)
    if repo_info:
        print(
            f"Parsed URL: owner={repo_info.owner}, repo={repo_info.repo}, ref={repo_info.ref}"
        )
        if repo_info.ref and repo_info.ref.startswith("-"):
            print(
                "[POTENTIAL BUG] repo_info.ref starts with a hyphen and will be passed directly to git clone!"
            )
    else:
        print("URL rejected (Safe)")


def test_special_characters_in_paths():
    print("\n=== Testing Scenario 2: Special characters in file paths ===")
    # Setup temporary git repo
    temp_dir = Path(__file__).resolve().parent.parent / "scratch_temp_repo"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)

    try:
        # Init git repo
        try:
            subprocess.run(
                ["git", "init"], cwd=temp_dir, capture_output=True, check=True
            )
        except FileNotFoundError:
            print(
                "[Cảnh báo] Không tìm thấy git.exe trong môi trường Windows/Wine. Bỏ qua Scenario 2."
            )
            return
        # Configure user for git commits
        subprocess.run(["git", "config", "user.name", "Test"], cwd=temp_dir, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"], cwd=temp_dir, check=True
        )

        # Create files with special names
        file_spaces = temp_dir / "file with spaces.txt"
        file_quotes = temp_dir / 'file"with"quotes.txt'
        file_pipes = temp_dir / "file|with|pipes.txt"

        file_spaces.write_text("spaces content", encoding="utf-8")
        file_quotes.write_text("quotes content", encoding="utf-8")
        file_pipes.write_text("pipes content", encoding="utf-8")

        # Stage and commit
        subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"], cwd=temp_dir, check=True
        )

        # Modify files to create diff
        file_spaces.write_text("spaces content modified", encoding="utf-8")
        file_quotes.write_text("quotes content modified", encoding="utf-8")
        file_pipes.write_text("pipes content modified", encoding="utf-8")

        print("Testing get_diff_only on temp repository...")
        res = get_diff_only(
            temp_dir, num_commits=0, include_staged=True, include_unstaged=True
        )

        print(f"Changed files detected: {res.changed_files}")

        # Verify if files were successfully found and read
        for f in [
            "file with spaces.txt",
            'file"with"quotes.txt',
            "file|with|pipes.txt",
        ]:
            if f in res.changed_files:
                print(f"  [OK] '{f}' detected in changed files")
            else:
                print(f"  [FAIL] '{f}' NOT detected in changed files")

        # Now test build_diff_only_prompt with include_changed_content=True
        from infrastructure.git.git_utils import build_diff_only_prompt

        prompt = build_diff_only_prompt(
            res,
            instructions="",
            include_changed_content=True,
            include_tree_structure=False,
            workspace_root=temp_dir,
        )

        print("\nChecking content inclusion in final prompt:")
        for name, content in [
            ("spaces", "spaces content modified"),
            ("quotes", "quotes content modified"),
            ("pipes", "pipes content modified"),
        ]:
            if content in prompt:
                print(f"  [OK] '{name}' content successfully included in prompt")
            else:
                print(
                    f"  [FAIL] '{name}' content NOT found in prompt (file read failed)"
                )

    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    test_branch_flag_injection()
    test_special_characters_in_paths()
