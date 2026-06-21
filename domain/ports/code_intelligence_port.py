import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from domain.codemap.types import Symbol, Relationship

@dataclass
class ParsedCodeInfo:
    """Unified structural information of a source file."""
    file_path: Path
    language: str
    symbols: List["Symbol"] = field(default_factory=list)
    relationships: List["Relationship"] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    outline: List[str] = field(default_factory=list)

class ICodeIntelligencePort(abc.ABC):
    """Port interface for all code parsing, outline mapping, and dependency checks."""

    @abc.abstractmethod
    def parse_file(self, file_path: Path, content: str) -> ParsedCodeInfo:
        """Parses a file and returns structural info DTO using the best available backend."""
        pass

    @abc.abstractmethod
    def generate_repo_map(
        self,
        file_paths: List[str],
        workspace_root: Optional[Path] = None,
        max_files: int = 500,
    ) -> str:
        """Generates a compressed repository signatures map for LLM context."""
        pass
