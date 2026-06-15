import abc
from pathlib import Path
from typing import Dict, Any

class IAstParser(abc.ABC):
    @abc.abstractmethod
    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """Parse file source code va tra ve thong tin AST (symbols, imports, classes, functions, v.v.)."""
        pass
