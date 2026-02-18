"""
Real-world performance test với paas-k3s project.

Test:
1. Parse nhiều files trong project
2. Measure total time với/không có relationships
3. Test cache effectiveness
"""

import pytest
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.smart_context.parser import smart_parse, _RELATIONSHIPS_CACHE  # noqa: E402
from core.prompt_generator import generate_smart_context  # noqa: E402


# Project path
PAAS_K3S_PATH = Path("/media/data/Apps/paas-k3s")


def get_python_files(project_path: Path, max_files: int = 20) -> list[Path]:
    """Get Python files từ project."""
    if not project_path.exists():
        return []

    files = []
    for f in project_path.rglob("*.py"):
        if "node_modules" in str(f) or ".venv" in str(f) or "__pycache__" in str(f):
            continue
        files.append(f)
        if len(files) >= max_files:
            break
    return files


def test_paas_k3s_performance():
    """Test performance với real project."""
    files = get_python_files(PAAS_K3S_PATH, max_files=20)

    if not files:
        pytest.skip(f"Project not found: {PAAS_K3S_PATH}")

    print(f"\n{'=' * 60}")
    print(f"Testing with {len(files)} Python files from paas-k3s")
    print(f"{'=' * 60}")

    # Clear cache
    _RELATIONSHIPS_CACHE.clear()

    # Test 1: Parse WITHOUT relationships
    print("\n[1] Parsing WITHOUT relationships...")
    start = time.perf_counter()
    for f in files:
        try:
            content = f.read_text()
            smart_parse(str(f), content, include_relationships=False)
        except Exception:
            pass
    time_without = time.perf_counter() - start
    print(
        f"    Time: {time_without:.2f}s ({time_without * 1000 / len(files):.1f}ms per file)"
    )

    # Clear cache
    _RELATIONSHIPS_CACHE.clear()

    # Test 2: Parse WITH relationships (first time - no cache)
    print("\n[2] Parsing WITH relationships (cache miss)...")
    start = time.perf_counter()
    for f in files:
        try:
            content = f.read_text()
            smart_parse(str(f), content, include_relationships=True)
        except Exception:
            pass
    time_with_nocache = time.perf_counter() - start
    print(
        f"    Time: {time_with_nocache:.2f}s ({time_with_nocache * 1000 / len(files):.1f}ms per file)"
    )
    print(f"    Overhead: {((time_with_nocache / time_without - 1) * 100):.1f}%")
    print(f"    Cache entries: {len(_RELATIONSHIPS_CACHE)}")

    # Test 3: Parse WITH relationships (second time - cache hit)
    print("\n[3] Parsing WITH relationships (cache hit)...")
    start = time.perf_counter()
    for f in files:
        try:
            content = f.read_text()
            smart_parse(str(f), content, include_relationships=True)
        except Exception:
            pass
    time_with_cache = time.perf_counter() - start
    print(
        f"    Time: {time_with_cache:.2f}s ({time_with_cache * 1000 / len(files):.1f}ms per file)"
    )
    print(f"    Speedup: {time_with_nocache / time_with_cache:.1f}x faster")

    # Test 4: Parallel processing với generate_smart_context
    print("\n[4] Testing parallel processing (>5 files)...")
    _RELATIONSHIPS_CACHE.clear()
    file_paths = {str(f) for f in files}

    start = time.perf_counter()
    result = generate_smart_context(file_paths, include_relationships=True)
    time_parallel = time.perf_counter() - start
    print(f"    Time: {time_parallel:.2f}s")
    print(f"    Output size: {len(result)} chars")

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"Without relationships:     {time_without:.2f}s")
    print(
        f"With relationships (cold): {time_with_nocache:.2f}s ({((time_with_nocache / time_without - 1) * 100):.1f}% overhead)"
    )
    print(
        f"With relationships (warm): {time_with_cache:.2f}s ({time_with_nocache / time_with_cache:.1f}x speedup)"
    )
    print(f"Parallel processing:       {time_parallel:.2f}s")
    print(f"{'=' * 60}")

    # Assertions
    assert time_with_cache < time_with_nocache, "Cache should improve performance"
    assert len(_RELATIONSHIPS_CACHE) > 0, "Cache should have entries"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
