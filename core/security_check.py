"""
Security Check - Secret Scanning Module

Module sử dụng detect-secrets library (Yelp) để phát hiện các thông tin nhạy cảm
(API Keys, Private Keys) trong content trước khi copy, ngăn ngừa rò rỉ secrets cho LLM.

detect-secrets là thư viện chuyên nghiệp với 27+ plugins được kiểm chứng kỹ lưỡng,
giảm thiểu false positives so với custom regex.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from pathlib import Path
import tempfile

from detect_secrets import SecretsCollection
from detect_secrets.settings import default_settings
from core.utils.file_utils import is_binary_file


# ============================================
# SECURITY SCAN CACHE
# Cache based on mtime để tránh scan lại file không thay đổi
# ============================================
_security_scan_cache: Dict[str, Tuple[float, List["SecretMatch"]]] = {}
_MAX_CACHE_SIZE = 500


def invalidate_security_cache(path: str):
    """
    Xóa cache entry cho một file cụ thể.
    Gọi khi file watcher phát hiện file thay đổi.
    """
    _security_scan_cache.pop(path, None)


def clear_security_cache():
    """Xóa toàn bộ security scan cache."""
    _security_scan_cache.clear()


def get_security_cache_stats() -> Dict[str, int]:
    """Lấy thống kê cache (cho debugging)."""
    return {
        "size": len(_security_scan_cache),
        "max_size": _MAX_CACHE_SIZE,
    }


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
    Quét content để tìm các secrets tiềm ẩn sử dụng detect-secrets.

    Args:
        content: Nội dung text cần quét
        file_path: Optional path to file (for display purposes)

    Returns:
        List các SecretMatch được tìm thấy
    """
    matches: list[SecretMatch] = []

    if not content or not content.strip():
        return matches

    # Tạo temp file để scan (detect-secrets cần file path)
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            temp_path = f.name
    except (OSError, IOError):
        return matches

    try:
        # Scan với detect-secrets
        secrets = SecretsCollection()
        with default_settings():
            secrets.scan_file(temp_path)

        # Parse kết quả
        results = secrets.json()

        # Extract secrets từ results dict
        for detected_secret in results.get(temp_path, []):
            secret_type = detected_secret.get("type", "Unknown")
            line_num = detected_secret.get("line_number", 0)

            # Tạo redacted preview từ dòng tương ứng
            lines = content.split("\n")
            if 0 <= line_num - 1 < len(lines):
                line_content = lines[line_num - 1]
                # Tạo preview an toàn
                if len(line_content) > 50:
                    preview = line_content[:20] + "..." + line_content[-20:]
                else:
                    preview = (
                        line_content[:6] + "..." + line_content[-4:]
                        if len(line_content) > 10
                        else line_content
                    )
            else:
                preview = "[content unavailable]"

            matches.append(
                SecretMatch(
                    secret_type=secret_type,
                    line_number=line_num,
                    redacted_preview=preview,
                    file_path=file_path,
                )
            )
    except Exception:
        # Nếu có lỗi khi scan, bỏ qua
        pass
    finally:
        # Cleanup temp file
        try:
            Path(temp_path).unlink()
        except Exception:
            pass

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
    Quét secrets trong danh sách các file sử dụng detect-secrets.

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
            if is_binary_file(path):
                continue

            # Size check
            try:
                if path.stat().st_size > max_file_size:
                    continue
            except OSError:
                continue

            content = path.read_text(encoding="utf-8", errors="replace")
            # Lưu absolute path để có thể mở file từ preview
            file_matches = scan_for_secrets(content, file_path=path_str)
            all_matches.extend(file_matches)

        except (OSError, IOError):
            pass

    return all_matches


def scan_secrets_in_files_cached(
    file_paths: set[str], max_file_size: int = 1024 * 1024
) -> list[SecretMatch]:
    """
    Quét secrets với mtime-based cache.

    Chỉ scan lại file khi file thay đổi (mtime khác).
    Uses batch processing for better performance with many files.

    Args:
        file_paths: Set các đường dẫn file cần quét
        max_file_size: Limit size để tránh quét file quá lớn

    Returns:
        List các SecretMatch được tìm thấy
    """
    global _security_scan_cache

    all_matches: list[SecretMatch] = []
    files_to_scan: list[tuple[str, Path]] = []
    sorted_paths = sorted(file_paths)

    # Phase 1: Check cache and collect files to scan
    for path_str in sorted_paths:
        path = Path(path_str)
        try:
            if not path.is_file():
                continue
            if is_binary_file(path):
                continue

            try:
                stat = path.stat()
                if stat.st_size > max_file_size:
                    continue
                if stat.st_size == 0:
                    continue
                mtime = stat.st_mtime
            except OSError:
                continue

            # Check cache
            cached = _security_scan_cache.get(path_str)
            if cached is not None and cached[0] == mtime:
                all_matches.extend(cached[1])
                continue

            # Need to scan this file
            files_to_scan.append((path_str, path))

        except (OSError, IOError):
            pass

    # Phase 2: Batch scan uncached files
    if files_to_scan:
        # For small batches, scan sequentially
        if len(files_to_scan) <= 5:
            for path_str, path in files_to_scan:
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    file_matches = scan_for_secrets(content, file_path=path_str)
                    
                    mtime = path.stat().st_mtime
                    _security_scan_cache[path_str] = (mtime, file_matches)
                    all_matches.extend(file_matches)
                except (OSError, IOError):
                    pass
        else:
            # For larger batches, use ThreadPoolExecutor
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def scan_single_file(item: tuple[str, Path]) -> tuple[str, float, list[SecretMatch]]:
                path_str, path = item
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    file_matches = scan_for_secrets(content, file_path=path_str)
                    mtime = path.stat().st_mtime
                    return (path_str, mtime, file_matches)
                except Exception:
                    return (path_str, 0.0, [])
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(scan_single_file, item) for item in files_to_scan]
                
                for future in as_completed(futures):
                    try:
                        path_str, mtime, file_matches = future.result()
                        if mtime > 0:
                            _security_scan_cache[path_str] = (mtime, file_matches)
                        all_matches.extend(file_matches)
                    except Exception:
                        pass

    # Cleanup cache if too large (use LRU-style eviction)
    if len(_security_scan_cache) > _MAX_CACHE_SIZE:
        keys_to_remove = list(_security_scan_cache.keys())[: _MAX_CACHE_SIZE // 5]
        for key in keys_to_remove:
            del _security_scan_cache[key]

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
