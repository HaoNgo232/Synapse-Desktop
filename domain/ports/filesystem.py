from abc import ABC, abstractmethod
from pathlib import Path
from typing import List


class IFileSystem(ABC):
    """
    Interface cho các thao tác với hệ thống tập tin.
    Được Domain layer và Application layer sử dụng để không phụ thuộc vào `os` hay `pathlib` trực tiếp.
    """

    @abstractmethod
    def read_text(self, path: Path) -> str:
        """Đọc toàn bộ nội dung văn bản từ một tập tin."""
        pass

    @abstractmethod
    def write_text(self, path: Path, content: str) -> None:
        """Ghi nội dung văn bản vào tập tin."""
        pass

    @abstractmethod
    def exists(self, path: Path) -> bool:
        """Kiểm tra xem tập tin hoặc thư mục có tồn tại không."""
        pass

    @abstractmethod
    def is_file(self, path: Path) -> bool:
        """Kiểm tra đường dẫn có phải là tập tin không."""
        pass

    @abstractmethod
    def is_dir(self, path: Path) -> bool:
        """Kiểm tra đường dẫn có phải là thư mục không."""
        pass

    @abstractmethod
    def list_dir(self, path: Path) -> List[Path]:
        """Liệt kê các tập tin và thư mục con trong một thư mục."""
        pass

    @abstractmethod
    def make_dir(self, path: Path, exist_ok: bool = True) -> None:
        """Tạo một thư mục mới."""
        pass

    @abstractmethod
    def remove(self, path: Path) -> None:
        """Xóa một tập tin."""
        pass

    @abstractmethod
    def get_mtime(self, path: Path) -> float:
        """Lấy thời gian sửa đổi cuối cùng của tập tin/thư mục."""
        pass
