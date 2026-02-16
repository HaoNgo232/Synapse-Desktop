"""
Test cache optimization.
"""

import pytest
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.smart_context.parser import smart_parse, _RELATIONSHIPS_CACHE


def test_cache_speedup():
    """Test that cache provides speedup on repeated calls."""
    test_code = """
def foo():
    bar()
    baz()
    
def bar():
    qux()
    
def baz():
    pass
    
def qux():
    pass
"""

    # Clear cache
    _RELATIONSHIPS_CACHE.clear()

    # First call - cache miss
    start = time.perf_counter()
    result1 = smart_parse("test_cache.py", test_code, include_relationships=True)
    time1 = time.perf_counter() - start

    # Second call - should hit cache
    start = time.perf_counter()
    result2 = smart_parse("test_cache.py", test_code, include_relationships=True)
    time2 = time.perf_counter() - start

    # Results should be identical
    assert result1 == result2, "Cache should return same result"

    # Second call should be faster (cache hit)
    print(f"\n  First call:  {time1 * 1000:.2f}ms")
    print(f"  Second call: {time2 * 1000:.2f}ms")
    print(f"  Speedup: {time1 / time2:.1f}x")

    # Cache should have entry
    assert len(_RELATIONSHIPS_CACHE) > 0, "Cache should have entries"

    # Second call should be significantly faster
    assert time2 < time1, "Cache hit should be faster"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
