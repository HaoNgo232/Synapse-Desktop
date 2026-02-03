"""
Repo Manager - Quản lý remote repositories và cache.

Module này cung cấp:
- Clone remote repo với shallow clone (--depth 1)
- Cache management tại ~/.synapse/repos/
- Update existing repos với git pull
- Cleanup và quản lý disk space
"""

import subprocess
import shutil
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Callable
from datetime import datetime

from core.utils.git_remote_parse import (
    parse_github_url,
    build_clone_url,
    get_repo_cache_name,
    RemoteRepoInfo,
)

# Configure logger
logger = logging.getLogger(__name__)


# ============================================
# Error Classes
# ============================================


class RepoError(Exception):
    """Base error cho repo operations."""

    pass


class GitNotInstalledError(RepoError):
    """Git không được cài đặt."""

    pass


class RepoNotFoundError(RepoError):
    """Repository không tìm thấy hoặc private."""

    pass


class CloneTimeoutError(RepoError):
    """Clone operation bị timeout."""

    pass


class InvalidUrlError(RepoError):
    """URL không hợp lệ."""

    pass


# ============================================
# Data Classes
# ============================================


@dataclass
class CloneProgress:
    """
    Progress info cho clone operation.

    Attributes:
        status: Mô tả trạng thái hiện tại
        percentage: Phần trăm hoàn thành (0-100), None nếu không xác định
    """

    status: str
    percentage: Optional[int] = None


@dataclass
class CachedRepo:
    """
    Thông tin về một repo đã cache.

    Attributes:
        name: Tên folder trong cache
        path: Full path đến folder
        size_bytes: Kích thước folder (bytes)
        last_modified: Thời gian sửa đổi cuối
        repo_info: Parsed repo info (nếu có)
    """

    name: str
    path: Path
    size_bytes: int = 0
    last_modified: Optional[datetime] = None
    repo_info: Optional[RemoteRepoInfo] = None


# Type alias cho progress callback
ProgressCallback = Callable[[CloneProgress], None]


# ============================================
# RepoManager Class
# ============================================


class RepoManager:
    """
    Quản lý remote repositories và cache.

    Cache location: ~/.synapse/repos/

    Usage:
        manager = RepoManager()
        path = manager.clone_repo("tiangolo/fastapi")
        repos = manager.get_cached_repos()
        manager.delete_repo("tiangolo_fastapi")
    """

    # Default cache directory
    DEFAULT_CACHE_DIR = Path.home() / ".synapse" / "repos"

    # Clone timeout (seconds)
    DEFAULT_TIMEOUT = 120

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Khởi tạo RepoManager.

        Args:
            cache_dir: Custom cache directory (default: ~/.synapse/repos/)
        """
        self.cache_dir = cache_dir or self.DEFAULT_CACHE_DIR
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Đảm bảo cache directory tồn tại."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Cache directory: {self.cache_dir}")

    def _is_git_installed(self) -> bool:
        """Kiểm tra git có được cài đặt không."""
        return shutil.which("git") is not None

    def clone_repo(
        self,
        url: str,
        on_progress: Optional[ProgressCallback] = None,
        timeout: Optional[int] = None,
        force_reclone: bool = False,
    ) -> Path:
        """
        Clone hoặc update remote repository.

        Nếu repo đã tồn tại trong cache, sẽ chạy git pull để update.
        Nếu chưa tồn tại, sẽ shallow clone (--depth 1).

        Args:
            url: GitHub URL hoặc shorthand (owner/repo)
            on_progress: Callback để nhận progress updates
            timeout: Timeout cho clone operation (seconds)
            force_reclone: Nếu True, xóa repo cũ và clone lại

        Returns:
            Path đến thư mục repo đã clone

        Raises:
            GitNotInstalledError: Git không được cài đặt
            InvalidUrlError: URL không hợp lệ
            RepoNotFoundError: Repo không tìm thấy
            CloneTimeoutError: Clone bị timeout
            RepoError: Lỗi khác
        """
        if not self._is_git_installed():
            raise GitNotInstalledError(
                "Git không được cài đặt hoặc không có trong PATH"
            )

        # Parse URL
        repo_info = parse_github_url(url)
        if not repo_info:
            raise InvalidUrlError(f"URL không hợp lệ: {url}")

        # Determine cache path
        cache_name = get_repo_cache_name(repo_info)
        target_path = self.cache_dir / cache_name

        # Check if already exists
        if target_path.exists():
            if force_reclone:
                logger.info(f"Force reclone: Deleting existing repo {cache_name}")
                shutil.rmtree(target_path)
            else:
                # Update existing repo
                logger.info(f"Repo exists, updating: {cache_name}")
                self._update_repo(target_path, on_progress, timeout)
                return target_path

        # Clone new repo
        logger.info(f"Cloning new repo: {cache_name}")
        self._clone_new_repo(repo_info, target_path, on_progress, timeout)

        return target_path

    def _clone_new_repo(
        self,
        repo_info: RemoteRepoInfo,
        target_path: Path,
        on_progress: Optional[ProgressCallback],
        timeout: Optional[int],
    ) -> None:
        """
        Clone một repo mới với shallow clone.

        Sử dụng git clone --depth 1 để chỉ lấy commit mới nhất.
        Sau đó xóa .git folder để tiết kiệm dung lượng.
        """
        clone_url = build_clone_url(repo_info)
        timeout = timeout or self.DEFAULT_TIMEOUT

        # Report progress
        if on_progress:
            on_progress(CloneProgress(status="Đang clone repository...", percentage=0))

        try:
            # Build clone command
            cmd = ["git", "clone", "--depth", "1"]

            # Add branch if specified
            if repo_info.ref:
                cmd.extend(["--branch", repo_info.ref])

            cmd.extend(["--", clone_url, str(target_path)])

            # Execute clone
            logger.debug(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout

                # Check for common errors
                if (
                    "not found" in error_msg.lower()
                    or "repository not found" in error_msg.lower()
                ):
                    raise RepoNotFoundError(f"Repository không tìm thấy: {clone_url}")
                if "could not read" in error_msg.lower():
                    raise RepoNotFoundError(
                        f"Không thể truy cập repository (có thể là private): {clone_url}"
                    )

                raise RepoError(f"Clone failed: {error_msg}")

            # Report progress
            if on_progress:
                on_progress(CloneProgress(status="Đang dọn dẹp...", percentage=80))

            # Remove .git folder to save space
            git_dir = target_path / ".git"
            if git_dir.exists():
                shutil.rmtree(git_dir)
                logger.debug("Removed .git directory")

            # Report complete
            if on_progress:
                on_progress(CloneProgress(status="Hoàn thành!", percentage=100))

        except subprocess.TimeoutExpired:
            # Cleanup partial clone
            if target_path.exists():
                shutil.rmtree(target_path)
            raise CloneTimeoutError(f"Clone timeout sau {timeout} giây")
        except (RepoError, GitNotInstalledError, RepoNotFoundError, CloneTimeoutError):
            # Re-raise our errors
            raise
        except Exception as e:
            # Cleanup on error
            if target_path.exists():
                shutil.rmtree(target_path)
            raise RepoError(f"Clone failed: {e}")

    def _update_repo(
        self,
        repo_path: Path,
        on_progress: Optional[ProgressCallback],
        timeout: Optional[int],
    ) -> None:
        """
        Update existing repo với git pull.

        Note: Vì đã xóa .git folder sau clone, update sẽ không hoạt động.
        Trong trường hợp này, chỉ log warning.
        """
        git_dir = repo_path / ".git"

        if not git_dir.exists():
            # .git đã bị xóa, không thể update
            logger.warning(f"Cannot update repo without .git directory: {repo_path}")
            if on_progress:
                on_progress(
                    CloneProgress(
                        status="Repo đã được cache (không cần update)", percentage=100
                    )
                )
            return

        # If .git exists, run git pull
        timeout = timeout or self.DEFAULT_TIMEOUT

        if on_progress:
            on_progress(CloneProgress(status="Đang update repository...", percentage=0))

        try:
            result = subprocess.run(
                ["git", "-C", str(repo_path), "pull", "--ff-only"],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                logger.warning(f"Git pull failed: {result.stderr}")
            else:
                logger.info("Repository updated successfully")

            if on_progress:
                on_progress(CloneProgress(status="Hoàn thành!", percentage=100))

        except subprocess.TimeoutExpired:
            raise CloneTimeoutError(f"Update timeout sau {timeout} giây")

    def get_cached_repos(self) -> List[CachedRepo]:
        """
        Lấy danh sách tất cả repos đã cache.

        Returns:
            List các CachedRepo objects
        """
        repos = []

        if not self.cache_dir.exists():
            return repos

        for item in self.cache_dir.iterdir():
            if item.is_dir():
                try:
                    size = self._get_dir_size(item)
                    mtime = datetime.fromtimestamp(item.stat().st_mtime)

                    repos.append(
                        CachedRepo(
                            name=item.name,
                            path=item,
                            size_bytes=size,
                            last_modified=mtime,
                        )
                    )
                except Exception as e:
                    logger.error(f"Failed to get info for {item}: {e}")

        # Sort by last modified (newest first)
        repos.sort(key=lambda r: r.last_modified or datetime.min, reverse=True)

        return repos

    def _get_dir_size(self, path: Path) -> int:
        """Tính tổng size của directory (bytes)."""
        total = 0
        try:
            for file in path.rglob("*"):
                if file.is_file():
                    total += file.stat().st_size
        except Exception:
            pass
        return total

    def delete_repo(self, repo_name: str) -> bool:
        """
        Xóa một repo khỏi cache.

        Args:
            repo_name: Tên folder của repo (không phải full path)

        Returns:
            True nếu xóa thành công, False nếu không tìm thấy
        """
        repo_path = self.cache_dir / repo_name

        if not repo_path.exists():
            logger.warning(f"Repo not found: {repo_name}")
            return False

        try:
            shutil.rmtree(repo_path)
            logger.info(f"Deleted repo: {repo_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete repo {repo_name}: {e}")
            return False

    def clear_cache(self) -> int:
        """
        Xóa tất cả repos trong cache.

        Returns:
            Số repos đã xóa
        """
        count = 0

        if not self.cache_dir.exists():
            return count

        for item in self.cache_dir.iterdir():
            if item.is_dir():
                try:
                    shutil.rmtree(item)
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to delete {item}: {e}")

        logger.info(f"Cleared cache: {count} repos deleted")
        return count

    def get_cache_size(self) -> int:
        """
        Tính tổng dung lượng cache (bytes).

        Returns:
            Total size in bytes
        """
        if not self.cache_dir.exists():
            return 0
        return self._get_dir_size(self.cache_dir)

    def format_size(self, size_bytes: int) -> str:
        """
        Format size thành human-readable string.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted string (e.g., "1.5 MB")
        """
        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
