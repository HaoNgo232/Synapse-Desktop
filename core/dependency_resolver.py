"""
Dependency Resolver - Tìm và resolve các file liên quan thông qua import statements.

Module này sử dụng Tree-sitter để parse import statements trong code
và resolve chúng thành file paths thực tế trong workspace.

MVP: Hỗ trợ Python imports trước (Phase 1).
Future: JavaScript/TypeScript imports (Phase 2).
"""

import os
from pathlib import Path
from typing import Optional, Set, Dict, List
from tree_sitter import Parser, Query, QueryCursor, Language  # type: ignore

from core.smart_context.loader import get_language
from core.utils.file_utils import TreeItem


# ========================================
# Import Queries cho từng ngôn ngữ
# Các queries này extract import module names từ AST
# ========================================

IMPORT_QUERIES: Dict[str, str] = {
    # Python: import statements và from ... import statements
    "python": """
        ; Standard import: import module_name
        (import_statement
            name: (dotted_name) @import.module)
        
        ; From import: from module_name import something
        (import_from_statement
            module_name: (dotted_name) @import.module)
        
        ; Relative import: from . import something hoặc from .. import something
        (import_from_statement
            module_name: (relative_import) @import.relative)
    """,
    
    # JavaScript/TypeScript
    "javascript": """
        ; ES6 import: import x from 'module'
        (import_statement
            source: (string) @import.source)
        
        ; ES6 re-export: export { x } from 'module' hoặc export * from 'module'
        (export_statement
            source: (string) @import.source)
        
        ; CommonJS require: require('module')
        (call_expression
            function: (identifier) @func (#eq? @func "require")
            arguments: (arguments (string) @import.source))
    """,
    
    "typescript": """
        ; ES6 import: import x from 'module'
        (import_statement
            source: (string) @import.source)
        
        ; ES6 re-export: export { x } from 'module' hoặc export * from 'module'
        (export_statement
            source: (string) @import.source)
        
        ; CommonJS require: require('module') - also used in some TS codebases
        (call_expression
            function: (identifier) @func (#eq? @func "require")
            arguments: (arguments (string) @import.source))
    """,
}


class DependencyResolver:
    """
    Resolve imports trong file thành file paths trong workspace.
    
    Sử dụng Tree-sitter để parse code, extract imports,
    và resolve chúng thành actual file paths.
    
    Attributes:
        workspace_root: Root path của workspace
        _file_index: Index mapping filename -> full path
    """
    
    def __init__(self, workspace_root: Path):
        """
        Khởi tạo DependencyResolver.
        
        Args:
            workspace_root: Root path của workspace để resolve imports
        """
        self.workspace_root = workspace_root.resolve()
        self._file_index: Dict[str, Path] = {}
        self._module_index: Dict[str, Path] = {}  # module_name -> file_path
        
        # Alias support cho JS/TS (từ tsconfig.json/jsconfig.json)
        self._ts_paths: Dict[str, List[str]] = {}  # alias pattern -> list of paths
        self._ts_base_url: Optional[Path] = None
        self._ts_config_loaded: bool = False
    
    def build_file_index(self, tree: Optional[TreeItem]) -> None:
        """
        Build index từ TreeItem để hỗ trợ resolve imports.
        
        Index bao gồm:
        - filename -> full_path mapping
        - module_name -> file_path mapping (cho Python modules)
        
        Args:
            tree: TreeItem root của file tree
        """
        # Load tsconfig/jsconfig for alias support (luôn load, không phụ thuộc tree)
        self._load_ts_config()
        
        if not tree:
            return
        
        self._file_index.clear()
        self._module_index.clear()
        self._index_recursive(tree)
    
    def _load_ts_config(self) -> None:
        """
        Load tsconfig.json hoặc jsconfig.json để lấy path aliases.
        
        Đọc compilerOptions.paths và compilerOptions.baseUrl.
        Tìm kiếm trong root và các subfolder phổ biến (frontend/, src/, app/).
        Kết quả được cache để không phải đọc lại.
        """
        if self._ts_config_loaded:
            return
        
        self._ts_config_loaded = True
        
        # Tìm config file - ưu tiên root, sau đó các subfolder phổ biến
        config_names = ["tsconfig.json", "jsconfig.json"]
        search_dirs = [
            self.workspace_root,
            self.workspace_root / "frontend",
            self.workspace_root / "src",
            self.workspace_root / "app",
            self.workspace_root / "client",
            self.workspace_root / "web",
        ]
        
        config_path = None
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
            with open(config_path, "r", encoding="utf-8") as f:
                # Handle JSON with comments (trailing commas, // comments)
                content = f.read()
                # Simple cleanup: remove single-line comments
                import re
                content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
                # Remove trailing commas before } or ]
                content = re.sub(r',(\s*[}\]])', r'\1', content)
                
                config = json.loads(content)
            
            compiler_options = config.get("compilerOptions", {})
            
            # Extract baseUrl - nếu không có thì dùng thư mục chứa tsconfig
            base_url = compiler_options.get("baseUrl", ".")
            self._ts_base_url = (config_path.parent / base_url).resolve()
            
            # Extract paths và normalize (bỏ ./ prefix nếu có)
            paths = compiler_options.get("paths", {})
            for alias_pattern, target_paths in paths.items():
                if isinstance(target_paths, list):
                    # Normalize: bỏ ./ prefix
                    normalized_paths = []
                    for p in target_paths:
                        if p.startswith("./"):
                            p = p[2:]
                        normalized_paths.append(p)
                    self._ts_paths[alias_pattern] = normalized_paths
        
        except Exception:
            # Nếu parse lỗi thì bỏ qua, không break flow
            pass
    
    def _index_recursive(self, item: TreeItem) -> None:
        """Recursively index all files trong tree."""
        if not item.is_dir:
            file_path = Path(item.path)
            # Index by filename
            self._file_index[file_path.name] = file_path
            
            # Index by module path (cho Python)
            # Chuyển đổi path thành module name
            # Ví dụ: core/utils/file_utils.py -> core.utils.file_utils
            try:
                rel_path = file_path.relative_to(self.workspace_root)
                if file_path.suffix == ".py":
                    # Bỏ .py và chuyển / thành .
                    module_name = str(rel_path.with_suffix("")).replace(os.sep, ".")
                    self._module_index[module_name] = file_path
            except ValueError:
                pass
        
        # Recurse into children
        for child in item.children:
            self._index_recursive(child)
    
    def get_related_files(self, file_path: Path, max_depth: int = 1) -> Set[Path]:
        """
        Parse file và trả về set các files được import.
        
        Phân tích imports trong file và resolve chúng thành
        actual file paths trong workspace.
        
        Args:
            file_path: Path đến file cần analyze
            max_depth: Số cấp đệ quy để follow imports (default: 1 = chỉ direct imports)
        
        Returns:
            Set of resolved file paths trong workspace
        """
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
        
        # Parse và extract imports
        import_names = self._extract_imports(language, content, lang_name, file_path)
        
        # Resolve to actual file paths
        resolved = self._resolve_imports(import_names, file_path, lang_name)
        
        # Recursive resolution nếu max_depth > 1
        if max_depth > 1:
            for resolved_path in list(resolved):
                if resolved_path.exists() and resolved_path != file_path:
                    # Avoid adding source file and prevent infinite loops
                    nested = self.get_related_files(resolved_path, max_depth - 1)
                    resolved.update(nested)
        
        return resolved
    
    def _extract_imports(
        self, 
        language: Language, 
        content: str, 
        lang_name: str,
        source_file: Path
    ) -> Set[str]:
        """
        Extract import names từ file content sử dụng Tree-sitter queries.
        
        Args:
            language: Tree-sitter Language object
            content: File content
            lang_name: Language name (python, javascript, etc.)
            source_file: Path to source file (for relative imports)
        
        Returns:
            Set of import module/path names
        """
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
            
            # Xử lý captures
            for capture_name, nodes in captures.items():
                for node in nodes:
                    import_text = node.text.decode("utf-8") if node.text else ""
                    
                    if not import_text:
                        continue
                    
                    # Xử lý relative imports cho Python
                    if capture_name == "import.relative":
                        # Relative import như .utils hoặc ..models
                        import_names.add(import_text)
                    elif capture_name == "import.module":
                        # Standard import
                        import_names.add(import_text)
                    elif capture_name == "import.source":
                        # JavaScript/TypeScript: Bỏ quotes
                        cleaned = import_text.strip("'\"")
                        import_names.add(cleaned)
        
        except Exception:
            pass
        
        return import_names
    
    def _resolve_imports(
        self, 
        import_names: Set[str], 
        source_file: Path,
        lang_name: str
    ) -> Set[Path]:
        """
        Resolve import names thành actual file paths.
        
        Strategies:
        1. Python: dotted module -> file path
        2. Relative imports: ./module, ../module
        3. Search in file index
        
        Args:
            import_names: Set of import module names
            source_file: Path to source file (for relative imports)
            lang_name: Language name
        
        Returns:
            Set of resolved file paths
        """
        resolved: Set[Path] = set()
        source_dir = source_file.parent
        
        for import_name in import_names:
            resolved_path = None
            
            if lang_name == "python":
                resolved_path = self._resolve_python_import(import_name, source_dir)
            elif lang_name in ("javascript", "typescript"):
                resolved_path = self._resolve_js_import(import_name, source_dir)
            
            if resolved_path and resolved_path.exists():
                resolved.add(resolved_path)
        
        return resolved
    
    def _resolve_python_import(
        self, 
        import_name: str, 
        source_dir: Path
    ) -> Optional[Path]:
        """
        Resolve Python import thành file path.
        
        Strategies:
        1. Relative imports (.module, ..module)
        2. Absolute imports via module index
        3. Direct file search
        
        Args:
            import_name: Python module name (dotted notation)
            source_dir: Directory của file đang import
        
        Returns:
            Resolved Path hoặc None
        """
        # 1. Relative imports
        if import_name.startswith("."):
            return self._resolve_python_relative(import_name, source_dir)
        
        # 2. Absolute import - check module index
        if import_name in self._module_index:
            return self._module_index[import_name]
        
        # 3. Có thể là submodule - try prefix matching
        # Ví dụ: core.utils có thể match core/utils/__init__.py hoặc core/utils.py
        parts = import_name.split(".")
        
        # Try as file path trực tiếp
        for i in range(len(parts), 0, -1):
            partial_module = ".".join(parts[:i])
            if partial_module in self._module_index:
                return self._module_index[partial_module]
        
        # 4. Search trong workspace theo path
        path_parts = import_name.replace(".", os.sep)
        
        # Try as .py file
        candidate = self.workspace_root / (path_parts + ".py")
        if candidate.exists():
            return candidate
        
        # Try as package với __init__.py
        candidate = self.workspace_root / path_parts / "__init__.py"
        if candidate.exists():
            return candidate.parent  # Return package dir
        
        return None
    
    def _resolve_python_relative(
        self, 
        import_name: str, 
        source_dir: Path
    ) -> Optional[Path]:
        """
        Resolve relative Python import.
        
        Examples:
        - .utils -> source_dir/utils.py
        - ..models -> source_dir/../models.py
        
        Args:
            import_name: Relative import (bắt đầu với .)
            source_dir: Directory của file đang import
        
        Returns:
            Resolved Path hoặc None
        """
        # Đếm số dấu . ở đầu
        dot_count = 0
        for char in import_name:
            if char == ".":
                dot_count += 1
            else:
                break
        
        # Phần còn lại sau các dấu .
        module_part = import_name[dot_count:]
        
        # Navigate up directories
        target_dir = source_dir
        for _ in range(dot_count - 1):  # -1 vì . đầu tiên = current dir
            target_dir = target_dir.parent
        
        if not module_part:
            # from . import something - chỉ reference current package
            return None
        
        # Chuyển đổi module path thành file path
        path_parts = module_part.replace(".", os.sep)
        
        # Try as .py file
        candidate = target_dir / (path_parts + ".py")
        if candidate.exists():
            return candidate
        
        # Try as package với __init__.py
        candidate = target_dir / path_parts / "__init__.py"
        if candidate.exists():
            return candidate
        
        return None
    
    def _resolve_js_import(
        self, 
        import_path: str, 
        source_dir: Path
    ) -> Optional[Path]:
        """
        Resolve JavaScript/TypeScript import thành file path.
        
        Hỗ trợ:
        1. Relative imports: ./module, ../module
        2. Path aliases từ tsconfig.json/jsconfig.json: @/components, @utils
        
        Node modules (lodash, react, etc.) không được resolve.
        
        Args:
            import_path: Import path (relative hoặc absolute)
            source_dir: Directory của file đang import
        
        Returns:
            Resolved Path hoặc None
        """
        possible_extensions = [".ts", ".tsx", ".js", ".jsx", ""]
        
        # 1. Handle relative imports
        if import_path.startswith("."):
            for ext in possible_extensions:
                candidate = (source_dir / (import_path + ext)).resolve()
                if candidate.exists() and candidate.is_file():
                    return candidate
                
                # Try index file
                if ext == "":
                    for index_name in ["index.ts", "index.tsx", "index.js", "index.jsx"]:
                        index_candidate = (source_dir / import_path / index_name).resolve()
                        if index_candidate.exists():
                            return index_candidate
            return None
        
        # 2. Handle path aliases (từ tsconfig.json/jsconfig.json)
        if self._ts_paths and self._ts_base_url:
            resolved = self._resolve_ts_alias(import_path, possible_extensions)
            if resolved:
                return resolved
        
        # 3. Non-relative, non-alias imports (node_modules) - skip
        return None
    
    def _resolve_ts_alias(
        self, 
        import_path: str, 
        extensions: list
    ) -> Optional[Path]:
        """
        Resolve import path sử dụng path aliases từ tsconfig.json.
        
        Ví dụ:
        - "@/components/Button" với paths {"@/*": ["src/*"]} 
          -> src/components/Button.tsx
        
        Args:
            import_path: Import path (e.g., "@/components/Button")
            extensions: List of extensions to try
        
        Returns:
            Resolved Path hoặc None
        """
        import fnmatch
        
        for alias_pattern, target_paths in self._ts_paths.items():
            # Chuyển đổi TypeScript pattern sang glob-style
            # "@/*" -> "@/*" (giữ nguyên cho fnmatch)
            # Kiểm tra xem import_path có match pattern không
            
            # Tạo regex-like check
            if alias_pattern.endswith("/*"):
                # Wildcard pattern: @/* matches @/anything
                prefix = alias_pattern[:-2]  # Bỏ /*
                if import_path.startswith(prefix + "/"):
                    # Match! Extract phần sau prefix
                    suffix = import_path[len(prefix) + 1:]
                    
                    # Try each target path
                    for target in target_paths:
                        if target.endswith("/*"):
                            target_prefix = target[:-2]
                        else:
                            target_prefix = target
                        
                        # Build full path
                        if self._ts_base_url:
                            base = self._ts_base_url / target_prefix / suffix
                        else:
                            base = self.workspace_root / target_prefix / suffix
                        
                        # Try with extensions
                        for ext in extensions:
                            candidate = Path(str(base) + ext)
                            if candidate.exists() and candidate.is_file():
                                return candidate
                            
                            # Try index file
                            if ext == "":
                                for index_name in ["index.ts", "index.tsx", "index.js", "index.jsx"]:
                                    index_candidate = base / index_name
                                    if index_candidate.exists():
                                        return index_candidate
            
            elif alias_pattern == import_path:
                # Exact match (không có wildcard)
                for target in target_paths:
                    if self._ts_base_url:
                        candidate = self._ts_base_url / target
                    else:
                        candidate = self.workspace_root / target
                    
                    for ext in extensions:
                        full_candidate = Path(str(candidate) + ext)
                        if full_candidate.exists() and full_candidate.is_file():
                            return full_candidate
        
        return None
    
    def _get_lang_name(self, ext: str) -> str:
        """
        Map file extension sang language name cho query lookup.
        
        Args:
            ext: File extension (không có dấu .)
        
        Returns:
            Language name hoặc empty string
        """
        ext_to_lang = {
            "py": "python",
            "pyw": "python",
            "js": "javascript",
            "jsx": "javascript",
            "mjs": "javascript",
            "cjs": "javascript",
            "ts": "typescript",
            "tsx": "typescript",
            "mts": "typescript",
            "cts": "typescript",
        }
        return ext_to_lang.get(ext.lower(), "")


def get_related_files_for_selection(
    workspace_root: Path,
    tree: Optional[TreeItem],
    selected_file: Path,
    max_depth: int = 1
) -> Set[Path]:
    """
    Convenience function để lấy related files cho một file đã chọn.
    
    Tạo DependencyResolver, build index, và resolve imports.
    
    Args:
        workspace_root: Root path của workspace
        tree: TreeItem root của file tree
        selected_file: File cần tìm related files
        max_depth: Số cấp đệ quy (default: 1)
    
    Returns:
        Set of related file paths
    """
    resolver = DependencyResolver(workspace_root)
    resolver.build_file_index(tree)
    return resolver.get_related_files(selected_file, max_depth)
