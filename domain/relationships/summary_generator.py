from __future__ import annotations
from pathlib import Path
from typing import Optional
from domain.relationships.graph import RelationshipGraph


def generate_relationship_summary_xml(
    graph: RelationshipGraph,
    workspace_root: Optional[Path] = None,
    max_entries: int = 50,
) -> str:
    """
    Generate XML summary of project relationships (Semantic Index) for prompt.

    This provides LLMs with high-level context about how files interact
    without needing the full content of every dependency.
    """
    if graph.edge_count() == 0:
        return ""

    import html
    from shared.utils.path_utils import path_for_display

    def _display(path_str: str) -> str:
        return html.escape(path_for_display(Path(path_str), workspace_root, True))

    lines = ["<semantic_index>"]

    # 1. Project Overview
    lines.append(
        f'  <overview total_files="{graph.file_count()}" total_edges="{graph.edge_count()}"/>'
    )

    # 2. Key Dependencies (most imported/called files)
    # Tinh xem file nao bi 'depend on' nhieu nhat
    in_degree = {}
    for file_path in graph.all_files():
        in_degree[file_path] = len(graph.get_edges_to(file_path))

    top_targets = sorted(in_degree.keys(), key=lambda k: in_degree[k], reverse=True)[
        :max_entries
    ]

    if top_targets:
        lines.append("  <key_dependencies>")
        for target in top_targets:
            if in_degree[target] == 0:
                continue

            # Group edges by kind for this target
            edges_in = graph.get_edges_to(target)
            kinds = {}
            for e in edges_in:
                kinds[e.kind.value] = kinds.get(e.kind.value, 0) + 1

            kind_str = ", ".join([f"{count} {k}" for k, count in kinds.items()])
            lines.append(
                f'    <file path="{_display(target)}" dependents="{in_degree[target]}" relations="{kind_str}"/>'
            )
        lines.append("  </key_dependencies>")

    # 3. Important relationships for primary files could be added here if we had them,
    # but since this is a global summary, we stick to high-level data.

    lines.append("</semantic_index>")
    return "\n".join(lines)


def generate_relationship_summary_plain(
    graph: RelationshipGraph,
    workspace_root: Optional[Path] = None,
    max_entries: int = 50,
) -> str:
    """
    Generate PLAIN text summary of project relationships (Semantic Index) for prompt.
    """
    if graph.edge_count() == 0:
        return ""

    from shared.utils.path_utils import path_for_display

    def _display(path_str: str) -> str:
        return path_for_display(Path(path_str), workspace_root, True)

    lines = []
    lines.append(
        f"Project Overview: {graph.file_count()} files, {graph.edge_count()} relationships."
    )

    in_degree = {}
    for file_path in graph.all_files():
        in_degree[file_path] = len(graph.get_edges_to(file_path))

    top_targets = sorted(in_degree.keys(), key=lambda k: in_degree[k], reverse=True)[
        :max_entries
    ]

    if top_targets:
        lines.append("\nKey Dependencies:")
        for target in top_targets:
            if in_degree[target] == 0:
                continue

            edges_in = graph.get_edges_to(target)
            kinds = {}
            for e in edges_in:
                kinds[e.kind.value] = kinds.get(e.kind.value, 0) + 1

            kind_str = ", ".join([f"{count} {k}" for k, count in kinds.items()])
            lines.append(
                f"  - {_display(target)}: {in_degree[target]} dependents ({kind_str})"
            )

    return "\n".join(lines)
