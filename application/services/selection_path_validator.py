"""
Selection Path Validator - Domain service để lọc và xác thực đường dẫn do AI trả về.
Chống các rủi ro bảo mật: Path Traversal, Workspace Escape, Sensitive Files, Non-existent Files.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple, Set


@dataclass
class ValidationResult:
    """
    Kết quả xác thực danh sách file path.
    """

    valid_paths: List[str] = field(
        default_factory=list
    )  # Các relative paths hợp lệ (chuẩn hóa separator thành /)
    rejected_paths: List[Tuple[str, str]] = field(
        default_factory=list
    )  # Danh sách (raw_path, reason)
    sensitive_blocked: List[str] = field(
        default_factory=list
    )  # Các paths bị block do nhạy cảm


# Các file nhạy cảm cần block mặc định (chuyển sang lowercase để so sánh)
SENSITIVE_FILENAMES = {
    ".env",
    "id_rsa",
    "id_ed25519",
    "id_dsa",
    "credentials.json",
    "client_secret.json",
}

SENSITIVE_EXTENSIONS = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
}


def is_relative_to(path: Path, base: Path) -> bool:
    """
    Helper tương thích ngược để kiểm tra xem path có nằm trong thư mục base hay không.
    """
    try:
        # Sử dụng resolve để xử lý symlink và normalize path trước khi so sánh
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def validate_ai_selection(
    workspace: str,
    raw_paths: List[str],
    ignore_patterns: Optional[List[str]] = None,
    max_results: int = 200,
) -> ValidationResult:
    """
    Xác thực toàn diện các file paths do AI gợi ý.
    """
    result = ValidationResult()
    if not workspace:
        return result

    try:
        workspace_root = Path(workspace).resolve(strict=True)
    except Exception:
        # Nếu workspace không tồn tại hoặc lỗi resolve
        result.rejected_paths.append((workspace, "Workspace root cannot be resolved"))
        return result

    seen_normalized: Set[str] = set()

    for raw in raw_paths:
        if not isinstance(raw, str):
            result.rejected_paths.append((str(raw), "Not a string"))
            continue

        trimmed = raw.strip()
        if not trimmed:
            result.rejected_paths.append((raw, "Empty path"))
            continue

        if "\x00" in trimmed:
            result.rejected_paths.append((raw, "Path contains NUL character"))
            continue

        # 1. Chống absolute path
        # Kiểm tra bắt đầu bằng / hoặc \ hoặc có drive name (Windows)
        if (
            trimmed.startswith("/")
            or trimmed.startswith("\\")
            or (len(trimmed) > 1 and trimmed[1] == ":")
        ):
            result.rejected_paths.append((raw, "Absolute paths are not allowed"))
            continue

        # 2. Chống Path Traversal ở tầng ký tự (ngăn ".." component)
        # Sử dụng Path để phân tách các components
        parts = Path(trimmed).parts
        if ".." in parts or "." in parts:
            result.rejected_paths.append(
                (raw, "Path traversal components ('.' or '..') are not allowed")
            )
            continue

        # Chuẩn hóa separator thành '/'
        normalized_rel = trimmed.replace("\\", "/")

        # Tránh trùng lặp (case-insensitive deduplication)
        norm_key = normalized_rel.lower()
        if norm_key in seen_normalized:
            continue
        seen_normalized.add(norm_key)

        # 3. Resolve path đầy đủ
        try:
            candidate_path = (workspace_root / normalized_rel).resolve()
        except Exception:
            result.rejected_paths.append((raw, "Could not resolve path"))
            continue

        # 4. Kiểm tra Workspace Boundary
        if not is_relative_to(candidate_path, workspace_root):
            result.rejected_paths.append((raw, "Path escapes workspace boundary"))
            continue

        # 5. Loại trừ các thư mục hệ thống / cấu hình nội bộ
        # Không cho phép chọn files trong .git hoặc .synapse
        rel_parts = candidate_path.relative_to(workspace_root).parts
        if rel_parts and (rel_parts[0] == ".synapse" or rel_parts[0] == ".git"):
            result.rejected_paths.append((raw, "Internal system folders are excluded"))
            continue

        # 6. Kiểm tra xem file có thực sự tồn tại và là file thông thường (không phải thư mục)
        if not candidate_path.exists():
            result.rejected_paths.append((raw, "File does not exist"))
            continue

        if not candidate_path.is_file():
            result.rejected_paths.append((raw, "Path is not a regular file"))
            continue

        # 7. Check sensitive files / blocklist
        name_lower = candidate_path.name.lower()
        ext_lower = candidate_path.suffix.lower()

        # Kiểm tra trùng khớp filename nhạy cảm hoặc extension
        is_sensitive = False
        if name_lower in SENSITIVE_FILENAMES:
            is_sensitive = True
        elif ext_lower in SENSITIVE_EXTENSIONS:
            is_sensitive = True
        elif name_lower.startswith(".env"):  # block tất cả các biến thể .env.*
            is_sensitive = True

        if is_sensitive:
            result.sensitive_blocked.append(normalized_rel)
            result.rejected_paths.append(
                (raw, "Sensitive credential/config file blocked")
            )
            continue

        # 8. Check custom ignore patterns nếu có
        if ignore_patterns:
            # Logic này đơn giản, có thể mở rộng sau nếu cần match patterns phức tạp
            is_ignored = False
            for pat in ignore_patterns:
                if pat and (pat in normalized_rel or pat in candidate_path.name):
                    is_ignored = True
                    break
            if is_ignored:
                result.rejected_paths.append((raw, "Excluded by ignore patterns"))
                continue

        # Nếu hợp lệ hoàn toàn
        result.valid_paths.append(normalized_rel)

        # Giới hạn số lượng
        if len(result.valid_paths) >= max_results:
            break

    return result
