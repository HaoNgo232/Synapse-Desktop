import abc
from pathlib import Path
from typing import Optional, List
from domain.ports.code_intelligence_port import ParsedCodeInfo

class CodeIntelligenceBackend(abc.ABC):
    """Abstract base class for all concrete parsing engines."""

    @abc.abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """Returns file extensions (without dots) supported by this backend."""
        pass

    @abc.abstractmethod
    def parse_file(self, file_path: Path, content: str) -> Optional[ParsedCodeInfo]:
        """Parses the file content. Returns ParsedCodeInfo or None if parsing fails."""
        pass
