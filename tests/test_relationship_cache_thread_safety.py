"""
Test thread safety of relationship cache under concurrent access.
"""

import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed


def test_relationship_cache_thread_safety(tmp_path):
    """Test concurrent access to relationship cache doesn't cause race conditions."""
    from core.smart_context.parser import _build_relationships_section

    # Create test files with different content
    test_files = []
    for i in range(20):
        content = f"""
def function_{i}_a():
    function_{i}_b()

def function_{i}_b():
    pass
"""
        test_files.append((f"test_{i}.py", content))

    # Concurrent access from multiple threads
    def process_file(file_path, content):
        # Call multiple times to trigger cache hits
        for _ in range(3):
            result = _build_relationships_section(file_path, content)
        return result

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(process_file, fp, content): fp for fp, content in test_files
        }

        results = []
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                pytest.fail(f"Thread raised exception: {e}")

    # All threads should complete without errors
    assert len(results) == len(test_files)


def test_relationship_cache_content_change():
    """Test cache invalidation when content changes."""
    from core.smart_context.parser import _build_relationships_section

    file_path = "test.py"

    # First content
    content1 = """
def foo():
    bar()
"""
    result1 = _build_relationships_section(file_path, content1)

    # Different content, same length (would collide with byte-length key)
    content2 = """
def baz():
    qux()
"""
    result2 = _build_relationships_section(file_path, content2)

    # Results should be different (hash-based key prevents collision)
    assert result1 != result2
