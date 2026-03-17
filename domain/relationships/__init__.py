"""
Public API cho domain.relationships.

Module này gom các types, graph core và port interface
để các layer khác có thể import một cách rõ ràng, dùng absolute import.
"""

from domain.relationships.types import Edge, EdgeKind, FileNode
from domain.relationships.graph import RelationshipGraph
from domain.relationships.port import IRelationshipGraphProvider

__all__ = [
    "Edge",
    "EdgeKind",
    "FileNode",
    "RelationshipGraph",
    "IRelationshipGraphProvider",
]
