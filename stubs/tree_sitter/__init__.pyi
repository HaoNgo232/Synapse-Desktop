"""Type stubs for tree_sitter package"""
from typing import Any

class Language:
    def __init__(self, ptr: Any) -> None: ...
    def query(self, source: str) -> Any: ...

class Query:
    def __init__(self, language: Language, source: str) -> None: ...

class QueryCursor:
    def __init__(self, query: Query) -> None: ...
    def captures(self, node: Any) -> dict[str, list[Any]]: ...

class Node:
    type: str
    start_point: tuple[int, int]
    end_point: tuple[int, int]
    text: bytes
    children: list[Node]

class Tree:
    root_node: Node

class Parser:
    def __init__(self, language: Language) -> None: ...
    def parse(self, source: bytes, old_tree: Tree | None = None) -> Tree: ...
