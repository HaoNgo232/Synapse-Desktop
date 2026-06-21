import logging
from pathlib import Path
from typing import List, Optional
from domain.ports.code_intelligence_port import ICodeIntelligencePort, ParsedCodeInfo
from infrastructure.adapters.code_intelligence.base_backend import CodeIntelligenceBackend

logger = logging.getLogger(__name__)

class CodeIntelligenceRouterAdapter(ICodeIntelligencePort):
    """Routes parsing requests to appropriate backends and generates repository maps."""

    def __init__(self, backends: List[CodeIntelligenceBackend]):
        self.backends = backends

    def parse_file(self, file_path: Path, content: str) -> ParsedCodeInfo:
        ext = file_path.suffix.lstrip(".").lower()
        for backend in self.backends:
            if ext in backend.get_supported_extensions():
                try:
                    result = backend.parse_file(file_path, content)
                    if result is not None:
                        return result
                except Exception as e:
                    logger.debug(f"Backend {backend.__class__.__name__} failed for {file_path}: {e}")

        # Default fallback DTO
        return ParsedCodeInfo(
            file_path=file_path,
            language=ext,
            symbols=[],
            relationships=[],
            imports=[],
            outline=[]
        )

    def generate_repo_map(
        self,
        file_paths: List[str],
        workspace_root: Optional[Path] = None,
        max_files: int = 500,
    ) -> str:
        lines = []
        parsed_count = 0
        for path_str in sorted(file_paths):
            if parsed_count >= max_files:
                lines.append(f"\n... and {len(file_paths) - max_files} more files")
                break
            path = Path(path_str)
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            info = self.parse_file(path, content)
            if not info.outline:
                continue

            if workspace_root:
                try:
                    display_path = path.relative_to(workspace_root)
                except ValueError:
                    display_path = path
            else:
                display_path = path

            # Standardize paths to use forward slashes for cross-platform/Aider compatibility
            display_path_str = str(display_path).replace("\\", "/")
            lines.append(f"{display_path_str}:")
            for item in info.outline:
                lines.append(f"  {item}")
            lines.append("")
            parsed_count += 1

        return "\n".join(lines)
