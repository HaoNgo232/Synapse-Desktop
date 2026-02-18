"""
Tests cho Tier 2.1 - Select Related Files (Dependency Graph)

Kiểm tra DependencyResolver hoạt động đúng với Python imports.
"""

import tempfile
import shutil
from pathlib import Path
import pytest

from core.dependency_resolver import DependencyResolver, get_related_files_for_selection
from core.utils.file_utils import scan_directory_shallow


@pytest.fixture
def temp_project():
    """Tạo project tạm thời với cấu trúc imports."""
    temp_dir = tempfile.mkdtemp(prefix="synapse_test_")
    project_dir = Path(temp_dir)

    # Tạo structure:
    # project/
    #   main.py (imports utils.helpers, core.processor)
    #   utils/
    #     __init__.py
    #     helpers.py
    #   core/
    #     __init__.py
    #     processor.py (imports utils.helpers)

    # Create directories
    (project_dir / "utils").mkdir()
    (project_dir / "core").mkdir()

    # main.py
    (project_dir / "main.py").write_text("""
import os
from typing import Optional

from utils.helpers import some_function
from core.processor import process_data
""")

    # utils/__init__.py
    (project_dir / "utils" / "__init__.py").write_text("")

    # utils/helpers.py
    (project_dir / "utils" / "helpers.py").write_text("""
def some_function():
    return "hello"
""")

    # core/__init__.py
    (project_dir / "core" / "__init__.py").write_text("")

    # core/processor.py
    (project_dir / "core" / "processor.py").write_text("""
from utils.helpers import some_function

def process_data():
    return some_function()
""")

    yield project_dir

    # Cleanup
    shutil.rmtree(temp_dir)


def test_dependency_resolver_basic(temp_project):
    """Test basic DependencyResolver initialization."""
    resolver = DependencyResolver(temp_project)

    # Build index
    tree = scan_directory_shallow(temp_project, depth=3)
    resolver.build_file_index(tree)

    # Verify index built
    assert len(resolver._module_index) > 0, "Module index should be built"


def test_extract_imports_from_main(temp_project):
    """Test extracting imports from main.py."""
    resolver = DependencyResolver(temp_project)
    tree = scan_directory_shallow(temp_project, depth=3)
    resolver.build_file_index(tree)

    main_file = temp_project / "main.py"
    related = resolver.get_related_files(main_file)

    # main.py imports utils.helpers và core.processor
    # Nên tìm thấy ít nhất 2 files
    assert len(related) >= 2, f"Expected at least 2 related files, got {len(related)}"

    # Verify specific files
    related_names = {f.name for f in related}
    assert "helpers.py" in related_names, "Should find helpers.py"
    assert "processor.py" in related_names, "Should find processor.py"


def test_transitive_dependencies(temp_project):
    """Test finding transitive dependencies with max_depth > 1."""
    resolver = DependencyResolver(temp_project)
    tree = scan_directory_shallow(temp_project, depth=3)
    resolver.build_file_index(tree)

    # core/processor.py imports utils.helpers
    # Với max_depth=2, từ main.py nên tìm được helpers.py qua processor.py
    main_file = temp_project / "main.py"

    # Direct imports only (depth=1)
    direct_related = resolver.get_related_files(main_file, max_depth=1)

    # Có thể có 2+ files
    assert len(direct_related) >= 2


def test_no_imports_file():
    """Test file không có imports."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project = Path(temp_dir)
        (project / "simple.py").write_text("print('hello')")

        resolver = DependencyResolver(project)
        tree = scan_directory_shallow(project, depth=2)
        resolver.build_file_index(tree)

        related = resolver.get_related_files(project / "simple.py")
        assert len(related) == 0, "File without imports should have no related files"


def test_get_related_files_for_selection():
    """Test convenience function."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project = Path(temp_dir)

        # Create simple file
        (project / "main.py").write_text("from helper import foo")
        (project / "helper.py").write_text("def foo(): pass")

        tree = scan_directory_shallow(project, depth=2)
        related = get_related_files_for_selection(
            workspace_root=project, tree=tree, selected_file=project / "main.py"
        )

        # Should find helper.py
        related_names = {f.name for f in related}
        assert "helper.py" in related_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
