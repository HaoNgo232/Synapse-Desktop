from typing import List, Optional
import abc
from pathlib import Path
from domain.smart_context.tree_item import TreeItem
from domain.ports.ignore_engine_port import IIgnoreEngine


class IDirectoryScanner(abc.ABC):
    """
    Interface cho directory scanning o Domain layer.
    """

    @abc.abstractmethod
    def scan_directory(
        self,
        root_path: Path,
        excluded_patterns: Optional[List[str]] = None,
        use_gitignore: bool = True,
    ) -> TreeItem:
        """Scan a directory recursively and build its TreeItem structure, respecting ignore rules."""
        pass

    @abc.abstractmethod
    def scan_directory_shallow(
        self,
        root_path: Path,
        ignore_engine: IIgnoreEngine,
        depth: int = 1,
        excluded_patterns: Optional[List[str]] = None,
    ) -> TreeItem:
        """Scan a directory shallowly up to a specified depth, respecting ignore rules."""
        pass

    @abc.abstractmethod
    def load_folder_children(
        self,
        node: TreeItem,
        ignore_engine: IIgnoreEngine,
        excluded_patterns: Optional[List[str]] = None,
        use_gitignore: bool = True,
        workspace_root: Optional[Path] = None,
    ) -> None:
        """Load children for a folder node on-demand, respecting ignore rules."""
        pass
