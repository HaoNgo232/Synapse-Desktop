"""
CodeMaps Types - Dataclasses cho symbols và relationships

Định nghĩa các types cơ bản cho CodeMaps feature.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SymbolKind(Enum):
    """Loại symbol trong code."""

    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    IMPORT = "import"


class RelationshipKind(Enum):
    """Loại relationship giữa symbols."""

    CALLS = "calls"  # function A gọi function B
    IMPORTS = "imports"  # file A import file B
    INHERITS = "inherits"  # class A kế thừa class B
    IMPLEMENTS = "implements"  # class A implement interface B
    USES = "uses"  # function A sử dụng class B


@dataclass
class Symbol:
    """
    Đại diện cho một symbol trong code (class, function, method, etc.).

    Attributes:
        name: Tên symbol
        kind: Loại symbol (class, function, etc.)
        file_path: Đường dẫn file chứa symbol
        line_start: Dòng bắt đầu
        line_end: Dòng kết thúc
        signature: Signature của symbol (optional)
        parent: Tên parent symbol (e.g., class chứa method)
    """

    name: str
    kind: SymbolKind
    file_path: str
    line_start: int
    line_end: int
    signature: Optional[str] = None
    parent: Optional[str] = None

    def __hash__(self) -> int:
        """Hash based on unique identifier."""
        return hash((self.name, self.kind, self.file_path, self.line_start))

    def __eq__(self, other: object) -> bool:
        """Equality based on unique identifier."""
        if not isinstance(other, Symbol):
            return False
        return (
            self.name == other.name
            and self.kind == other.kind
            and self.file_path == other.file_path
            and self.line_start == other.line_start
        )


@dataclass
class Relationship:
    """
    Đại diện cho một relationship giữa symbols.

    Attributes:
        source: Tên symbol nguồn hoặc file path
        target: Tên symbol đích hoặc file path
        kind: Loại relationship
        source_line: Dòng nơi relationship được định nghĩa
    """

    source: str
    target: str
    kind: RelationshipKind
    source_line: int

    def __hash__(self) -> int:
        """Hash based on unique identifier."""
        return hash((self.source, self.target, self.kind, self.source_line))

    def __eq__(self, other: object) -> bool:
        """Equality based on unique identifier."""
        if not isinstance(other, Relationship):
            return False
        return (
            self.source == other.source
            and self.target == other.target
            and self.kind == other.kind
            and self.source_line == other.source_line
        )


@dataclass
class CodeMap:
    """
    CodeMap cho một file - chứa symbols và relationships.

    Attributes:
        file_path: Đường dẫn file
        symbols: List các symbols trong file
        relationships: List các relationships
    """

    file_path: str
    symbols: list[Symbol] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)

    def get_symbol_by_name(self, name: str) -> Optional[Symbol]:
        """Tìm symbol theo tên."""
        for symbol in self.symbols:
            if symbol.name == name:
                return symbol
        return None

    def get_relationships_by_source(self, source: str) -> list[Relationship]:
        """Lấy tất cả relationships từ source."""
        return [r for r in self.relationships if r.source == source]

    def get_relationships_by_target(self, target: str) -> list[Relationship]:
        """Lấy tất cả relationships đến target."""
        return [r for r in self.relationships if r.target == target]
