"""
Structure Handler - Xu ly cac tool lien quan den project structure.

Bao gom: explain_architecture. (get_project_structure da go bo - dung built-in glob/script.)
"""

import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Annotated, Optional

from mcp.server.fastmcp import Context
from pydantic import Field

from mcp_server.core.constants import logger
from mcp_server.core.workspace_manager import WorkspaceManager
import asyncio


def _detect_frameworks(ws: Path) -> list[str]:
    """Phat hien cac framework dua tren file cau hinh.

    Dung 1 listdir + set lookup thay vi nhieu stat calls.
    """
    try:
        root_files = set(os.listdir(ws))
    except OSError:
        return []

    frameworks = []
    markers = {
        "requirements.txt": "Python",
        "pyproject.toml": "Python (modern)",
        "package.json": "Node.js",
        "Cargo.toml": "Rust",
        "go.mod": "Go",
        "pom.xml": "Java/Maven",
        "build.gradle": "Java/Gradle",
        "Gemfile": "Ruby",
        "composer.json": "PHP",
    }
    for filename, fw in markers.items():
        if filename in root_files:
            frameworks.append(fw)

    if "manage.py" in root_files:
        frameworks.append("Django")
    if "next.config.js" in root_files or "next.config.mjs" in root_files:
        frameworks.append("Next.js")
    if "angular.json" in root_files:
        frameworks.append("Angular")

    return frameworks


def _get_project_structure(
    workspace_path: str, cached_files: Optional[list[str]] = None
) -> str:
    """Internal implementation cho get_project_structure, co the goi tu start_session.

    Args:
        workspace_path: Duong dan workspace root.
        cached_files: Danh sach files da scan san (optional).
                      Neu truyen vao, se dung truc tiep thay vi goi collect_files_from_disk.
                      Giup tranh scan filesystem nhieu lan trong start_session.
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    try:
        # Su dung cached_files neu co, tranh scan filesystem lan 2
        if cached_files is not None:
            all_files = cached_files
        else:
            from services.workspace_index import collect_files_from_disk

            all_files = collect_files_from_disk(ws, workspace_path=ws)

        total = len(all_files)

        if total == 0:
            return f"Project: {ws.name}\nNo files found (empty or fully ignored)."

        ext_counter: Counter[str] = Counter()
        total_bytes = 0
        for f in all_files:
            ext = Path(f).suffix.lower() or "(no extension)"
            ext_counter[ext] += 1
            try:
                total_bytes += os.path.getsize(f)
            except OSError:
                pass

        ext_lines = []
        for ext, count in ext_counter.most_common(20):
            ext_lines.append(f"  {ext:<15} {count:>5} files")

        frameworks = _detect_frameworks(ws)
        fw_line = (
            f"Frameworks: {', '.join(frameworks)}"
            if frameworks
            else "Frameworks: (not detected)"
        )

        estimated_tokens = total_bytes // 4

        return (
            f"Project: {ws.name}\n"
            f"Total files: {total:,}\n"
            f"Total size: {total_bytes:,} bytes (~{estimated_tokens:,} tokens)\n"
            f"{fw_line}\n"
            f"\nFile types:\n" + "\n".join(ext_lines)
        )

    except Exception as e:
        logger.error("get_project_structure error: %s", e)
        return f"Error analyzing project: {e}"


def _explain_architecture_impl(
    scan_root: Path, ws: Path, focus_directory: Optional[str]
) -> str:
    """Internal implementation cho explain_architecture, dung asyncio.to_thread."""
    try:
        from services.workspace_index import collect_files_from_disk
        from core.dependency_resolver import DependencyResolver

        all_files = collect_files_from_disk(scan_root, workspace_path=ws)
        if not all_files:
            return "No files found to analyze."

        module_stats: dict[str, dict] = defaultdict(
            lambda: {"files": 0, "extensions": Counter()}
        )
        entry_points: list[str] = []
        config_files: list[str] = []

        entry_names = {
            "main.py",
            "app.py",
            "server.py",
            "index.js",
            "index.ts",
            "main.go",
            "main.rs",
            "Main.java",
            "Program.cs",
            "manage.py",
            "wsgi.py",
            "asgi.py",
            "cli.py",
        }
        config_names = {
            "package.json",
            "pyproject.toml",
            "Cargo.toml",
            "go.mod",
            "pom.xml",
            "build.gradle",
            "Gemfile",
            "composer.json",
            "tsconfig.json",
            "webpack.config.js",
            "vite.config.ts",
            "docker-compose.yml",
            "Dockerfile",
        }

        for f in all_files:
            fp = Path(f)
            try:
                rel = fp.relative_to(ws)
            except ValueError:
                continue

            parts = rel.parts
            module = parts[0] if len(parts) > 1 else "(root)"
            module_stats[module]["files"] += 1
            module_stats[module]["extensions"][fp.suffix.lower()] += 1

            if fp.name in entry_names:
                entry_points.append(str(rel))

            if fp.name in config_names:
                config_files.append(str(rel))

        code_exts = {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".go",
            ".rs",
        }
        code_files = [f for f in all_files if Path(f).suffix.lower() in code_exts]

        coupling_matrix: dict[str, Counter] = defaultdict(Counter)
        resolver = DependencyResolver(ws)
        resolver.build_file_index_from_disk(ws)

        sample_files = sorted(code_files)[:100]
        for f in sample_files:
            fp = Path(f)
            try:
                rel = fp.relative_to(ws)
                source_module = rel.parts[0] if len(rel.parts) > 1 else "(root)"
                related = resolver.get_related_files(fp, max_depth=1)
                for dep in related:
                    try:
                        dep_rel = dep.relative_to(ws)
                        dep_module = (
                            dep_rel.parts[0] if len(dep_rel.parts) > 1 else "(root)"
                        )
                        if dep_module != source_module:
                            coupling_matrix[source_module][dep_module] += 1
                    except ValueError:
                        pass
            except Exception as e:
                logger.debug("Failed to analyze dependencies for %s: %s", fp, e)

        sections = []
        title = f"Architecture: {ws.name}"
        if focus_directory:
            title += f" (focus: {focus_directory}/)"
        sections.append(f"{title}\n{'=' * len(title)}\n")

        sections.append(
            f"Total: {len(all_files)} files, {len(module_stats)} top-level modules\n"
        )

        if entry_points:
            sections.append("Entry Points:")
            for ep in entry_points[:10]:
                sections.append(f"  -> {ep}")
            sections.append("")

        if config_files:
            sections.append("Configuration:")
            for cf in config_files[:10]:
                sections.append(f"  * {cf}")
            sections.append("")

        sections.append("Modules (by file count):")
        sorted_modules = sorted(
            module_stats.items(),
            key=lambda x: x[1]["files"],
            reverse=True,
        )
        for module, stats in sorted_modules[:15]:
            file_count = stats["files"]
            top_exts = stats["extensions"].most_common(3)
            ext_str = ", ".join(f"{ext}({c})" for ext, c in top_exts)
            sections.append(f"  {module + '/':.<30} {file_count:>4} files  [{ext_str}]")
        sections.append("")

        if coupling_matrix:
            sections.append("Cross-Module Dependencies (strongest links):")
            all_links = []
            for src, targets in coupling_matrix.items():
                for tgt, count in targets.items():
                    all_links.append((src, tgt, count))
            all_links.sort(key=lambda x: x[2], reverse=True)
            for src, tgt, count in all_links[:10]:
                sections.append(f"  {src} -> {tgt} ({count} imports)")
            sections.append("")

        sections.append("Suggested exploration order:")
        if entry_points:
            sections.append(
                f"  1. Start with entry points: {', '.join(entry_points[:3])}"
            )
        sections.append(
            f"  2. Use batch_codemap on key modules: {', '.join(m for m, _ in sorted_modules[:3])}"
        )
        sections.append("  3. Use get_imports_graph for detailed dependency analysis")

        return "\n".join(sections)

    except Exception as e:
        logger.error("explain_architecture error: %s", e)
        return f"Error: {e}"


def register_tools(mcp_instance) -> None:
    """Dang ky structure tools voi MCP server."""

    @mcp_instance.tool()
    async def explain_architecture(
        focus_directory: Annotated[
            Optional[str],
            Field(
                description='Optional subdirectory to focus analysis on (e.g., "src", "mcp_server"). Analyzes entire workspace if omitted.'
            ),
        ] = None,
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted."
            ),
        ] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Generate a high-level architecture summary of the codebase.

        Analyzes entry points, configuration files, module structure (by file count and type),
        cross-module dependency coupling, and suggests an exploration order for AI agents.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        scan_root = ws
        if focus_directory:
            scan_root = (ws / focus_directory).resolve()
            if not scan_root.is_relative_to(ws) or not scan_root.is_dir():
                return f"Error: Invalid focus directory: {focus_directory}"

        return await asyncio.to_thread(
            _explain_architecture_impl, scan_root, ws, focus_directory
        )
