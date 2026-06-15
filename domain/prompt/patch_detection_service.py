import os
from dataclasses import dataclass, field
from typing import List, Optional, Set
from domain.prompt.opx_parser import (
    FileAction,
    parse_any_response,
    _looks_like_opx,
    _looks_like_search_replace,
)


@dataclass
class PatchDetectionResult:
    """Kết quả phân tích nhận dạng patch từ AI response.

    Attributes:
        has_patches (bool): True nếu có ít nhất một file action hợp lệ được phân tích thành công.
        file_actions (List[FileAction]): Danh sách các file action được phân tích từ opx_parser.
        parse_errors (List[str]): Danh sách các lỗi cú pháp xảy ra khi cố gắng parse patch.
        affected_files (List[str]): Danh sách các đường dẫn tương đối, độc nhất của các file bị ảnh hưởng.
    """

    has_patches: bool
    file_actions: List[FileAction] = field(default_factory=list)
    parse_errors: List[str] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)


class PatchDetectionService:
    """Service phát hiện và trích xuất thông tin patch từ AI response text."""

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        """Khởi tạo service với thư mục gốc workspace tùy chọn.

        Args:
            workspace_root (Optional[str]): Thư mục gốc của workspace dùng để tính toán relative path.
        """
        self.workspace_root = workspace_root

    def detect(self, raw_text: str) -> PatchDetectionResult:
        """Phát hiện và parse các patch từ text thô của AI response.

        Hàm này sử dụng trực tiếp logic của opx_parser để nhận dạng và phân tích
        cú pháp định dạng OPX hoặc Search/Replace.

        Args:
            raw_text (str): Phản hồi thô từ AI.

        Returns:
            PatchDetectionResult: Kết quả phân tích chứa thông tin patch và lỗi cú pháp nếu có.
        """
        # 1. Guard clauses cho đầu vào trống hoặc None-like
        if raw_text is None:
            return PatchDetectionResult(has_patches=False)

        if not isinstance(raw_text, str):
            return PatchDetectionResult(has_patches=False)

        cleaned = raw_text.strip()
        if not cleaned or cleaned.lower() in ("none", "null"):
            return PatchDetectionResult(has_patches=False)

        # 2. Kiểm tra xem text có chứa cấu trúc patch hay không (tránh coi chat thường là lỗi parse)
        is_opx = _looks_like_opx(cleaned)
        is_sr = _looks_like_search_replace(cleaned)

        if not is_opx and not is_sr:
            # Hội thoại thông thường, không có ý định patch -> trả về kết quả trống, không có lỗi
            return PatchDetectionResult(has_patches=False)

        # 3. Phân tích cú pháp bằng opx_parser
        parse_result = parse_any_response(cleaned)

        file_actions = parse_result.file_actions
        has_patches = len(file_actions) > 0
        parse_errors = parse_result.errors

        # 4. Trích xuất affected_files (relative path, unique, giữ nguyên thứ tự)
        affected_files: List[str] = []
        seen_paths: Set[str] = set()

        for action in file_actions:
            path = action.path

            # Chuẩn hóa path thành relative path nếu là absolute path
            if os.path.isabs(path):
                root = self.workspace_root or os.getcwd()
                try:
                    rel_path = os.path.relpath(path, root)
                except Exception:
                    rel_path = path
            else:
                rel_path = path

            # Lọc trùng lặp nhưng giữ nguyên thứ tự xuất hiện gốc
            if rel_path not in seen_paths:
                seen_paths.add(rel_path)
                affected_files.append(rel_path)

        return PatchDetectionResult(
            has_patches=has_patches,
            file_actions=file_actions,
            parse_errors=parse_errors,
            affected_files=affected_files,
        )
