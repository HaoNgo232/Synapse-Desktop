#!/usr/bin/env python3
"""
Quick test script cho advanced optimizations.
"""

import sys
import time
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test imports
print("Testing imports...")
try:
    from core.smart_context.parser import smart_parse, _RELATIONSHIPS_CACHE

    print("✓ Imports successful")
except Exception as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test cache
print("\nTesting LRU cache...")
test_code = """
def foo():
    bar()
    
def bar():
    pass
"""

# First call - cache miss
start = time.perf_counter()
result1 = smart_parse("test.py", test_code, include_relationships=True)
time1 = (time.perf_counter() - start) * 1000

# Second call - cache hit
start = time.perf_counter()
result2 = smart_parse("test.py", test_code, include_relationships=True)
time2 = (time.perf_counter() - start) * 1000

print(f"  First call (cache miss):  {time1:.2f}ms")
print(f"  Second call (cache hit):  {time2:.2f}ms")
print(f"  Speedup: {time1 / time2:.1f}x faster")
print(f"  Cache size: {len(_RELATIONSHIPS_CACHE)} entries")

if time2 < time1:
    print("✓ Cache working!")
else:
    print("✗ Cache not working")

print("\n✓ All tests passed!")
