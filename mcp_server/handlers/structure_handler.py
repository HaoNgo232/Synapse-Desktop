"""
Structure Handler - Xu ly cac tool lien quan den project structure.

Bao gom: get_project_structure, explain_architecture.
"""

import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import Context

from mcp_server.core.constants import logger
from mcp_server.core.workspace_manager import WorkspaceManager
import asyncio


def _detect_frameworks(ws: Path) -> list[str]:
    """Phat hien cac framework dua tren file cau hinh.

    Dung 1 listdir + set lookup thay vi nhieu stat calls.

    Args:
        ws: Workspace root path.

    Returns:
        Danh sach framework names da phat hien.
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

    # Kiem tra them framework cu the
    if "manage.py" in root_files:
        frameworks.append("Django")
    if "next.config.js" in root_files or "next.config.mjs" in root_files:
        frameworks.append("Next.js")
    if "angular.json" in root_files:
        frameworks.append("Angular")

    return frameworks


def _get_project_structure(workspace_path: str) -> str:
    """Internal implementation cho get_project_structure, co the goi tu start_session.

    Args:
        workspace_path: Duong dan workspace.

    Returns:
        Chuoi tom tat project structure.
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    try:
        from services.workspace_index import collect_files_from_disk

        all_files = collect_files_from_disk(ws, workspace_path=ws)
        total = len(all_files)

        if total == 0:
            return f"Project: {ws.name}\nNo files found (empty or fully ignored)."

        # Dem so luong file theo extension
        ext_counter: Counter[str] = Counter()
        total_bytes = 0
        for f in all_files:
            ext = Path(f).suffix.lower() or "(no extension)"
            ext_counter[ext] += 1
            try:
                total_bytes += os.path.getsize(f)
            except OSError:
                pass

        # Sap xep theo so luong giam dan
        ext_lines = []
        for ext, count in ext_counter.most_common(20):
            ext_lines.append(f"  {ext:<15} {count:>5} files")

        # Phat hien frameworks
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

        # 1. Module analysis - group files by top-level directory
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
            # Top-level module = first directory, or "(root)" for root files
            module = parts[0] if len(parts) > 1 else "(root)"
            module_stats[module]["files"] += 1
            module_stats[module]["extensions"][fp.suffix.lower()] += 1

            # Detect entry points
            if fp.name in entry_names:
                entry_points.append(str(rel))

            # Detect config files
            if fp.name in config_names:
                config_files.append(str(rel))

        # 2. Dependency analysis (sample top modules)
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

        # Sample up to 100 files for dependency analysis
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

        # 3. Format output
        sections = []
        title = f"Architecture: {ws.name}"
        if focus_directory:
            title += f" (focus: {focus_directory}/)"
        sections.append(f"{title}\n{'=' * len(title)}\n")

        # Overview
        sections.append(
            f"Total: {len(all_files)} files, {len(module_stats)} top-level modules\n"
        )

        # Entry points
        if entry_points:
            sections.append("Entry Points:")
            for ep in entry_points[:10]:
                sections.append(f"  -> {ep}")
            sections.append("")

        # Config/infra
        if config_files:
            sections.append("Configuration:")
            for cf in config_files[:10]:
                sections.append(f"  * {cf}")
            sections.append("")

        # Module breakdown
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

        # Cross-module coupling
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

        # Recommendations for agent
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
    async def get_project_structure(
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Get project summary: file counts, types, frameworks, and estimated tokens.

        Args:
            workspace_path: Absolute path to workspace root.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        return await asyncio.to_thread(_get_project_structure, str(ws))

    @mcp_instance.tool()
    async def explain_architecture(
        focus_directory: Optional[str] = None,
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Generate a high-level architecture summary of the codebase.

        Args:
            focus_directory: Optional subdirectory to focus analysis on (e.g., "src").
            workspace_path: Absolute path to workspace root.
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
