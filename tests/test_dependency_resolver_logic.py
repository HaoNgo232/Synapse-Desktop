"""
Unit/Integration tests cho logic extract và resolve của DependencyResolver.

File này kiểm thử:
1. Trích xuất imports Python bằng Tree-sitter.
2. Resolve imports Python (bao gồm absolute và relative).
3. Resolve imports JavaScript/TypeScript (bao gồm relative và tsconfig path aliases).
"""

from pathlib import Path
from typing import Set, Dict, List, Optional
import pytest
import json

from application.services.dependency_resolver import DependencyResolver
from domain.smart_context.loader import get_language


class TestDependencyResolverLogic:
    """Kiểm thử các hàm trích xuất và resolve module cụ thể trong DependencyResolver."""

    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Path:
        """Tạo workspace tạm thời cho quá trình test."""
        return tmp_path

    @pytest.fixture
    def resolver(self, workspace: Path) -> DependencyResolver:
        """Khởi tạo instance DependencyResolver với workspace tạm thời."""
        return DependencyResolver(workspace)

    def test_extract_python_imports(self, resolver: DependencyResolver, workspace: Path) -> None:
        """Kiểm tra việc trích xuất các import Python từ code nguồn."""
        code_content: str = (
            "import os\n"
            "import sys\n"
            "from datetime import datetime\n"
            "from .relative_mod import func\n"
            "from ..parent_mod import ClassName\n"
        )
        file_path: Path = workspace / "test_file.py"
        file_path.write_text(code_content, encoding="utf-8")

        ext: str = "py"
        lang_name: str = "python"
        language = get_language(ext)
        assert language is not None

        imports: Set[str] = resolver._extract_imports(language, code_content, lang_name, file_path)

        # Kiểm tra xem có trích xuất đúng các module name hay không
        assert "os" in imports
        assert "sys" in imports
        assert "datetime" in imports
        assert ".relative_mod" in imports
        assert "..parent_mod" in imports

    def test_resolve_python_relative_imports(self, resolver: DependencyResolver, workspace: Path) -> None:
        """Kiểm tra việc resolve relative Python imports thành file path thực tế."""
        # Tạo cấu trúc thư mục:
        # workspace/
        #   subpkg/
        #     __init__.py
        #     main.py
        #     utils.py
        #   models.py
        subpkg = workspace / "subpkg"
        subpkg.mkdir()
        (subpkg / "__init__.py").write_text("", encoding="utf-8")

        main_file: Path = subpkg / "main.py"
        utils_file: Path = subpkg / "utils.py"
        utils_file.write_text("def helper(): pass", encoding="utf-8")

        models_file: Path = workspace / "models.py"
        models_file.write_text("class User: pass", encoding="utf-8")

        # Load file index
        resolver.build_file_index_from_disk(workspace)

        # 1. Test relative import cùng thư mục: `.utils` từ `subpkg/main.py`
        resolved_utils: Optional[Path] = resolver._resolve_python_relative(".utils", subpkg)
        assert resolved_utils == utils_file

        # 2. Test relative import thư mục cha: `..models` từ `subpkg/main.py`
        resolved_models: Optional[Path] = resolver._resolve_python_relative("..models", subpkg)
        assert resolved_models == models_file

    def test_resolve_js_relative_imports(self, resolver: DependencyResolver, workspace: Path) -> None:
        """Kiểm tra việc resolve relative imports trong JavaScript/TypeScript."""
        src_dir = workspace / "src"
        src_dir.mkdir()

        main_file: Path = src_dir / "index.ts"
        helper_file: Path = src_dir / "helper.ts"
        helper_file.write_text("export const run = () => {}", encoding="utf-8")

        # Thư mục con
        components_dir = src_dir / "components"
        components_dir.mkdir()
        button_file: Path = components_dir / "Button.tsx"
        button_file.write_text("export default Button", encoding="utf-8")

        # Test import helper từ index.ts: `./helper`
        resolved_helper: Optional[Path] = resolver.resolve_js_import("./helper", src_dir)
        assert resolved_helper == helper_file

        # Test import Button từ index.ts: `./components/Button`
        resolved_button: Optional[Path] = resolver.resolve_js_import("./components/Button", src_dir)
        assert resolved_button == button_file

    def test_resolve_js_tsconfig_aliases(self, resolver: DependencyResolver, workspace: Path) -> None:
        """Kiểm tra việc resolve import thông qua path aliases cấu hình trong tsconfig.json."""
        # Setup tsconfig.json
        tsconfig_content = {
            "compilerOptions": {
                "baseUrl": ".",
                "paths": {
                    "@/*": ["src/*"],
                    "@components/*": ["src/components/*"]
                }
            }
        }
        (workspace / "tsconfig.json").write_text(json.dumps(tsconfig_content), encoding="utf-8")

        # Cấu trúc thư mục
        src_dir = workspace / "src"
        src_dir.mkdir()
        components_dir = src_dir / "components"
        components_dir.mkdir()

        button_file: Path = components_dir / "Button.tsx"
        button_file.write_text("export default Button", encoding="utf-8")

        utils_dir = src_dir / "utils"
        utils_dir.mkdir()
        format_file: Path = utils_dir / "format.ts"
        format_file.write_text("export const fmt = () => {}", encoding="utf-8")

        # Build index
        resolver.build_file_index_from_disk(workspace)

        # Test resolve alias `@/utils/format`
        resolved_format: Optional[Path] = resolver.resolve_js_import("@/utils/format", src_dir)
        assert resolved_format == format_file

        # Test resolve alias `@components/Button`
        resolved_button: Optional[Path] = resolver.resolve_js_import("@components/Button", src_dir)
        assert resolved_button == button_file
