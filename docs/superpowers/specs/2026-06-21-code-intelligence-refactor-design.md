# Design Spec: Code Intelligence Port Refactoring

## 1. Objective & Context
Currently, the source code parsing, symbol extraction, and relationship tracing logic in Synapse Desktop are fragmented across multiple components:
- `domain/smart_context/parser.py` (inline tree-sitter calls, violating Clean Architecture/Onion Architecture)
- `domain/codemap/symbol_extractor.py` (tree-sitter query extraction)
- `domain/codemap/relationship_extractor.py` (tree-sitter relationship extraction)
- `infrastructure/adapters/ast_parser.py` (implements legacy `IAstParser` via python standard `ast` module and regex heuristics)
- `shared/utils/import_parser.py` (regex-based import extractor)

This refactoring aims to resolve this fragmentation and establish a extensible foundation for future code-parsing backends (such as Universal Ctags or SCIP) by:
1. Standardizing a single port interface: `ICodeIntelligencePort`.
2. Defining a unified Rich DTO: `ParsedCodeInfo` that returns symbols, relationships, raw imports, and outline signatures in a consistent format.
3. Implementing a Router Adapter (`CodeIntelligenceRouterAdapter`) that manages multiple backends in priority order and handles automatic fallback.
4. Keeping the core domain decoupled from the concrete parsing implementations (e.g., Tree-sitter, regex).

## 2. Target File Structure & Layout
The new and modified files will be structured as follows:

```text
domain/
  ports/
    code_intelligence_port.py    <-- [New] Port & DTO definition
    registry.py                  <-- [Modified] Register Code Intelligence Port, remove IAstParser
  codemap/
    types.py                     <-- [Unchanged] Symbol, Relationship definitions

infrastructure/
  adapters/
    code_intelligence/           <-- [New Directory]
      __init__.py
      base_backend.py            <-- [New] Base backend class
      router_adapter.py          <-- [New] Port implementation & routing logic
      tree_sitter_backend.py     <-- [New] Concrete Tree-sitter adapter
      python_ast_backend.py      <-- [New] Concrete Python standard ast adapter
      regex_fallback_backend.py   <-- [New] Concrete Regex heuristics adapter
```

## 3. Interfaces & DTO Specifications

### 3.1 Port and DTO: `domain/ports/code_intelligence_port.py`
```python
import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from domain.codemap.types import Symbol, Relationship

@dataclass
class ParsedCodeInfo:
    """Unified structural information of a source file."""
    file_path: Path
    language: str
    symbols: List[Symbol] = field(default_factory=list)
    relationships: List[Relationship] = field(default_factory=list)
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
```

### 3.2 Base Backend: `infrastructure/adapters/code_intelligence/base_backend.py`
```python
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
```

### 3.3 Router Adapter: `infrastructure/adapters/code_intelligence/router_adapter.py`
```python
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

            lines.append(f"{display_path}:")
            for item in info.outline:
                lines.append(f"  {item}")
            lines.append("")
            parsed_count += 1

        return "\n".join(lines)
```

## 4. Backends Porting Details

1. **`TreeSitterBackend`**:
   - Integrates existing Tree-sitter query extraction from `domain/codemap/symbol_extractor.py`, `relationship_extractor.py`, and `smart_context/parser.py`.
   - Returns a `ParsedCodeInfo` where:
     - `symbols` are extracted using the compiled SCM Queries.
     - `relationships` are extracted using `relationship_extractor.py`.
     - `imports` are extracted by walking the Tree-sitter nodes (multi-line import extraction).
     - `outline` is formatted from the extracted symbols.

2. **`PythonAstBackend`**:
   - Focuses only on python files (`.py`, `.pyw`) using Python's standard `ast` library.
   - Ports signature formatting and outline generation from `_extract_python_outline` in the legacy `ast_parser.py`.

3. **`RegexFallbackBackend`**:
   - Fallback engine for non-Python languages using the pre-defined regular expressions in `_extract_regex_outline`.
   - Populates the `outline` field and basic imports list based on regex patterns.

## 5. Migration Strategy

1. **Remove `IAstParser`**:
   - Delete `domain/ports/ast_parser_port.py`.
   - Delete `infrastructure/adapters/ast_parser.py`.
   - Clean up corresponding import statements and registry bindings.
2. **Registry and Container Registration**:
   - Update `DomainRegistry` in `domain/ports/registry.py` to register/unregister `ICodeIntelligencePort`.
   - Instantiate and register the new `CodeIntelligenceRouterAdapter` in `presentation/service_container.py`.
3. **Decouple Smart Parse**:
   - Update `smart_parse` in `domain/smart_context/parser.py` to get code structures entirely via `DomainRegistry.code_intelligence().parse_file(Path(file_path), content)`.
4. **Update Unit Tests**:
   - Adjust mock registers in `tests/conftest.py` and `tests/domain/test_registry.py` to match the new Port interface.

## 6. Verification and Diagnostics
To verify correctness, run:
- `pytest tests/domain/smart_context/test_parser_hybrid.py`
- `pytest tests/domain/test_registry.py`
- `pytest tests/ -v`
All existing parsing and prompt tests must pass successfully.
