from abc import ABC, abstractmethod


class IAppLifecycleService(ABC):
    """
    Interface quản lý vòng đời ứng dụng và dọn dẹp tài nguyên threads/scans.
    """

    @abstractmethod
    def set_active_view(self, view_id: str) -> None:
        """Thiết lập view ID đang active hiện tại."""
        pass

    @abstractmethod
    def get_active_view(self) -> str:
        """Lấy view ID đang active hiện tại."""
        pass

    @abstractmethod
    def is_view_active(self, view_id: str) -> bool:
        """Kiểm tra view ID có đang active không."""
        pass

    @abstractmethod
    def is_app_stopping(self) -> bool:
        """Kiểm tra xem ứng dụng có đang tắt không."""
        pass

    @abstractmethod
    def shutdown_all(self) -> None:
        """Dừng tất cả các threads/tasks khi đóng ứng dụng."""
        pass

    @abstractmethod
    def stop_scanning(self) -> None:
        """Dừng tiến trình quét thư mục (file scanner)."""
        pass

    @abstractmethod
    def stop_token_counting(self) -> None:
        """Dừng tiến trình đếm token."""
        pass
