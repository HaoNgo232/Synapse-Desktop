"""
Formatter - Render ProjectMetadata thanh string XML-style de inject vao prompt.

Thiet ke: compact, structured, LLM-friendly.
Khong qua 30-40 dong de tiet kiem tokens.
"""

from domain.metadata.project_metadata import ProjectMetadata


def format_project_structure(metadata: ProjectMetadata) -> str:
    """
    Render ProjectMetadata thanh XML block de chen vao prompt.

    Tra ve string rong neu metadata khong co du lieu (graph chua duoc build
    hoac project qua nho de co structure co y nghia).

    Args:
        metadata: ProjectMetadata tinh tu graph

    Returns:
        XML string de inject vao prompt, hoac "" neu khong co gi de hien thi
    """
    has_top_files = bool(metadata.top_files)
    has_modules = bool(metadata.modules)
    has_flows = bool(metadata.sample_flows)

    # Neu khong co du lieu gi, tra ve rong tranh chen section thua
    if not has_top_files and not has_modules and not has_flows:
        return ""

    sections: list[str] = []

    # Section 1: Top files (file quan trong nhat)
    if has_top_files:
        top_lines = ["  <key_files>"]
        for fs in metadata.top_files[:8]:  # Toi da 8 files
            top_lines.append(f'    <file path="{fs.path}" centrality="{fs.score}"/>')
        top_lines.append("  </key_files>")
        sections.append("\n".join(top_lines))

    # Section 2: Module structure
    if has_modules:
        mod_lines = ["  <modules>"]
        for mi in metadata.modules[:6]:  # Toi da 6 modules
            mod_lines.append(
                f'    <module root="{mi.root}" files="{mi.file_count}" '
                f'coupling="{mi.internal_edges}"/>'
            )
        mod_lines.append("  </modules>")
        sections.append("\n".join(mod_lines))

    # Section 3: Key flows
    if has_flows:
        flow_lines = ["  <key_flows>"]
        for flow in metadata.sample_flows[:5]:  # Toi da 5 flows
            flow_lines.append(f"    <flow>{flow}</flow>")
        flow_lines.append("  </key_flows>")
        sections.append("\n".join(flow_lines))

    inner = "\n".join(sections)
    return f"<semantic_index>\n{inner}\n</semantic_index>"
