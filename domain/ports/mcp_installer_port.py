from abc import ABC, abstractmethod
from typing import Optional


class IMCPInstaller(ABC):
    """
    Interface cho MCP Config Installer Service.
    """

    @abstractmethod
    def get_mcp_targets(self) -> dict:
        """Lay danh sach cac target MCP va cau hinh cua chung."""
        pass

    @abstractmethod
    def check_installed(
        self, target_name: str, workspace_path: Optional[str] = None
    ) -> bool:
        """Kiem tra xem Synapse da duoc cai dat vao target chua."""
        pass

    @abstractmethod
    def get_mcp_command(self) -> list[str]:
        """Lay lenh khoi chay MCP server."""
        pass

    @abstractmethod
    def get_config_path(
        self, target_name: str, workspace_path: Optional[str] = None
    ) -> str:
        """Lay duong dan den file cau hinh cua target."""
        pass

    @abstractmethod
    def preview_json(
        self, target_name: str, workspace_path: Optional[str] = None
    ) -> str:
        """Xem truoc JSON cau hinh sau khi merge."""
        pass

    @abstractmethod
    def install_config(
        self, target_name: str, workspace_path: Optional[str] = None
    ) -> tuple[bool, str]:
        """Cai dat cau hinh MCP vao target."""
        pass
