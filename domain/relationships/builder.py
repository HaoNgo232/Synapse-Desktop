from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from tree_sitter import Parser  # type: ignore

from application.services.dependency_resolver import DependencyResolver
from domain.codemap.relationship_extractor import extract_relationships
from domain.codemap.symbol_extractor import extract_symbols
from domain.codemap.types import RelationshipKind, SymbolKind
from domain.relationships import Edge, EdgeKind, RelationshipGraph

"""
GraphBuilder - Xây dựng RelationshipGraph từ các nguồn dữ liệu hiện có.

Mục tiêu:
- Dùng lại DependencyResolver cho quan hệ IMPORTS giữa các file
- (Tương lai) kết hợp với CodeMap / relationship_extractor để bổ sung
  quan hệ CALLS, INHERITS ở mức file.

Lưu ý:
- Module này chỉ chịu trách nhiệm orchestrate build, không cache global.
- Lifecycle/caching sẽ được quản lý ở application layer (GraphService).
"""


class GraphBuilder:
    """
    Xây dựng RelationshipGraph cho một workspace.

    Hiện tại mới tập trung vào IMPORTS edges sử dụng DependencyResolver
    để đảm bảo backward-compatible và dễ verify. CALLS/INHERITS sẽ được
    bổ sung dần dựa trên CodeMap khi đã ổn định.
    """

    def __init__(self, workspace_root: Path) -> None:
        """
        Khởi tạo GraphBuilder cho một workspace.

        Args:
            workspace_root: Thư mục gốc của workspace
        """

        self._workspace_root = workspace_root.resolve()

    def build(
        self,
        file_paths: Iterable[str],
        existing_resolver: Optional[DependencyResolver] = None,
        max_codemap_files: int = 500,
        imports_max_depth: int = 2,
    ) -> RelationshipGraph:
        """
        Build RelationshipGraph đầy đủ cho danh sách file đầu vào.

        Gồm hai pha:
        1. IMPORTS edges bằng DependencyResolver (file-level)
        2. CALLS/INHERITS edges bằng CodeMap extractor (symbol-level → file-level)

        Args:
            file_paths: Danh sách đường dẫn file (string, nên là absolute)
            existing_resolver: Resolver đã build sẵn index (optional)
            max_codemap_files: Giới hạn số file cho CALLS/INHERITS extraction
            imports_max_depth: Độ sâu tối đa cho import traversal

        Returns:
            RelationshipGraph đã được build
        """

        graph = RelationshipGraph()

        # Chuẩn hóa danh sách file (loại bỏ file không tồn tại)
        normalized_files: list[Path] = []
        for path_str in file_paths:
            p = Path(path_str)
            if p.is_file():
                normalized_files.append(p)

        # ===== Phase 1: IMPORTS edges - Single Pass Batch Strategy =====
        #
        # Trước đây: gọi get_related_files_with_depth() PER FILE (1281 files)
        #   -> mỗi call đọc disk + parse tree-sitter + recurse depth=2
        #   -> cùng 1 file bị đọc & parse hàng chục lần -> ~30s
        #
        # Tối ưu: ĐỌC MỖI FILE ĐÚNG 1 LẦN, xây adjacency map in-memory,
        #   -> BFS trên adjacency map (pure dict lookup) -> ~2-3s
        resolver = existing_resolver or DependencyResolver(self._workspace_root)
        if existing_resolver is None:
            resolver.build_file_index_from_disk(self._workspace_root)

        # Bước 1: Single-pass extract imports -> adjacency map
        # adjacency[source_abs] = set of target_abs (direct imports only)
        adjacency: dict[str, set[str]] = {}
        for source_path in normalized_files:
            try:
                source_abs = str(source_path.resolve())
            except OSError:
                source_abs = str(source_path)

            # Chỉ gọi depth=1 để lấy direct imports (không recurse)
            direct_deps = resolver.get_related_files_with_depth(
                source_path, max_depth=1
            )
            targets: set[str] = set()
            for target_path, _depth in direct_deps.items():
                if not target_path.exists():
                    continue
                try:
                    target_abs = str(target_path.resolve())
                except OSError:
                    target_abs = str(target_path)
                if target_abs != source_abs:
                    targets.add(target_abs)
            adjacency[source_abs] = targets

        # Bước 2: Tạo edges từ adjacency map bằng BFS (in-memory, O(E))
        for source_abs, direct_targets in adjacency.items():
            for target_abs in direct_targets:
                graph.add_edge(
                    Edge(
                        source_file=source_abs,
                        target_file=target_abs,
                        kind=EdgeKind.IMPORTS,
                        metadata={"depth": 1},
                    )
                )

            # Transitive deps (depth 2..max) qua adjacency lookup thuần
            if imports_max_depth >= 2:
                for d1_target in direct_targets:
                    d2_targets = adjacency.get(d1_target, set())
                    for d2_target in d2_targets:
                        if d2_target != source_abs and d2_target not in direct_targets:
                            graph.add_edge(
                                Edge(
                                    source_file=source_abs,
                                    target_file=d2_target,
                                    kind=EdgeKind.IMPORTS,
                                    metadata={"depth": 2},
                                )
                            )

        # ===== Phase 2: CALLS / INHERITS edges qua CodeMap =====
        # Build symbol index: symbol_name -> file_path
        symbol_index: dict[str, str] = {}

        limited_files = normalized_files[:max_codemap_files]
        for file_path in limited_files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            symbols = extract_symbols(str(file_path), content)
            for sym in symbols:
                if sym.kind in (
                    SymbolKind.FUNCTION,
                    SymbolKind.METHOD,
                    SymbolKind.CLASS,
                ):
                    # Ưu tiên giữ mapping đầu tiên để tránh nhảy lung tung
                    symbol_index.setdefault(sym.name, str(file_path.resolve()))

        if not symbol_index:
            return graph

        # Chỉ xử lý các file đã có ít nhất một edge trong graph (connected files)
        connected_files = {
            Path(p) for p in graph.all_files() if Path(p).is_file()
        } & set(limited_files)

        for file_path in list(connected_files)[:max_codemap_files]:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            # Parse AST một lần và chia sẻ cho relationship extraction
            from domain.smart_context.loader import get_language

            ext = file_path.suffix.lstrip(".")  # Remove leading dot
            language = get_language(ext)
            if language is None:
                continue

            try:
                parser = Parser(language)
                tree = parser.parse(bytes(content, "utf-8"))
            except Exception:
                tree = None
                language = None

            relationships = extract_relationships(
                str(file_path),
                content,
                known_symbols=set(symbol_index.keys()),
                tree=tree,
                language=language,
            )

            try:
                source_abs = str(file_path.resolve())
            except OSError:
                source_abs = str(file_path)

            for rel in relationships:
                if rel.kind not in (RelationshipKind.CALLS, RelationshipKind.INHERITS):
                    continue

                target_file = symbol_index.get(rel.target)
                if not target_file:
                    continue

                if target_file == source_abs:
                    continue

                edge_kind = (
                    EdgeKind.CALLS
                    if rel.kind == RelationshipKind.CALLS
                    else EdgeKind.INHERITS
                )
                edge = Edge(
                    source_file=source_abs,
                    target_file=target_file,
                    kind=edge_kind,
                    metadata={"symbol": rel.target, "line": rel.source_line},
                )
                graph.add_edge(edge)

        return graph
