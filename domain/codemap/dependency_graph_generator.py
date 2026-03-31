import os
from pathlib import Path
from typing import Dict, List, Optional
from application.services.dependency_resolver import DependencyResolver


class DependencyGraphGenerator:
    """
    Generator tạo ra Project Dependency Graph (Phần 1 của Hybrid Compressed Context).
    Thể hiện quan hệ giữa các file trong project dưới dạng flat list.
    """

    def __init__(
        self, workspace_root: Path, resolver: Optional[DependencyResolver] = None
    ):
        """
        Khởi tạo DependencyGraphGenerator.

        Args:
            workspace_root: Root path của workspace
            resolver: Optional DependencyResolver đã build sẵn index
        """
        self.workspace_root = workspace_root
        if resolver:
            self.resolver = resolver
        else:
            self.resolver = DependencyResolver(workspace_root)
            self.resolver.build_file_index_from_disk(workspace_root)

    def generate_graph(self, file_contents: Dict[str, str]) -> str:
        """
        Tạo nội dung Dependency Graph cho danh sách các files.

        Args:
            file_contents: Dict mapping absolute_path -> content

        Returns:
            String định dạng theo spec:
            # Dependency Graph
            src/a.py
              \u2192 src/b.py
        """
        # 1. Trích xuất relationships cho từng file
        file_dependencies: Dict[str, List[str]] = {}

        for file_path, content in file_contents.items():
            # Sử dụng DependencyResolver để lấy các files được import
            # resolver.get_related_files() trả về Set[Path] đã được resolve thành absolute path
            path_obj = Path(file_path)
            related_files = self.resolver.get_related_files(path_obj)

            internal_imports = set()
            for dep_path in related_files:
                # resolver đã lọc mostly internal, nhưng ta check lại cho chắc
                if str(dep_path).startswith(str(self.workspace_root)):
                    internal_imports.add(self._to_relative(str(dep_path)))

            if internal_imports:
                rel_source = self._to_relative(file_path)
                file_dependencies[rel_source] = sorted(list(internal_imports))

        if not file_dependencies:
            return ""

        # 2. Format output
        lines = ["# Dependency Graph", ""]

        # Sắp xếp các file theo đường dẫn để output ổn định
        sorted_files = sorted(file_dependencies.keys())

        for source_file in sorted_files:
            lines.append(source_file)
            for dep in file_dependencies[source_file]:
                lines.append(f"  \u2192 {dep}")
            lines.append("")  # Khoảng trống giữa các block

        return "\n".join(lines).strip()

    def _normalize_path(self, path_str: str) -> str:
        """Chuẩn hóa đường dẫn (dùng forward slash, handle absolute/relative)."""
        # Nếu đã là absolute hoặc có vẻ là path
        if (
            os.path.isabs(path_str)
            or "./" in path_str
            or "../" in path_str
            or "/" in path_str
            or "\\" in path_str
        ):
            return path_str
        return path_str  # Giữ nguyên nếu là module name (e.g. 'os')

    def _is_internal(self, target: str) -> bool:
        """Kiểm tra dependency có phải nội bộ project không."""
        # target có thể là absolute path hoặc relative từ somewhere
        try:
            path = Path(target)
            if not path.is_absolute():
                # Nếu không absolute, ta không chắc chắn trừ khi nó tồn tại tương đối với workspace
                # Tuy nhiên RelationshipExtractor thường resolve thành absolute cho internal files
                return False

            return str(path).startswith(str(self.workspace_root))
        except Exception:
            return False

    def _to_relative(self, path_str: str) -> str:
        """Chuyển path thành relative từ workspace root và dùng forward slash."""
        try:
            path = Path(path_str)
            if path.is_absolute():
                rel_path = path.relative_to(self.workspace_root)
                return str(rel_path).replace("\\", "/")
            return path_str.replace("\\", "/")
        except Exception:
            return path_str.replace("\\", "/")
