"""
Unit tests cho Git Utils module.

Test các case:
- is_git_repo(): Kiểm tra thư mục có phải Git repo.
- get_git_diffs(): Lấy working tree và staged diffs.
- get_git_logs(): Lấy commit history.
- Parsing logic cho git log output.
- Error handling khi git không available.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess
import os
import sys

from infrastructure.git.git_utils import (
    is_git_repo,
    get_git_diffs,
    get_git_logs,
    GitDiffResult,
    GitLogResult,
    GitCommit,
    extract_changed_files_from_diff,
    filter_diff_by_files,
)


class TestIsGitRepo:
    """Test is_git_repo() function."""

    def test_not_a_repo(self, tmp_path):
        """Non-git directory returns False."""
        result = is_git_repo(tmp_path)
        assert result is False

    def test_nonexistent_path(self):
        """Nonexistent path returns False."""
        result = is_git_repo(Path("/nonexistent/path"))
        assert result is False

    def test_git_not_installed(self, tmp_path):
        """Git not installed returns False gracefully."""
        with patch("shutil.which", return_value=None):
            result = is_git_repo(tmp_path)
            assert result is False

    @pytest.mark.skipif(
        not os.path.exists("/home/hao/Desktop/labs/synapse-desktop/.git"),
        reason="Not running in git repo",
    )
    def test_actual_git_repo(self):
        """Actual git repo returns True."""
        # Sử dụng thư mục project hiện tại (đã biết là git repo)
        result = is_git_repo(Path("/home/hao/Desktop/labs/synapse-desktop"))
        assert result is True


class TestGetGitDiffs:
    """Test get_git_diffs() function."""

    def test_not_a_repo(self, tmp_path):
        """Non-git directory returns None."""
        result = get_git_diffs(tmp_path)
        assert result is None

    def test_git_not_installed(self, tmp_path):
        """Git not installed returns None."""
        with patch("shutil.which", return_value=None):
            result = get_git_diffs(tmp_path)
            assert result is None

    def test_mock_git_diff_output(self, tmp_path):
        """Mocked git diff returns GitDiffResult."""
        mock_worktree = "diff --git a/file.py b/file.py\n+new line"
        mock_staged = "diff --git a/staged.py b/staged.py\n-old line"

        with patch("shutil.which", return_value="/usr/bin/git"):
            with patch("infrastructure.git.git_utils.is_git_repo", return_value=True):
                with patch("subprocess.run") as mock_run:
                    # Mock cho 2 lần gọi subprocess.run
                    mock_run.side_effect = [
                        MagicMock(stdout=mock_worktree, returncode=0),
                        MagicMock(stdout=mock_staged, returncode=0),
                    ]

                    result = get_git_diffs(tmp_path)

                    assert result is not None
                    assert isinstance(result, GitDiffResult)
                    assert "new line" in result.work_tree_diff
                    assert "old line" in result.staged_diff

    def test_empty_diff(self, tmp_path):
        """Empty diff returns GitDiffResult with empty strings."""
        with patch("shutil.which", return_value="/usr/bin/git"):
            with patch("infrastructure.git.git_utils.is_git_repo", return_value=True):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = [
                        MagicMock(stdout="", returncode=0),
                        MagicMock(stdout="", returncode=0),
                    ]

                    result = get_git_diffs(tmp_path)

                    assert result is not None
                    assert result.work_tree_diff == ""
                    assert result.staged_diff == ""

    def test_subprocess_error(self, tmp_path):
        """Subprocess error returns None."""
        with patch("shutil.which", return_value="/usr/bin/git"):
            with patch("infrastructure.git.git_utils.is_git_repo", return_value=True):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = subprocess.CalledProcessError(1, "git")

                    result = get_git_diffs(tmp_path)
                    assert result is None

    def test_timeout_error(self, tmp_path):
        """Timeout error returns None."""
        with patch("shutil.which", return_value="/usr/bin/git"):
            with patch("infrastructure.git.git_utils.is_git_repo", return_value=True):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = subprocess.TimeoutExpired("git", 10)

                    result = get_git_diffs(tmp_path)
                    assert result is None


class TestGetGitLogs:
    """Test get_git_logs() function."""

    def test_not_a_repo(self, tmp_path):
        """Non-git directory returns None."""
        result = get_git_logs(tmp_path)
        assert result is None

    def test_git_not_installed(self, tmp_path):
        """Git not installed returns None."""
        with patch("shutil.which", return_value=None):
            result = get_git_logs(tmp_path)
            assert result is None

    def test_mock_git_log_output(self, tmp_path):
        """Mocked git log returns GitLogResult with parsed commits."""
        # Format: \x00hash|date|subject\nfile1\nfile2
        mock_log = "\x00abc1234|2024-12-20|First commit\nfile1.py\nfile2.py"
        mock_log += "\x00def5678|2024-12-19|Second commit\nfile3.py"

        with patch("shutil.which", return_value="/usr/bin/git"):
            with patch("infrastructure.git.git_utils.is_git_repo", return_value=True):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(stdout=mock_log, returncode=0)

                    result = get_git_logs(tmp_path, max_commits=10)

                    assert result is not None
                    assert isinstance(result, GitLogResult)
                    assert len(result.commits) == 2

                    # First commit
                    assert result.commits[0].hash == "abc1234"
                    assert result.commits[0].message == "First commit"
                    assert "file1.py" in result.commits[0].files
                    assert "file2.py" in result.commits[0].files

                    # Second commit
                    assert result.commits[1].hash == "def5678"
                    assert result.commits[1].message == "Second commit"

    def test_empty_log(self, tmp_path):
        """Empty log returns GitLogResult with empty commits."""
        with patch("shutil.which", return_value="/usr/bin/git"):
            with patch("infrastructure.git.git_utils.is_git_repo", return_value=True):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(stdout="", returncode=0)

                    result = get_git_logs(tmp_path)

                    assert result is not None
                    assert len(result.commits) == 0
                    assert result.log_content == ""

    def test_windows_sanitizes_null_char_in_log_content(self, tmp_path):
        """Tren Windows, log_content khong duoc chua NULL char (\\x00) de tranh clipboard truncate."""
        # Format: \x00hash|date|subject\nfile1\nfile2
        mock_log = "\x00abc1234|2024-12-20|First commit\nfile1.py\nfile2.py"
        mock_log += "\x00def5678|2024-12-19|Second commit\nfile3.py"

        with patch("shutil.which", return_value="/usr/bin/git"):
            with patch("infrastructure.git.git_utils.is_git_repo", return_value=True):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(stdout=mock_log, returncode=0)
                    with patch.object(sys, "platform", "win32"):
                        result = get_git_logs(tmp_path, max_commits=10)

        assert result is not None
        assert "\x00" not in result.log_content
        # Ensure still contains commit headers
        assert "abc1234|2024-12-20|First commit" in result.log_content

    def test_max_commits_parameter(self, tmp_path):
        """max_commits parameter is passed to git command."""
        with patch("shutil.which", return_value="/usr/bin/git"):
            with patch("infrastructure.git.git_utils.is_git_repo", return_value=True):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(stdout="", returncode=0)

                    get_git_logs(tmp_path, max_commits=5)

                    # Kiểm tra command có chứa -n 5
                    call_args = mock_run.call_args[0][0]
                    assert "-n" in call_args
                    n_index = call_args.index("-n")
                    assert call_args[n_index + 1] == "5"

    def test_subprocess_error(self, tmp_path):
        """Subprocess error returns None."""
        with patch("shutil.which", return_value="/usr/bin/git"):
            with patch("infrastructure.git.git_utils.is_git_repo", return_value=True):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = subprocess.CalledProcessError(1, "git")

                    result = get_git_logs(tmp_path)
                    assert result is None


class TestGitDiffResult:
    """Test GitDiffResult dataclass."""

    def test_creation(self):
        """GitDiffResult can be created."""
        result = GitDiffResult(
            work_tree_diff="diff content", staged_diff="staged content"
        )
        assert result.work_tree_diff == "diff content"
        assert result.staged_diff == "staged content"

    def test_empty_creation(self):
        """GitDiffResult can be created with empty strings."""
        result = GitDiffResult(work_tree_diff="", staged_diff="")
        assert result.work_tree_diff == ""
        assert result.staged_diff == ""


class TestGitLogResult:
    """Test GitLogResult dataclass."""

    def test_creation(self):
        """GitLogResult can be created."""

        commits = [
            GitCommit(
                hash="abc123", date="2024-12-20", message="Test", files=["file.py"]
            )
        ]
        result = GitLogResult(commits=commits, log_content="raw log")

        assert len(result.commits) == 1
        assert result.log_content == "raw log"


class TestIntegration:
    """Integration tests với actual git commands (nếu available)."""

    @pytest.mark.skipif(
        not os.path.exists("/home/hao/Desktop/labs/synapse-desktop/.git"),
        reason="Not running in git repo",
    )
    def test_get_git_diffs_real(self):
        """Get diffs from actual git repo."""
        result = get_git_diffs(Path("/home/hao/Desktop/labs/synapse-desktop"))

        # Có thể là None nếu không có changes, nhưng không nên error
        if result is not None:
            assert isinstance(result, GitDiffResult)

    @pytest.mark.skipif(
        not os.path.exists("/home/hao/Desktop/labs/synapse-desktop/.git"),
        reason="Not running in git repo",
    )
    def test_get_git_logs_real(self):
        """Get logs from actual git repo."""
        result = get_git_logs(
            Path("/home/hao/Desktop/labs/synapse-desktop"), max_commits=3
        )

        assert result is not None
        assert isinstance(result, GitLogResult)
        # Repo có commits nên phải có data
        assert len(result.commits) > 0


class TestDiffFiltering:
    """Test filter_diff_by_files() va extract_changed_files_from_diff()."""

    def test_filter_diff_by_files_basic(self):
        diff = """diff --git a/src/app.py b/src/app.py
index abc..def 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,4 @@
+import os
 import sys

 def main():
diff --git a/pnpm-lock.yaml b/pnpm-lock.yaml
index 111..222 100644
--- a/pnpm-lock.yaml
+++ b/pnpm-lock.yaml
@@ -1,100 +1,150 @@
-old lock content
+new lock content
diff --git a/src/utils.py b/src/utils.py
index 333..444 100644
--- a/src/utils.py
+++ b/src/utils.py
@@ -5,3 +5,5 @@
 def helper():
-    pass
+    return True
+    # added comment
"""
        result = filter_diff_by_files(diff, ["src/app.py", "src/utils.py"])
        assert "src/app.py" in result
        assert "src/utils.py" in result
        assert "pnpm-lock.yaml" not in result

    def test_filter_diff_empty_selection(self):
        diff = "diff --git a/file.py b/file.py\n..."
        result = filter_diff_by_files(diff, [])
        assert result == ""

    def test_filter_diff_all_selected(self):
        diff = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-old
+new
"""
        result = filter_diff_by_files(diff, ["a.py"])
        assert "a.py" in result

    def test_extract_changed_files(self):
        diff = """diff --git a/src/app.py b/src/app.py
index abc..def
diff --git a/pnpm-lock.yaml b/pnpm-lock.yaml
index 111..222
diff --git a/src/utils.py b/src/utils.py
index 333..444
"""
        files = extract_changed_files_from_diff(diff)
        assert files == ["src/app.py", "pnpm-lock.yaml", "src/utils.py"]

    def test_extract_renamed_files(self):
        diff = """diff --git a/old_name.py b/new_name.py
similarity index 95%
rename from old_name.py
rename to new_name.py
"""
        files = extract_changed_files_from_diff(diff)
        assert "new_name.py" in files


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
