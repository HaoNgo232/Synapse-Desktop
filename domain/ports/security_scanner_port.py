from dataclasses import dataclass
from typing import Optional, List, Set, Protocol, runtime_checkable


@dataclass
class SecretMatch:
    secret_type: str
    line_number: int
    redacted_preview: str
    file_path: Optional[str] = None


@runtime_checkable
class ISecurityScanner(Protocol):
    def scan_secrets_in_files_cached(
        self, file_paths: Set[str], max_file_size: int = 1024 * 1024
    ) -> List[SecretMatch]: ...

    def format_security_warning(self, matches: List[SecretMatch]) -> str: ...
