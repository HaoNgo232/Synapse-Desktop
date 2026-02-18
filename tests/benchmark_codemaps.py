"""
Benchmark script để đo performance của CodeMaps optimizations.

Chạy: python tests/benchmark_codemaps.py
"""

import time
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.smart_context.parser import smart_parse  # noqa: E402
from core.codemaps.relationship_extractor import (  # noqa: E402
    _build_function_boundaries_map,
    _find_enclosing_function_fast,
)
from core.smart_context.loader import get_language  # noqa: E402
from tree_sitter import Parser  # noqa: E402


def generate_large_python_code(num_functions: int = 50) -> str:
    """
    Generate Python code lớn để benchmark.
    """
    lines = ["# Auto-generated benchmark code\n"]

    for i in range(num_functions):
        lines.append(f'''
def function_{i}(arg1, arg2):
    """Docstring for function_{i}."""
    result = helper_{i}(arg1)
    process_{i}(result, arg2)
    return result
''')

    # Add a class with inheritance
    lines.append('''
class BaseClass:
    """Base class."""
    def base_method(self):
        pass

class DerivedClass(BaseClass):
    """Derived class."""
    def derived_method(self):
        self.base_method()
        function_0()
''')

    return "\n".join(lines)


def benchmark_smart_parse(content: str, iterations: int = 10) -> dict:
    """
    Benchmark smart_parse với và không có relationships.
    """
    file_path = "benchmark.py"

    # Warm up
    smart_parse(file_path, content, include_relationships=False)
    smart_parse(file_path, content, include_relationships=True)

    # Benchmark WITHOUT relationships
    start = time.perf_counter()
    for _ in range(iterations):
        smart_parse(file_path, content, include_relationships=False)
    without_time = (time.perf_counter() - start) / iterations

    # Benchmark WITH relationships
    start = time.perf_counter()
    for _ in range(iterations):
        smart_parse(file_path, content, include_relationships=True)
    with_time = (time.perf_counter() - start) / iterations

    return {
        "without_relationships_ms": without_time * 1000,
        "with_relationships_ms": with_time * 1000,
        "overhead_ms": (with_time - without_time) * 1000,
        "overhead_percent": ((with_time / without_time) - 1) * 100
        if without_time > 0
        else 0,
    }


def benchmark_tree_reuse(content: str, iterations: int = 10) -> dict:
    """
    Benchmark tree reuse optimization.
    """
    _ = "benchmark.py"  # noqa: F841 - used for documentation only
    language = get_language("py")

    # Warm up
    parser = Parser(language)
    parser.parse(bytes(content, "utf-8"))

    # WITHOUT tree reuse (old way - parse twice)
    start = time.perf_counter()
    for _ in range(iterations):
        parser1 = Parser(language)
        parser1.parse(bytes(content, "utf-8"))
        # Simulate second parse in extract_relationships
        parser2 = Parser(language)
        parser2.parse(bytes(content, "utf-8"))
    old_way_time = (time.perf_counter() - start) / iterations

    # WITH tree reuse (new way - parse once)
    start = time.perf_counter()
    for _ in range(iterations):
        parser_new = Parser(language)
        parser_new.parse(bytes(content, "utf-8"))
        # Reuse tree - no second parse
    new_way_time = (time.perf_counter() - start) / iterations

    return {
        "old_way_ms": old_way_time * 1000,
        "new_way_ms": new_way_time * 1000,
        "improvement_percent": ((old_way_time / new_way_time) - 1) * 100
        if new_way_time > 0
        else 0,
    }


def benchmark_boundaries_map(content: str, iterations: int = 10) -> dict:
    """
    Benchmark function boundaries map optimization.
    """
    language = get_language("py")
    parser = Parser(language)
    tree = parser.parse(bytes(content, "utf-8"))
    lines = content.split("\n")

    # Build boundaries map
    boundaries_map = _build_function_boundaries_map(tree.root_node, lines)

    # Simulate 100 lookups
    num_lookups = 100
    test_lines = list(range(0, len(lines), max(1, len(lines) // num_lookups)))[
        :num_lookups
    ]

    # Fast lookup
    start = time.perf_counter()
    for _ in range(iterations):
        for line in test_lines:
            _find_enclosing_function_fast(line, boundaries_map)
    fast_time = (time.perf_counter() - start) / iterations

    return {
        "boundaries_count": len(boundaries_map),
        "lookups_per_iteration": len(test_lines),
        "fast_lookup_ms": fast_time * 1000,
    }


def run_benchmarks():
    """
    Run tất cả benchmarks.
    """
    print("=" * 60)
    print("CodeMaps Performance Benchmark")
    print("=" * 60)

    # Generate test code
    print("\n[1] Generating test code...")
    content = generate_large_python_code(50)
    print(f"    Generated {len(content)} chars, {len(content.splitlines())} lines")

    # Benchmark smart_parse
    print("\n[2] Benchmarking smart_parse()...")
    results = benchmark_smart_parse(content)
    print(f"    Without relationships: {results['without_relationships_ms']:.2f}ms")
    print(f"    With relationships:    {results['with_relationships_ms']:.2f}ms")
    print(
        f"    Overhead:              {results['overhead_ms']:.2f}ms ({results['overhead_percent']:.1f}%)"
    )

    # Benchmark tree reuse
    print("\n[3] Benchmarking tree reuse optimization...")
    results = benchmark_tree_reuse(content)
    print(f"    Old way (2 parses):    {results['old_way_ms']:.2f}ms")
    print(f"    New way (1 parse):     {results['new_way_ms']:.2f}ms")
    print(f"    Improvement:           {results['improvement_percent']:.1f}% faster")

    # Benchmark boundaries map
    print("\n[4] Benchmarking boundaries map optimization...")
    results = benchmark_boundaries_map(content)
    print(f"    Function boundaries:   {results['boundaries_count']}")
    print(f"    Lookups per iteration: {results['lookups_per_iteration']}")
    print(f"    Fast lookup time:      {results['fast_lookup_ms']:.2f}ms")

    # Test with real file
    print("\n[5] Testing with real file (main.py)...")
    main_py = project_root / "main.py"
    if main_py.exists():
        real_content = main_py.read_text()
        results = benchmark_smart_parse(real_content, iterations=5)
        print(f"    File size:             {len(real_content)} chars")
        print(f"    Without relationships: {results['without_relationships_ms']:.2f}ms")
        print(f"    With relationships:    {results['with_relationships_ms']:.2f}ms")
        print(
            f"    Overhead:              {results['overhead_ms']:.2f}ms ({results['overhead_percent']:.1f}%)"
        )

    print("\n" + "=" * 60)
    print("Benchmark complete!")
    print("=" * 60)


if __name__ == "__main__":
    run_benchmarks()
