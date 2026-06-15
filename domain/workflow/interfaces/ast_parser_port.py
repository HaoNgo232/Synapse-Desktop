import abc
from pathlib import Path
from typing import Dict, Any, List, Optional


class IAstParser(abc.ABC):
    @abc.abstractmethod
    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """Parse file source code va tra ve thong tin AST (symbols, imports, classes, functions, v.v.)."""
        pass

    @abc.abstractmethod
    def generate_repo_map(
        self,
        file_paths: List[str],
        workspace_root: Optional[Path] = None,
        max_files: int = 500,
    ) -> str:
        """Tao Repo Map tu danh sach file paths."""
        pass
