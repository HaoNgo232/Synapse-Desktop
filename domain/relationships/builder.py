from __future__ import annotations
import os
import concurrent.futures
import time
import hashlib
from pathlib import Path
from typing import Iterable, Optional, Dict, Set, List, Any
from dataclasses import dataclass

from tree_sitter import Parser  # type: ignore

from application.services.dependency_resolver import DependencyResolver
from domain.codemap.relationship_extractor import extract_relationships
from domain.codemap.symbol_extractor import extract_symbols
from domain.codemap.types import RelationshipKind, SymbolKind
from domain.relationships import Edge, EdgeKind, RelationshipGraph
from domain.smart_context.loader import get_language


@dataclass
class FileProcessingResult:
    """Kết quả thu được sau khi parse một file duy nhất (Unified Pass)."""

    source_abs: str
    direct_imports: set[str]
    symbols: list[tuple[str, str]]  # list of (symbol_name, file_abs)
    relationships: List[Any]  # list of Relationship objects
    tree_info: Optional[tuple[str, tuple[float, Any, str, set[str]]]] = (
        None  # (path, (mtime, tree, hash, targets))
    )


class GraphBuilder:
    """
    Xây dựng RelationshipGraph tối ưu hóa cho tốc độ xử lý (Parallel + Single-pass).
    """

    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root.resolve()

    def build(
        self,
        file_paths: Iterable[str],
        existing_resolver: Optional[DependencyResolver] = None,
        max_codemap_files: int = 500,
        imports_max_depth: int = 2,
        tree_cache: Optional[dict[str, tuple[float, Any, str, set[str]]]] = None,
    ) -> RelationshipGraph:
        """
        Build RelationshipGraph sử dụng chiến lược Unified Parallel Pass.
        """
        graph = RelationshipGraph()

        # 1. Chuẩn hóa & lọc danh sách file
        normalized_files: list[Path] = []
        for path_str in file_paths:
            p = Path(path_str)
            if p.is_file():
                normalized_files.append(p)

        if not normalized_files:
            return graph

        from shared.logging_config import log_info

        # Performance counters
        stats = {
            "total_files": len(normalized_files),
            "codemap_files": 0,
            "tree_cache_hits": 0,
            "tree_cache_misses": 0,
            "start_time": time.perf_counter(),
        }

        # 2. Chuẩn bị Resolver (Cần thiết để resolve import names)
        resolver = existing_resolver or DependencyResolver(self._workspace_root)
        if existing_resolver is None:
            resolver.build_file_index_from_disk(self._workspace_root)

        # 3. UNIFIED PASS: Parallel processing
        results: List[FileProcessingResult] = []
        max_workers = min(os.cpu_count() or 4, 8)

        # Chỉ xử lý CodeMap cho một lượng giới hạn files (để tránh quá tải)
        code_map_files_set = {
            str(p.resolve()) for p in normalized_files[:max_codemap_files]
        }

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(
                    self._process_file,
                    p,
                    resolver,
                    str(p.resolve()) in code_map_files_set,
                    tree_cache.get(str(p.resolve())) if tree_cache else None,
                ): p
                for p in normalized_files
            }
            for future in concurrent.futures.as_completed(future_to_file):
                try:
                    res, f_stats = future.result()
                    if res:
                        results.append(res)
                        if f_stats.get("is_codemap"):
                            stats["codemap_files"] += 1
                            if f_stats.get("cache_hit"):
                                stats["tree_cache_hits"] += 1
                            else:
                                stats["tree_cache_misses"] += 1
                except Exception:
                    continue

        # 4. Gom Phase 1: Adjacency & Symbols
        adjacency: Dict[str, Set[str]] = {}
        symbol_index: Dict[str, str] = {}

        for res in results:
            # Update tree cache if provided (Phase 4 Optimization)
            if tree_cache is not None and res.tree_info:
                path, info = res.tree_info
                tree_cache[path] = info

            adjacency[res.source_abs] = res.direct_imports
            for sym_name, file_abs in res.symbols:
                symbol_index.setdefault(sym_name, file_abs)

        # 5. Xây dựng IMPORTS edges (bao gồm cả transitive depth)
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

            # Transitive deps
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

        # 6. Xây dựng CALLS / INHERITS edges từ kết quả đã thu thập
        for res in results:
            for rel in res.relationships:
                if rel.kind not in (RelationshipKind.CALLS, RelationshipKind.INHERITS):
                    continue

                target_file = symbol_index.get(rel.target)
                if not target_file or target_file == res.source_abs:
                    continue

                edge_kind = (
                    EdgeKind.CALLS
                    if rel.kind == RelationshipKind.CALLS
                    else EdgeKind.INHERITS
                )
                graph.add_edge(
                    Edge(
                        source_file=res.source_abs,
                        target_file=target_file,
                        kind=edge_kind,
                        metadata={"symbol": rel.target, "line": rel.source_line},
                    )
                )

        duration = time.perf_counter() - stats["start_time"]
        log_info(
            f"[GraphBuilder] Build finished in {duration:.2f}s:\n"
            f"  - Total files: {stats['total_files']}\n"
            f"  - CodeMap files processed: {stats['codemap_files']}\n"
            f"  - Tree cache hit: {stats['tree_cache_hits']}\n"
            f"  - Tree cache miss: {stats['tree_cache_misses']}"
        )

        return graph

    def _process_file(
        self,
        file_path: Path,
        resolver: DependencyResolver,
        do_codemap: bool,
        old_tree_data: Optional[tuple[float, Any, str, set[str]]] = None,
    ) -> tuple[Optional[FileProcessingResult], dict]:
        """
        Xử lý đơn lẻ một file: Read disk (1 lần) + Parse AST (1 lần) + Extract Multi-Extractors.
        Returns (Result, Stats)
        """
        stats = {"is_codemap": do_codemap, "cache_hit": False}
        try:
            source_abs = str(file_path.resolve())
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            # MD5 hash is stable across Python sessions (hash() is not)
            content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
            mtime = file_path.stat().st_mtime

            # --- Pha 1: Extract Quick Imports (With Adjacency Cache) ---
            targets = set()

            # Reuse targets if content hasn't changed (Phase 5 Incremental Optimization)
            if old_tree_data and old_tree_data[2] == content_hash:
                targets = old_tree_data[3]  # Reuse targets
                stats["cache_hit"] = True
            else:
                direct_deps = resolver.get_related_files_with_depth(
                    file_path, max_depth=1
                )
                for target_path, _ in direct_deps.items():
                    if target_path.exists():
                        try:
                            targets.add(str(target_path.resolve()))
                        except OSError:
                            targets.add(str(target_path))

            # Nếu không cần CodeMap, thoát sớm để tiết kiệm CPU
            if not do_codemap:
                return FileProcessingResult(
                    source_abs,
                    targets,
                    [],
                    [],
                    (source_abs, (mtime, None, content_hash, targets)),
                ), stats

            ext = file_path.suffix.lstrip(".")
            language = get_language(ext)
            if not language:
                return FileProcessingResult(source_abs, targets, [], [], None), stats

            # PHASE 4: CONTENT HASH REUSE
            tree = None
            if (
                old_tree_data
                and old_tree_data[2] == content_hash
                and old_tree_data[1] is not None
            ):
                tree = old_tree_data[1]
                stats["cache_hit"] = True  # Giữ nguyên hoặc cộng dồn hit
            else:
                parser = Parser(language)
                tree = parser.parse(bytes(content, "utf-8"))

            if not tree or not tree.root_node:
                return FileProcessingResult(
                    source_abs,
                    targets,
                    [],
                    [],
                    (source_abs, (mtime, None, content_hash, targets)),
                ), stats

            # 2a. Symbols (Reuse tree đã parse)
            symbols_raw = extract_symbols(
                str(file_path), content, tree=tree, language=language
            )
            symbols = []
            for sym in symbols_raw:
                if sym.kind in (
                    SymbolKind.FUNCTION,
                    SymbolKind.METHOD,
                    SymbolKind.CLASS,
                ):
                    symbols.append((sym.name, source_abs))

            # 2b. Relationships (Reuse tree đã parse)
            relationships = extract_relationships(
                str(file_path),
                content,
                known_symbols=None,
                tree=tree,
                language=language,
            )

            return FileProcessingResult(
                source_abs,
                targets,
                symbols,
                relationships,
                tree_info=(source_abs, (mtime, tree, content_hash, targets)),
            ), stats

        except Exception:
            return None, stats
