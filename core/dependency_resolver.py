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
    
    # JavaScript/TypeScript (Phase 2 - sẽ implement sau)
    "javascript": """
        ; ES6 import: import x from 'module'
        (import_statement
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
    
    def build_file_index(self, tree: Optional[TreeItem]) -> None:
        """
        Build index từ TreeItem để hỗ trợ resolve imports.
        
        Index bao gồm:
        - filename -> full_path mapping
        - module_name -> file_path mapping (cho Python modules)
        
        Args:
            tree: TreeItem root của file tree
        """
        if not tree:
            return
        
        self._file_index.clear()
        self._module_index.clear()
        self._index_recursive(tree)
    
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
        
        Note: MVP - chỉ handle relative imports.
        Node modules và aliases chưa được hỗ trợ.
        
        Args:
            import_path: Import path (relative hoặc absolute)
            source_dir: Directory của file đang import
        
        Returns:
            Resolved Path hoặc None
        """
        # Skip node_modules imports
        if not import_path.startswith("."):
            return None
        
        # Handle relative imports
        possible_extensions = [".ts", ".tsx", ".js", ".jsx", ""]
        
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
