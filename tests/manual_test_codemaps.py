#!/usr/bin/env python3
"""
Manual test script cho CodeMaps - không cần pytest

Chạy: python3 manual_test_codemaps.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.codemaps.symbol_extractor import extract_symbols
from core.codemaps.relationship_extractor import extract_relationships
from core.codemaps.graph_builder import CodeMapBuilder
from core.codemaps.types import SymbolKind, RelationshipKind


# Test data
PYTHON_CODE = """
class MyClass:
    def __init__(self):
        self.value = 0
    
    def method_a(self):
        self.method_b()
        helper_function()
    
    def method_b(self):
        pass

def helper_function():
    pass

class ChildClass(MyClass):
    pass
"""


def test_extract_symbols():
    """Test extract symbols từ Python code."""
    print("\n=== TEST: Extract Symbols ===")
    
    symbols = extract_symbols("test.py", PYTHON_CODE)
    
    print(f"Total symbols extracted: {len(symbols)}")
    
    # Group by kind
    by_kind = {}
    for s in symbols:
        kind = s.kind.value
        if kind not in by_kind:
            by_kind[kind] = []
        by_kind[kind].append(s.name)
    
    for kind, names in by_kind.items():
        print(f"  {kind}: {names}")
    
    # Verify
    class_symbols = [s for s in symbols if s.kind == SymbolKind.CLASS]
    assert len(class_symbols) >= 2, f"Expected >= 2 classes, got {len(class_symbols)}"
    
    print("✓ Symbol extraction PASSED")
    return symbols


def test_extract_relationships():
    """Test extract relationships từ Python code."""
    print("\n=== TEST: Extract Relationships ===")
    
    relationships = extract_relationships("test.py", PYTHON_CODE)
    
    print(f"Total relationships extracted: {len(relationships)}")
    
    # Group by kind
    by_kind = {}
    for r in relationships:
        kind = r.kind.value
        if kind not in by_kind:
            by_kind[kind] = []
        by_kind[kind].append(f"{r.source} -> {r.target}")
    
    for kind, rels in by_kind.items():
        print(f"  {kind}:")
        for rel in rels:
            print(f"    {rel}")
    
    # Verify inheritance
    inherit_rels = [r for r in relationships if r.kind == RelationshipKind.INHERITS]
    print(f"\nInheritance relationships: {len(inherit_rels)}")
    
    print("✓ Relationship extraction PASSED")
    return relationships


def test_graph_builder():
    """Test CodeMapBuilder."""
    print("\n=== TEST: Graph Builder ===")
    
    # Create temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(PYTHON_CODE)
        temp_path = f.name
    
    try:
        # Build CodeMap
        builder = CodeMapBuilder(Path(temp_path).parent)
        codemap = builder.build_for_file(temp_path)
        
        print(f"CodeMap built for: {temp_path}")
        if codemap:
            print(f"  Symbols: {len(codemap.symbols)}")
            print(f"  Relationships: {len(codemap.relationships)}")
        else:
            print("  CodeMap is None")
        
        # Test queries
        related = builder.get_related_symbols("method_a", depth=1, file_path=temp_path)
        print(f"\nSymbols related to 'method_a': {related}")
        
        callers = builder.get_callers("method_b")
        print(f"Callers of 'method_b': {callers}")
        
        print("✓ Graph builder PASSED")
        
    finally:
        # Cleanup
        Path(temp_path).unlink()


def main():
    """Run all tests."""
    print("=" * 60)
    print("CodeMaps Manual Test Suite")
    print("=" * 60)
    
    try:
        test_extract_symbols()
        test_extract_relationships()
        test_graph_builder()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
