"""
Git Remote Parse - URL parsing và validation cho remote repositories.

Module này cung cấp các utilities để:
- Parse GitHub URL (full URL, shorthand owner/repo)
- Extract owner, repo, branch/tag/commit từ URL
- Validate URL để chống command injection
"""

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse
import logging

# Configure logger
logger = logging.getLogger(__name__)


@dataclass
class RemoteRepoInfo:
    """
    Thông tin parsed từ remote repository URL.

    Attributes:
        owner: GitHub username hoặc organization
        repo: Repository name
        ref: Branch, tag, hoặc commit SHA (optional)
        original_url: URL gốc trước khi parse
    """

    owner: str
    repo: str
    ref: Optional[str] = None
    original_url: str = ""


# Pattern cho GitHub shorthand: owner/repo
# Cho phép: letters, numbers, hyphens, underscores, dots
# Phải bắt đầu và kết thúc bằng alphanumeric
VALID_NAME_PATTERN = r"[a-zA-Z0-9](?:[a-zA-Z0-9._-]*[a-zA-Z0-9])?"
SHORTHAND_REGEX = re.compile(f"^{VALID_NAME_PATTERN}/{VALID_NAME_PATTERN}$")


def is_valid_shorthand(value: str) -> bool:
    """
    Kiểm tra xem value có phải là GitHub shorthand (owner/repo) không.

    Args:
        value: String cần kiểm tra

    Returns:
        True nếu là valid shorthand format

    Examples:
        >>> is_valid_shorthand("tiangolo/fastapi")
        True
        >>> is_valid_shorthand("https://github.com/owner/repo")
        False
    """
    if not value or "/" not in value:
        return False
    return bool(SHORTHAND_REGEX.match(value))


def validate_git_url(url: str) -> None:
    """
    Validate Git URL để chống command injection và các attacks.

    Args:
        url: URL cần validate

    Raises:
        ValueError: Nếu URL chứa dangerous parameters hoặc invalid format
    """
    # Chặn command injection qua git options
    dangerous_params = ["--upload-pack", "--config", "--exec", "-c ", "--receive-pack"]
    for param in dangerous_params:
        if param in url:
            raise ValueError(f"URL chứa parameter không an toàn: {param}")

    # Kiểm tra protocol - chỉ cho phép https:// hoặc git@
    if not (url.startswith("https://") or url.startswith("git@")):
        # Có thể là shorthand, skip validation
        if is_valid_shorthand(url):
            return
        raise ValueError("URL phải bắt đầu bằng 'https://' hoặc 'git@'")

    # Validate URL format cho https://
    if url.startswith("https://"):
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                raise ValueError("URL không có hostname")
        except Exception as e:
            raise ValueError(f"URL format không hợp lệ: {e}")


def parse_github_url(url: str) -> Optional[RemoteRepoInfo]:
    """
    Parse GitHub URL hoặc shorthand thành RemoteRepoInfo.

    Supported formats:
    - owner/repo (shorthand)
    - https://github.com/owner/repo
    - https://github.com/owner/repo.git
    - https://github.com/owner/repo/tree/branch
    - https://github.com/owner/repo/tree/feature/my-feature (nested branch)
    - https://github.com/owner/repo/commit/abc123
    - git@github.com:owner/repo.git

    Args:
        url: GitHub URL hoặc shorthand

    Returns:
        RemoteRepoInfo nếu parse thành công, None nếu không phải GitHub URL

    Raises:
        ValueError: Nếu URL format không hợp lệ hoặc có security issues
    """
    if not url or not url.strip():
        return None

    url = url.strip()

    # Validate trước - nếu không valid, return None thay vì raise
    try:
        validate_git_url(url)
    except ValueError:
        return None

    # Case 1: Shorthand format (owner/repo)
    if is_valid_shorthand(url):
        parts = url.split("/")
        # Remove .git suffix if present
        repo = parts[1].removesuffix(".git")
        logger.debug(f"Parsed shorthand: {url}")
        return RemoteRepoInfo(owner=parts[0], repo=repo, original_url=url)

    # Case 2: SSH format (git@github.com:owner/repo.git)
    if url.startswith("git@github.com:"):
        path = url[len("git@github.com:") :]
        path = path.removesuffix(".git")
        parts = path.split("/")
        if len(parts) >= 2:
            logger.debug(f"Parsed SSH URL: {url}")
            return RemoteRepoInfo(owner=parts[0], repo=parts[1], original_url=url)
        return None

    # Case 3: HTTPS URL
    try:
        parsed = urlparse(url)

        # Chỉ accept github.com
        if parsed.netloc not in ["github.com", "www.github.com"]:
            logger.debug(f"Not a GitHub URL: {url}")
            return None

        # Parse path
        path_parts = [p for p in parsed.path.split("/") if p]

        if len(path_parts) < 2:
            return None

        owner = path_parts[0]
        repo = path_parts[1].removesuffix(".git")
        ref = None

        # Extract ref từ /tree/branch hoặc /commit/sha
        if len(path_parts) >= 4:
            if path_parts[2] == "tree":
                # Branch có thể chứa / (ví dụ: feature/my-feature)
                ref = "/".join(path_parts[3:])
            elif path_parts[2] == "commit":
                ref = path_parts[3]

        logger.debug(f"Parsed HTTPS URL: owner={owner}, repo={repo}, ref={ref}")
        return RemoteRepoInfo(owner=owner, repo=repo, ref=ref, original_url=url)

    except Exception as e:
        logger.error(f"Failed to parse URL {url}: {e}")
        return None


def build_clone_url(info: RemoteRepoInfo) -> str:
    """
    Build git clone URL từ RemoteRepoInfo.

    Args:
        info: Parsed repo info

    Returns:
        HTTPS URL ready for git clone
    """
    return f"https://github.com/{info.owner}/{info.repo}.git"


def get_repo_cache_name(info: RemoteRepoInfo) -> str:
    """
    Generate tên folder cache cho repo.

    Format: owner_repo hoặc owner_repo_ref (nếu có ref)

    Args:
        info: Parsed repo info

    Returns:
        Cache folder name (safe for filesystem)
    """
    # Replace / với _ trong ref (cho nested branches)
    if info.ref:
        safe_ref = info.ref.replace("/", "_").replace("\\", "_")
        return f"{info.owner}_{info.repo}_{safe_ref}"
    return f"{info.owner}_{info.repo}"
