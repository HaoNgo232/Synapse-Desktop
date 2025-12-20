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
import tempfile
import os

from core.utils.git_utils import (
    is_git_repo,
    get_git_diffs,
    get_git_logs,
    GitDiffResult,
    GitLogResult,
    GitCommit,
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
            with patch("core.utils.git_utils.is_git_repo", return_value=True):
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
            with patch("core.utils.git_utils.is_git_repo", return_value=True):
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
            with patch("core.utils.git_utils.is_git_repo", return_value=True):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = subprocess.CalledProcessError(1, "git")

                    result = get_git_diffs(tmp_path)
                    assert result is None

    def test_timeout_error(self, tmp_path):
        """Timeout error returns None."""
        with patch("shutil.which", return_value="/usr/bin/git"):
            with patch("core.utils.git_utils.is_git_repo", return_value=True):
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
            with patch("core.utils.git_utils.is_git_repo", return_value=True):
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
            with patch("core.utils.git_utils.is_git_repo", return_value=True):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(stdout="", returncode=0)

                    result = get_git_logs(tmp_path)

                    assert result is not None
                    assert len(result.commits) == 0
                    assert result.log_content == ""

    def test_max_commits_parameter(self, tmp_path):
        """max_commits parameter is passed to git command."""
        with patch("shutil.which", return_value="/usr/bin/git"):
            with patch("core.utils.git_utils.is_git_repo", return_value=True):
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
            with patch("core.utils.git_utils.is_git_repo", return_value=True):
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
        from core.utils.git_utils import GitCommit

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
