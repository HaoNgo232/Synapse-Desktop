"""
Dependency Resolver - Tìm và resolve các file liên quan thông qua import statements.

Module này sử dụng Tree-sitter để parse import statements trong code
và resolve chúng thành file paths thực tế trong workspace.

MVP: Hỗ trợ Python imports trước (Phase 1).
Future: JavaScript/TypeScript imports (Phase 2).
"""

import os
import logging
from pathlib import Path
from typing import Optional, Set, Dict, List
from tree_sitter import Parser, Query, QueryCursor, Language  # type: ignore

from domain.smart_context.loader import get_language
from domain.filesystem.collector import collect_files_from_disk
from shared.utils.filesystem import is_binary_file, is_system_path_str
from infrastructure.filesystem.file_utils import TreeItem

logger = logging.getLogger(__name__)

# ========================================
# Import Queries cho từng ngôn ngữ
# Các queries này extract import module names từ AST
# ========================================

IMPORT_QUERIES: Dict[str, str] = {
    "python": """
        (import_statement
            name: (dotted_name) @import.module)
        (import_from_statement
            module_name: (dotted_name) @import.module)
        (import_from_statement
            module_name: (relative_import) @import.relative)
    """,
    "javascript": """
        (import_statement
            source: (string) @import.source)
        (export_statement
            source: (string) @import.source)
        (call_expression
            function: (identifier) @func (#eq? @func "require")
            arguments: (arguments (string) @import.source))
    """,
    "typescript": """
        (import_statement
            source: (string) @import.source)
        (export_statement
            source: (string) @import.source)
        (call_expression
            function: (identifier) @func (#eq? @func "require")
            arguments: (arguments (string) @import.source))
    """,
    "go": """
        (import_spec path: [(interpreted_string_literal) (raw_string_literal)] @import.source)
    """,
    "rust": """
        (use_declaration argument: (path_expression) @import.source)
        (extern_crate_declaration name: (identifier) @import.source)
    """,
    "ruby": """
        (call
            method: (identifier) @func (#match? @func "require(_relative)?")
            arguments: (argument_list (string) @import.source))
    """,
    "java": """
        (import_declaration name: (dotted_name) @import.module)
    """,
    "cpp": """
        (preproc_include path: [(string_literal) (system_lib_string) (header_name)] @import.source)
    """,
    "c_sharp": """
        (using_directive name: [(identifier) (qualified_name)] @import.module)
    """,
}


class DependencyResolver:
    """
    Resolve imports trong file thành file paths trong workspace.
    """

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root.resolve()
        self._file_index: Dict[str, Path] = {}
        self._module_index: Dict[str, Path] = {}
        self._ts_paths: Dict[str, List[str]] = {}
        self._ts_base_url: Optional[Path] = None
        self._ts_config_loaded: bool = False

    def build_file_index(self, tree: Optional[TreeItem]) -> None:
        self._load_ts_config()
        if not tree:
            return
        self._file_index.clear()
        self._module_index.clear()
        self._index_recursive(tree)

    def build_file_index_from_disk(self, workspace_root: Path) -> None:
        """Build file index trực tiếp từ disk."""
        self._load_ts_config()
        self._file_index.clear()
        self._module_index.clear()

        all_files = collect_files_from_disk(
            workspace_root, workspace_path=workspace_root
        )

        for file_path_str in all_files:
            if is_system_path_str(file_path_str) or is_binary_file(file_path_str):
                continue

            file_path = Path(file_path_str)
            self._file_index[file_path.name] = file_path

            try:
                rel_path = file_path.relative_to(self.workspace_root)
                if file_path.suffix == ".py":
                    module_name = str(rel_path.with_suffix("")).replace(os.sep, ".")
                    self._module_index[module_name] = file_path
            except ValueError:
                pass

    def _load_ts_config(self) -> None:
        if self._ts_config_loaded:
            return
        self._ts_config_loaded = True
        config_names = ["tsconfig.json", "jsconfig.json"]
        search_dirs = [
            self.workspace_root,
            self.workspace_root / "frontend",
            self.workspace_root / "src",
            self.workspace_root / "app",
        ]
        config_path: Path | None = None
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for name in config_names:
                candidate = search_dir / name
                if candidate.exists():
                    config_path = candidate
                    break
            if config_path:
                break
        if not config_path:
            return
        try:
            import json
            import re

            content = config_path.read_text(encoding="utf-8")
            content = re.sub(r"//.*$", "", content, flags=re.MULTILINE)
            content = re.sub(r",(\s*[}\]])", r"\1", content)
            config = json.loads(content)
            compiler_options = config.get("compilerOptions", {})
            base_url = compiler_options.get("baseUrl", ".")
            self._ts_base_url = (config_path.parent / base_url).resolve()
            paths = compiler_options.get("paths", {})
            for alias_pattern, target_paths in paths.items():
                if isinstance(target_paths, list):
                    normalized_paths: list[str] = [
                        str(p)[2:] if str(p).startswith("./") else str(p)
                        for p in target_paths
                    ]
                    self._ts_paths[alias_pattern] = normalized_paths
        except Exception:
            pass

    def _index_recursive(self, item: TreeItem) -> None:
        if not item.is_dir:
            file_path = Path(item.path)
            self._file_index[file_path.name] = file_path
            try:
                rel_path = file_path.relative_to(self.workspace_root)
                if file_path.suffix == ".py":
                    module_name = str(rel_path.with_suffix("")).replace(os.sep, ".")
                    self._module_index[module_name] = file_path
            except ValueError:
                pass
        for child in item.children:
            self._index_recursive(child)

    def get_related_files(self, file_path: Path, max_depth: int = 1) -> Set[Path]:
        if not file_path.exists():
            return set()
        ext = file_path.suffix.lstrip(".")
        lang_name = self._get_lang_name(ext)
        if lang_name not in IMPORT_QUERIES:
            return set()
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return set()
        language = get_language(ext)
        if not language:
            return set()
        import_names = self._extract_imports(language, content, lang_name, file_path)
        resolved = self._resolve_imports(import_names, file_path, lang_name)
        if max_depth > 1:
            for resolved_path in list(resolved):
                if resolved_path.exists() and resolved_path != file_path:
                    nested = self.get_related_files(resolved_path, max_depth - 1)
                    resolved.update(nested)
        return resolved

    def get_related_files_with_depth(
        self, file_path: Path, max_depth: int = 1
    ) -> Dict[Path, int]:
        if not file_path.exists():
            return {}
        result: Dict[Path, int] = {}
        visited: Set[Path] = {file_path}
        self._collect_with_depth(file_path, 1, max_depth, result, visited)
        result.pop(file_path, None)
        return result

    def _collect_with_depth(
        self,
        file_path: Path,
        current_depth: int,
        max_depth: int,
        result: Dict[Path, int],
        visited: Set[Path],
    ) -> None:
        if current_depth > max_depth:
            return
        ext = file_path.suffix.lstrip(".")
        lang_name = self._get_lang_name(ext)
        if lang_name not in IMPORT_QUERIES:
            return
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return
        language = get_language(ext)
        if not language:
            return
        import_names = self._extract_imports(language, content, lang_name, file_path)
        resolved = self._resolve_imports(import_names, file_path, lang_name)
        for resolved_path in resolved:
            if not resolved_path.exists():
                continue
            prev_depth = result.get(resolved_path)
            is_shorter = prev_depth is None or current_depth < prev_depth
            if is_shorter:
                result[resolved_path] = current_depth
            if resolved_path not in visited or (
                is_shorter and current_depth + 1 <= max_depth
            ):
                visited.add(resolved_path)
                self._collect_with_depth(
                    resolved_path, current_depth + 1, max_depth, result, visited
                )

    def _extract_imports(
        self, language: Language, content: str, lang_name: str, source_file: Path
    ) -> Set[str]:
        import_names: Set[str] = set()
        try:
            parser = Parser(language)
            tree = parser.parse(bytes(content, "utf-8"))
            if not tree or not tree.root_node:
                return import_names
            query_string = IMPORT_QUERIES.get(lang_name, "")
            if not query_string:
                return import_names
            query = Query(language, query_string)
            query_cursor = QueryCursor(query)
            captures = query_cursor.captures(tree.root_node)
            for capture_name, nodes in captures.items():
                for node in nodes:
                    import_text = node.text.decode("utf-8") if node.text else ""
                    if not import_text:
                        continue
                    if capture_name == "import.relative":
                        import_names.add(import_text)
                    elif capture_name == "import.module":
                        import_names.add(import_text)
                    elif capture_name == "import.source":
                        import_names.add(import_text.strip("'\""))
        except Exception:
            pass
        return import_names

    def _resolve_imports(
        self, import_names: Set[str], source_file: Path, lang_name: str
    ) -> Set[Path]:
        resolved: Set[Path] = set()
        source_dir = source_file.parent
        for import_name in import_names:
            resolved_path = None
            if lang_name == "python":
                resolved_path = self._resolve_python_import(import_name, source_dir)
            elif lang_name in ("javascript", "typescript"):
                resolved_path = self.resolve_js_import(import_name, source_dir)
            if resolved_path and resolved_path.exists():
                resolved.add(resolved_path)
        return resolved

    def _resolve_python_import(
        self, import_name: str, source_dir: Path
    ) -> Optional[Path]:
        if import_name.startswith("."):
            return self._resolve_python_relative(import_name, source_dir)
        if import_name in self._module_index:
            return self._module_index[import_name]
        parts = import_name.split(".")
        for i in range(len(parts), 0, -1):
            partial_module = ".".join(parts[:i])
            if partial_module in self._module_index:
                return self._module_index[partial_module]
        path_parts = import_name.replace(".", os.sep)
        candidate = self.workspace_root / (path_parts + ".py")
        if candidate.exists():
            return candidate
        candidate = self.workspace_root / path_parts / "__init__.py"
        if candidate.exists():
            return candidate.parent
        return None

    def _resolve_python_relative(
        self, import_name: str, source_dir: Path
    ) -> Optional[Path]:
        dot_count = 0
        for char in import_name:
            if char == ".":
                dot_count += 1
            else:
                break
        module_part = import_name[dot_count:]
        target_dir = source_dir
        for _ in range(dot_count - 1):
            target_dir = target_dir.parent
        if not module_part:
            return None
        path_parts = module_part.replace(".", os.sep)
        candidate = target_dir / (path_parts + ".py")
        if candidate.exists():
            return candidate
        candidate = target_dir / path_parts / "__init__.py"
        if candidate.exists():
            return candidate
        return None

    def resolve_js_import(self, import_path: str, source_dir: Path) -> Optional[Path]:
        possible_extensions = [".ts", ".tsx", ".js", ".jsx", ""]
        if import_path.startswith("."):
            for ext in possible_extensions:
                candidate = (source_dir / (import_path + ext)).resolve()
                if candidate.exists() and candidate.is_file():
                    return candidate
                if ext == "":
                    for index_name in [
                        "index.ts",
                        "index.tsx",
                        "index.js",
                        "index.jsx",
                    ]:
                        index_candidate = (
                            source_dir / import_path / index_name
                        ).resolve()
                        if index_candidate.exists():
                            return index_candidate
            return None
        resolved = self._resolve_js_by_filename(import_path, possible_extensions)
        if resolved:
            return resolved
        if self._ts_paths and self._ts_base_url:
            resolved = self._resolve_ts_alias(import_path, possible_extensions)
            if resolved:
                return resolved
        return None

    def _resolve_ts_alias(
        self, import_path: str, extensions: list[str]
    ) -> Optional[Path]:
        for alias_pattern, target_paths in self._ts_paths.items():
            if alias_pattern.endswith("/*"):
                prefix = alias_pattern[:-2]
                if import_path.startswith(prefix + "/"):
                    suffix = import_path[len(prefix) + 1 :]
                    for target in target_paths:
                        target_prefix = (
                            target.replace("*", suffix) if "*" in target else target
                        )
                        suffix_to_append = "" if "*" in target else suffix
                        base = (
                            (self._ts_base_url or self.workspace_root)
                            / target_prefix
                            / suffix_to_append
                        )
                        for ext in extensions:
                            candidate = Path(str(base) + ext)
                            if candidate.exists() and candidate.is_file():
                                return candidate
                            if ext == "":
                                for index_name in [
                                    "index.ts",
                                    "index.tsx",
                                    "index.js",
                                    "index.jsx",
                                ]:
                                    index_candidate = base / index_name
                                    if index_candidate.exists():
                                        return index_candidate
            elif alias_pattern == import_path:
                for target in target_paths:
                    base = (self._ts_base_url or self.workspace_root) / target
                    for ext in extensions:
                        full_candidate = Path(str(base) + ext)
                        if full_candidate.exists() and full_candidate.is_file():
                            return full_candidate
        return None

    def _resolve_js_by_filename(
        self, import_path: str, extensions: list[str]
    ) -> Optional[Path]:
        if not self._file_index:
            return None
        basename = import_path.rsplit("/", 1)[-1] if "/" in import_path else import_path
        if not basename:
            return None
        for ext in extensions:
            key = basename + ext
            if key in self._file_index:
                return self._file_index[key]
        return None

    def _get_lang_name(self, ext: str) -> str:
        ext = ext.lower()
        if ext == "py":
            return "python"
        if ext in ("js", "jsx"):
            return "javascript"
        if ext in ("ts", "tsx"):
            return "typescript"
        if ext == "go":
            return "go"
        if ext == "rs":
            return "rust"
        if ext == "rb":
            return "ruby"
        if ext == "java":
            return "java"
        if ext in ("cpp", "cc", "cxx", "h", "hpp"):
            return "cpp"
        if ext == "cs":
            return "c_sharp"
        return ""


def get_related_files_for_selection(
    workspace_root: Path, tree: Optional[TreeItem], selected_file: Path
) -> Set[Path]:
    """
    Convenience function to find related files for a specific selection.
    This creates a resolver instance, builds the index, and returns results.
    """
    resolver = DependencyResolver(workspace_root)
    resolver.build_file_index(tree)
    return resolver.get_related_files(selected_file)
