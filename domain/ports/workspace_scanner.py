import abc
from pathlib import Path
from typing import List


class IWorkspaceScanner(abc.ABC):
    """
    Interface cho workspace scanning.

    Cho phep Domain layer scan repository files ma khong
    can import truc tiep tu application layer.
    """

    @abc.abstractmethod
    def collect_files(self, folder: Path) -> List[str]:
        """
        Scan folder va tra ve danh sach các paths hop le.

        Args:
            folder: Thu muc can scan

        Returns:
            List các absolute paths duoi dang string
        """
        pass
