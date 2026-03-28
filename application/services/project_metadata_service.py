"""
ProjectMetadataService - Tinh metadata cau truc tu RelationshipGraph.

Zero cost, zero latency, zero API calls.
Chi su dung graph da duoc build san boi GraphService.
"""

import hashlib
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

from domain.metadata.project_metadata import FileScore, ModuleInfo, ProjectMetadata
from domain.relationships.graph import RelationshipGraph
from domain.relationships.types import EdgeKind


class ProjectMetadataService:
    """
    Tinh toan ProjectMetadata thuan tuy tu RelationshipGraph.

    Khong ket noi mang, khong goi LLM, khong doc disk (ngoai viec group paths).
    Thoi gian chay: <100ms cho project toi 10K files.
    """

    def compute(
        self,
        graph: RelationshipGraph,
        workspace_root: Path,
        top_n: int = 10,
        max_flows: int = 5,
    ) -> ProjectMetadata:
        """
        Tinh ProjectMetadata tu RelationshipGraph da build san.

        Args:
            graph: RelationshipGraph da duoc build boi GraphService
            workspace_root: Thu muc goc de tinh relative paths
            top_n: So luong top files toi da
            max_flows: So luong sample flows toi da

        Returns:
            ProjectMetadata bao gom top_files, modules, sample_flows
        """
        all_files = graph.all_files()
        workspace_str = str(workspace_root.resolve())

        # Tinh relative paths cho tat ca files
        rel_map: Dict[str, str] = self._build_rel_map(all_files, workspace_str)

        top_files = self._compute_top_files(graph, rel_map, limit=top_n)
        modules = self._compute_modules(graph, rel_map)
        sample_flows = self._compute_sample_flows(graph, rel_map, limit=max_flows)
        fingerprint = self._compute_fingerprint(graph)

        return ProjectMetadata(
            graph_fingerprint=fingerprint,
            file_count=len(all_files),
            edge_count=graph.edge_count(),
            top_files=top_files,
            modules=modules,
            sample_flows=sample_flows,
        )

    # ===== Internal helpers =====

    def _build_rel_map(self, abs_paths: Set[str], workspace_str: str) -> Dict[str, str]:
        """
        Build mapping: abs_path -> relative_path (tu workspace).
        Neu path la relative hoac nam ngoai workspace, dung basename.
        """
        rel_map: Dict[str, str] = {}
        for abs_path in abs_paths:
            p = Path(abs_path)
            # Neu path da la relative (e.g., trong tests), sau khi resolve se dung basenames
            if not p.is_absolute():
                # Path tuong doi -> giu nguyen (co the la workspace-relative da)
                rel_map[abs_path] = abs_path
                continue
            try:
                rel = os.path.relpath(abs_path, workspace_str)
                rel_map[abs_path] = rel
            except ValueError:
                # Windows: drive khac nhau
                rel_map[abs_path] = os.path.basename(abs_path)
        return rel_map

    def _compute_top_files(
        self,
        graph: RelationshipGraph,
        rel_map: Dict[str, str],
        limit: int,
    ) -> List[FileScore]:
        """
        Tinh diem quan trong cua tung file.
        score = in_edges * 2 + out_edges (file binh quay = file trung tam).
        """
        scores: List[FileScore] = []
        for abs_path, rel_path in rel_map.items():
            in_e = len(graph.get_edges_to(abs_path))
            out_e = len(graph.get_edges_from(abs_path))
            score = in_e * 2 + out_e
            scores.append(
                FileScore(
                    path=rel_path,
                    score=score,
                    in_edges=in_e,
                    out_edges=out_e,
                )
            )

        return sorted(scores, key=lambda x: x.score, reverse=True)[:limit]

    def _compute_modules(
        self,
        graph: RelationshipGraph,
        rel_map: Dict[str, str],
    ) -> List[ModuleInfo]:
        """
        Nhom files theo directory (top-level), dem internal edges.
        Internal edge = edge giua 2 files cung directory.

        Heuristic: developer thuong dat files cung feature vao cung thu muc.
        """
        # Group abs_paths theo top-level directory (1-2 levels) tu workspace
        dir_files: Dict[str, List[str]] = defaultdict(list)
        for abs_path, rel_path in rel_map.items():
            parts = Path(rel_path).parts
            if len(parts) >= 3:
                # Dung 2 levels: domain/auth/
                top_dir = parts[0] + "/" + parts[1] + "/"
            elif len(parts) == 2:
                # Chi co 1 level: modA/
                top_dir = parts[0] + "/"
            elif len(parts) == 1:
                top_dir = "(root)/"
            else:
                continue
            dir_files[top_dir].append(abs_path)

        # Dem internal edges cho moi module
        modules: List[ModuleInfo] = []
        for dir_root, file_list in dir_files.items():
            file_set = set(file_list)
            internal: int = 0
            for abs_path in file_list:
                for edge in graph.get_edges_from(abs_path):
                    if edge.target_file in file_set:
                        internal += 1
            if len(file_list) >= 2 or internal > 0:
                modules.append(
                    ModuleInfo(
                        root=dir_root,
                        file_count=len(file_list),
                        internal_edges=internal,
                    )
                )

        return sorted(modules, key=lambda m: m.internal_edges, reverse=True)

    def _compute_sample_flows(
        self,
        graph: RelationshipGraph,
        rel_map: Dict[str, str],
        limit: int,
    ) -> List[str]:
        """
        Tim cac call chains bat dau tu entry points (files khong co in_edges).
        Moi flow la chuoi: "a.py -> b.py -> c.py".
        """
        # Tim entry points: files co out_edges > 0 va in_edges == 0
        entry_points: List[str] = []
        for abs_path in rel_map:
            in_e = len(graph.get_edges_to(abs_path))
            out_e = len(graph.get_edges_from(abs_path))
            if in_e == 0 and out_e > 0:
                entry_points.append(abs_path)

        flows: List[str] = []
        seen: Set[str] = set()
        allowed_kinds = {EdgeKind.CALLS, EdgeKind.IMPORTS}

        for entry in entry_points:
            if len(flows) >= limit:
                break
            # BFS de tim duong di dai nhat tu entry
            path = self._longest_path_bfs(graph, entry, allowed_kinds, max_depth=4)
            if len(path) >= 2:
                flow = " -> ".join(os.path.basename(rel_map.get(p, p)) for p in path)
                if flow not in seen:
                    flows.append(flow)
                    seen.add(flow)

        return flows

    def _longest_path_bfs(
        self,
        graph: RelationshipGraph,
        start: str,
        allowed_kinds: Set[EdgeKind],
        max_depth: int,
    ) -> List[str]:
        """
        BFS tu start de tim duong di dai nhat (theo so nodes).
        Tranh cycle bang visited set.
        Returns: list cac node theo thu tu.
        """
        from collections import deque

        # (current_node, path_so_far)
        queue: deque = deque([(start, [start])])
        best_path: List[str] = [start]

        while queue:
            node, path = queue.popleft()
            if len(path) > len(best_path):
                best_path = path
            if len(path) >= max_depth:
                continue
            for edge in graph.get_edges_from(node):
                if edge.kind not in allowed_kinds:
                    continue
                neighbor = edge.target_file
                if neighbor not in path:  # Tranh cycle
                    queue.append((neighbor, path + [neighbor]))

        return best_path

    def _compute_fingerprint(self, graph: RelationshipGraph) -> str:
        """
        Hash nhanh cua graph: sort va hash tat ca edges.
        Dung de kiem tra xem graph co thay doi giua 2 lan compute khong.
        """
        all_files = sorted(graph.all_files())
        edge_strs: List[str] = []
        for file_path in all_files:
            for edge in graph.get_edges_from(file_path):
                edge_strs.append(f"{edge.source_file}|{edge.target_file}|{edge.kind}")

        edge_strs.sort()
        content = "\n".join(edge_strs)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
