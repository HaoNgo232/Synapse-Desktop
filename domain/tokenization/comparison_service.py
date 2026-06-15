"""
Token comparison service.

Module này cung cấp service thuần Python để so sánh Full Context,
Smart Context và Tree Map cho các file đang được chọn.
"""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable, Optional

from domain.prompt.generator import generate_file_map
from domain.smart_context.parser import smart_parse
from domain.tokenization.counter import count_tokens
from domain.smart_context.tree_item import TreeItem
from shared.utils.file_utils import is_binary_file


@dataclass(frozen=True)
class TokenComparison:
    """
    Kết quả so sánh token cho một selection.

    Attributes:
        full_tokens: Token khi dùng full file content.
        smart_tokens: Token khi dùng Smart Context, fallback bằng Full khi không parse được.
        tree_map_tokens: Token của file tree map.
        savings_pct: Phần trăm tiết kiệm, làm tròn 1 chữ số thập phân.
    """

    full_tokens: int
    smart_tokens: int
    tree_map_tokens: int
    savings_pct: float


class TokenComparisonService:
    """
    Service thuần Python để tính token comparison cho selection.

    Lớp này bọc public function hiện có để UI có thể inject dependency thay vì
    gọi trực tiếp module-level function.
    """

    def compare_paths(self, file_paths: list[str]) -> TokenComparison:
        """
        Tính token comparison cho danh sách file paths.

        Args:
            file_paths: Danh sách absolute path của các file đang chọn.

        Returns:
            TokenComparison đã tính Full, Smart, Tree Map và savings.
        """
        return compare_token_counts(file_paths)


def compare_token_counts(file_paths: list[str]) -> TokenComparison:
    """
    Tính bộ so sánh token cho danh sách file đã chọn.

    Service không giữ state nên có thể gọi đồng thời từ nhiều thread.

    Args:
        file_paths: Danh sách absolute path của các file đang được chọn.

    Returns:
        TokenComparison chứa full, smart, tree map và phần trăm tiết kiệm.
    """
    paths = _normalize_existing_files(file_paths)
    if not paths:
        return TokenComparison(
            full_tokens=0,
            smart_tokens=0,
            tree_map_tokens=0,
            savings_pct=0.0,
        )

    full_tokens = 0
    smart_tokens = 0

    for path in paths:
        content = _read_text_file(path)
        if content is None:
            continue

        full_count = count_tokens(content)
        full_tokens += full_count
        smart_tokens += _count_smart_tokens(path, content, full_count)

    tree_map_tokens = _count_tree_map_tokens(paths)
    return TokenComparison(
        full_tokens=full_tokens,
        smart_tokens=smart_tokens,
        tree_map_tokens=tree_map_tokens,
        savings_pct=_calculate_savings_pct(full_tokens, smart_tokens),
    )


def _normalize_existing_files(file_paths: Iterable[str]) -> list[Path]:
    """Chuẩn hóa path và chỉ giữ regular file đang tồn tại."""
    paths: list[Path] = []
    seen: set[Path] = set()
    for raw_path in file_paths:
        try:
            path = Path(raw_path).resolve()
        except (OSError, RuntimeError):
            continue

        if path in seen or not path.exists() or not path.is_file():
            continue
        seen.add(path)
        paths.append(path)
    return paths


def _read_text_file(path: Path) -> Optional[str]:
    """Đọc file text; binary hoặc file lỗi I/O trả về None để skip an toàn."""
    try:
        if is_binary_file(path):
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return None


def _count_smart_tokens(path: Path, content: str, full_count: int) -> int:
    """
    Đếm Smart Context tokens với fallback bằng Full khi parser không hỗ trợ/lỗi.

    Kết quả được clamp để đảm bảo Smart không vượt Full trong mọi input hợp lệ.
    """
    try:
        smart_content = smart_parse(str(path), content)
    except Exception:
        smart_content = None

    if not smart_content:
        return full_count

    smart_count = count_tokens(smart_content)
    return min(smart_count, full_count)


def _count_tree_map_tokens(paths: list[Path]) -> int:
    """Sinh tree map bằng generator hiện có rồi đếm token output."""
    tree = _build_tree(paths)
    if tree is None:
        return 0

    selected_paths = {str(path) for path in paths}
    tree_map = generate_file_map(
        tree,
        selected_paths,
        workspace_root=Path(tree.path),
        use_relative_paths=True,
    )
    return count_tokens(tree_map)


def _build_tree(paths: list[Path]) -> Optional[TreeItem]:
    """Build TreeItem tối thiểu từ selection để tái sử dụng generate_file_map()."""
    if not paths:
        return None

    workspace_root = _common_parent(paths)
    root = TreeItem(
        label=workspace_root.name or str(workspace_root),
        path=str(workspace_root),
        is_dir=True,
    )

    for path in sorted(paths):
        _insert_path(root, workspace_root, path)

    return root


def _common_parent(paths: list[Path]) -> Path:
    """Tìm thư mục cha chung của các file trong selection."""
    parents = [path.parent for path in paths]
    try:
        return Path(os.path.commonpath([str(parent) for parent in parents]))
    except ValueError:
        return parents[0]


def _insert_path(root: TreeItem, workspace_root: Path, file_path: Path) -> None:
    """Chèn một file path vào TreeItem root theo cấu trúc thư mục."""
    try:
        relative_parts = file_path.relative_to(workspace_root).parts
    except ValueError:
        relative_parts = (file_path.name,)

    current = root
    current_path = workspace_root
    for part in relative_parts[:-1]:
        current_path = current_path / part
        child = _find_child(current, str(current_path))
        if child is None:
            child = TreeItem(label=part, path=str(current_path), is_dir=True)
            current.children.append(child)
        current = child

    current.children.append(
        TreeItem(label=relative_parts[-1], path=str(file_path), is_dir=False)
    )


def _find_child(item: TreeItem, path: str) -> Optional[TreeItem]:
    """Tìm child theo absolute path trong danh sách con trực tiếp."""
    for child in item.children:
        if child.path == path:
            return child
    return None


def _calculate_savings_pct(full_tokens: int, smart_tokens: int) -> float:
    """Tính phần trăm tiết kiệm và làm tròn 1 chữ số thập phân."""
    if full_tokens <= 0:
        return 0.0
    return round(((full_tokens - smart_tokens) / full_tokens) * 100, 1)
