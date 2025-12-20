"""
Security Check - Secret Scanning Module

Module để quét và phát hiện các thông tin nhạy cảm (API Keys, Private Keys)
trong content trước khi copy, ngăn ngừa rò rỉ secrets cho LLM.

Sử dụng Regex patterns đã được kiểm chứng cho các dịch vụ phổ biến.
"""

import re
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
from core.file_utils import is_binary_by_extension


@dataclass
class SecretPattern:
    """Định nghĩa một pattern để phát hiện secret."""

    name: str
    pattern: re.Pattern
    description: Optional[str] = None


# Danh sách các Regex patterns để phát hiện secrets
# Dựa trên các patterns phổ biến từ detect-secrets và secretlint
SECRET_PATTERNS: list[SecretPattern] = [
    # OpenAI API Keys
    SecretPattern(
        name="OpenAI API Key",
        pattern=re.compile(r"sk-[a-zA-Z0-9]{20,}T3BlbkFJ[a-zA-Z0-9]{20,}"),
        description="OpenAI API key (sk-...T3BlbkFJ...)",
    ),
    # OpenAI Project API Key (newer format)
    SecretPattern(
        name="OpenAI Project Key",
        pattern=re.compile(r"sk-proj-[a-zA-Z0-9_-]{48,}"),
        description="OpenAI project API key (sk-proj-...)",
    ),
    # OpenAI Session Key
    SecretPattern(
        name="OpenAI Session Key",
        pattern=re.compile(r"sess-[a-zA-Z0-9]{40,}"),
        description="OpenAI session key (sess-...)",
    ),
    # Anthropic API Keys
    SecretPattern(
        name="Anthropic API Key",
        pattern=re.compile(r"sk-ant-[a-zA-Z0-9_-]{40,}"),
        description="Anthropic API key (sk-ant-...)",
    ),
    # AWS Access Key ID
    SecretPattern(
        name="AWS Access Key ID",
        pattern=re.compile(r"(?<![A-Za-z0-9/+=])AKIA[0-9A-Z]{16}(?![A-Za-z0-9/+=])"),
        description="AWS Access Key ID (AKIA...)",
    ),
    # AWS Secret Access Key:
    # Improved regex to reduce false positives (e.g. SHA1 hashes).
    # Requires at least one non-hex character (not 0-9a-fA-F) OR
    # essentially high entropy distribution.
    # Simple heuristic: must match 40 chars base64, but exclude if it looks like a pure hex hash.
    SecretPattern(
        name="AWS Secret Access Key",
        pattern=re.compile(
            r"(?<![A-Za-z0-9/+=])(?=.*[^0-9a-fA-F])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])"
        ),
        description="AWS Secret Access Key (40 chars, base64)",
    ),
    # GitHub Personal Access Token (classic)
    SecretPattern(
        name="GitHub Token (Classic)",
        pattern=re.compile(r"ghp_[a-zA-Z0-9]{36}"),
        description="GitHub Personal Access Token (ghp_...)",
    ),
    # GitHub Fine-grained Token
    SecretPattern(
        name="GitHub Token (Fine-grained)",
        pattern=re.compile(r"github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}"),
        description="GitHub Fine-grained PAT",
    ),
    # GitHub OAuth Access Token
    SecretPattern(
        name="GitHub OAuth Token",
        pattern=re.compile(r"gho_[a-zA-Z0-9]{36}"),
        description="GitHub OAuth Token (gho_...)",
    ),
    # Google API Key
    SecretPattern(
        name="Google API Key",
        pattern=re.compile(r"AIza[0-9A-Za-z_-]{35}"),
        description="Google API Key (AIza...)",
    ),
    # Stripe Keys
    SecretPattern(
        name="Stripe Secret Key",
        pattern=re.compile(r"sk_live_[a-zA-Z0-9]{24,}"),
        description="Stripe Secret Key (sk_live_...)",
    ),
    SecretPattern(
        name="Stripe Restricted Key",
        pattern=re.compile(r"rk_live_[a-zA-Z0-9]{24,}"),
        description="Stripe Restricted Key (rk_live_...)",
    ),
    # Private Keys (generic)
    SecretPattern(
        name="Private Key",
        pattern=re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
        description="Private key in PEM format",
    ),
    # Slack Bot Token
    SecretPattern(
        name="Slack Bot Token",
        pattern=re.compile(r"xoxb-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}"),
        description="Slack Bot Token (xoxb-...)",
    ),
    # Slack User Token
    SecretPattern(
        name="Slack User Token",
        pattern=re.compile(r"xoxp-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}"),
        description="Slack User Token (xoxp-...)",
    ),
    # Twilio API Key
    SecretPattern(
        name="Twilio API Key",
        pattern=re.compile(r"SK[a-f0-9]{32}"),
        description="Twilio API Key (SK...)",
    ),
    # SendGrid API Key
    SecretPattern(
        name="SendGrid API Key",
        pattern=re.compile(r"SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}"),
        description="SendGrid API Key (SG...)",
    ),
    # Generic high-entropy strings that look like secrets
    # (commented out as it may have too many false positives)
    # SecretPattern(
    #     name="High Entropy Secret",
    #     pattern=re.compile(r"['\"][a-zA-Z0-9]{32,}['\"]"),
    #     description="Long alphanumeric string in quotes",
    # ),
]


@dataclass
class SecretMatch:
    """Kết quả của một secret match."""

    secret_type: str
    line_number: int  # Line number within the file/content
    redacted_preview: str
    file_path: Optional[str] = None  # File path containing the secret


def scan_for_secrets(
    content: str, file_path: Optional[str] = None
) -> list[SecretMatch]:
    """
    Quét content để tìm các secrets tiềm ẩn.
    """
    matches: list[SecretMatch] = []
    lines = content.split("\n")

    for line_num, line in enumerate(lines, start=1):
        for pattern in SECRET_PATTERNS:
            for match in pattern.pattern.finditer(line):
                matched_text = match.group()
                # Tạo preview an toàn (che giấu phần lớn secret)
                if len(matched_text) > 10:
                    redacted = matched_text[:6] + "..." + matched_text[-4:]
                else:
                    redacted = matched_text[:3] + "..."

                matches.append(
                    SecretMatch(
                        secret_type=pattern.name,
                        line_number=line_num,
                        redacted_preview=redacted,
                        file_path=file_path,
                    )
                )

    # Loại bỏ duplicate dựa trên secret_type và line_number
    seen = set()
    unique_matches = []
    for m in matches:
        key = (m.secret_type, m.line_number, m.file_path)
        if key not in seen:
            seen.add(key)
            unique_matches.append(m)

    return unique_matches


def scan_secrets_in_files(
    file_paths: set[str], max_file_size: int = 1024 * 1024
) -> list[SecretMatch]:
    """
    Quét secrets trong danh sách các file.

    Args:
        file_paths: Set các đường dẫn file cần quét
        max_file_size: Limit size để tránh quét file quá lớn

    Returns:
        List các SecretMatch được tìm thấy
    """
    all_matches: list[SecretMatch] = []
    sorted_paths = sorted(file_paths)

    for path_str in sorted_paths:
        path = Path(path_str)
        try:
            if not path.is_file():
                continue
            if is_binary_by_extension(path):
                continue

            # Size check
            try:
                if path.stat().st_size > max_file_size:
                    continue
            except OSError:
                continue

            content = path.read_text(encoding="utf-8", errors="replace")
            file_matches = scan_for_secrets(
                content, file_path=path.name
            )  # Use basename for UI
            all_matches.extend(file_matches)

        except (OSError, IOError):
            pass

    return all_matches


def get_unique_secret_types(matches: list[SecretMatch]) -> list[str]:
    """
    Lấy danh sách các loại secret duy nhất từ kết quả scan.

    Args:
        matches: List các SecretMatch từ scan_for_secrets()

    Returns:
        List các secret type names (không trùng lặp)
    """
    return list(dict.fromkeys(m.secret_type for m in matches))


def format_security_warning(matches: list[SecretMatch]) -> str:
    """
    Tạo message cảnh báo cho user từ kết quả scan.

    Args:
        matches: List các SecretMatch từ scan_for_secrets()

    Returns:
        Message cảnh báo để hiển thị trong dialog
    """
    if not matches:
        return ""

    types = get_unique_secret_types(matches)
    count = len(matches)

    if count == 1:
        return f"Found 1 potential secret: {types[0]}"
    else:
        type_list = ", ".join(types[:3])
        if len(types) > 3:
            type_list += f" (+{len(types) - 3} more)"
        return f"Found {count} potential secrets: {type_list}"
