#!/usr/bin/env python3
"""
Demo script để test CodeMaps integration với Smart Copy

Chạy: python3 demo_codemaps_integration.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Test code
TEST_PYTHON_CODE = """
class Calculator:
    def __init__(self):
        self.result = 0
    
    def add(self, a, b):
        result = self._compute(a, b, '+')
        self.log_operation('add', result)
        return result
    
    def subtract(self, a, b):
        result = self._compute(a, b, '-')
        self.log_operation('subtract', result)
        return result
    
    def _compute(self, a, b, op):
        if op == '+':
            return a + b
        elif op == '-':
            return a - b
        return 0
    
    def log_operation(self, op_name, result):
        print(f"{op_name}: {result}")

class ScientificCalculator(Calculator):
    def power(self, a, b):
        return a ** b
"""


def test_smart_parse_without_relationships():
    """Test Smart Parse mode cũ (không có relationships)."""
    print("=" * 80)
    print("TEST 1: Smart Parse WITHOUT Relationships (Backward Compatible)")
    print("=" * 80)

    from core.smart_context.parser import smart_parse

    result = smart_parse("test.py", TEST_PYTHON_CODE, include_relationships=False)

    if result:
        print("\n✓ Smart Parse successful!")
        print("\nOutput:")
        print("-" * 80)
        print(result)
        print("-" * 80)
    else:
        print("\n✗ Smart Parse failed")


def test_smart_parse_with_relationships():
    """Test Smart Parse mode mới (có relationships)."""
    print("\n\n" + "=" * 80)
    print("TEST 2: Smart Parse WITH Relationships (CodeMaps Enabled)")
    print("=" * 80)

    from core.smart_context.parser import smart_parse

    result = smart_parse("test.py", TEST_PYTHON_CODE, include_relationships=True)

    if result:
        print("\n✓ Smart Parse with relationships successful!")
        print("\nOutput:")
        print("-" * 80)
        print(result)
        print("-" * 80)

        # Verify relationships section exists
        if "## Relationships" in result:
            print("\n✓ Relationships section found!")
        else:
            print(
                "\n⚠ Relationships section NOT found (might be no relationships detected)"
            )
    else:
        print("\n✗ Smart Parse failed")


def test_direct_relationship_extraction():
    """Test direct relationship extraction."""
    print("\n\n" + "=" * 80)
    print("TEST 3: Direct Relationship Extraction")
    print("=" * 80)

    from core.codemaps.relationship_extractor import extract_relationships
    from core.codemaps.types import RelationshipKind

    relationships = extract_relationships("test.py", TEST_PYTHON_CODE)

    print(f"\nTotal relationships extracted: {len(relationships)}")

    # Group by kind
    by_kind = {}
    for r in relationships:
        kind = r.kind.value
        if kind not in by_kind:
            by_kind[kind] = []
        by_kind[kind].append(f"{r.source} -> {r.target} (line {r.source_line})")

    for kind, rels in by_kind.items():
        print(f"\n{kind.upper()}:")
        for rel in rels:
            print(f"  - {rel}")


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("CodeMaps Integration Demo")
    print("=" * 80)

    try:
        test_smart_parse_without_relationships()
        test_smart_parse_with_relationships()
        test_direct_relationship_extraction()

        print("\n\n" + "=" * 80)
        print("ALL TESTS COMPLETED ✓")
        print("=" * 80)
        print("\nNext Steps:")
        print("1. Verify relationships are correctly extracted")
        print("2. Add UI toggle in ContextView for 'Include Relationships'")
        print("3. Test with real codebase files")

    except Exception as e:
        print(f"\n\n✗ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
