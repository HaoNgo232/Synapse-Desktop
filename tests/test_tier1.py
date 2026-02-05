#!/usr/bin/env python3
"""
Test script for Tier 1 implementations
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.utils.file_utils import TreeItem, get_cached_pathspec, clear_gitignore_cache
from components.file_tree import FileTreeComponent
from components.virtual_file_tree import VirtualFileTreeComponent


def create_test_tree(num_items: int) -> TreeItem:
    """Create a test tree with specified number of items"""
    root = TreeItem(
        label="test_root",
        path="/test",
        is_dir=True,
        children=[],
        is_loaded=True
    )
    
    # Add files to reach the desired count
    for i in range(num_items - 1):  # -1 because root counts as 1
        child = TreeItem(
            label=f"file_{i}.py",
            path=f"/test/file_{i}.py",
            is_dir=False,
            is_loaded=True
        )
        root.children.append(child)
    
    return root


def count_items(tree: TreeItem) -> int:
    """Count total items in tree"""
    if not tree:
        return 0
    
    count = 1
    if hasattr(tree, 'children') and tree.children:
        for child in tree.children:
            count += count_items(child)
    return count


def test_pathspec_caching():
    """Test PathSpec caching functionality"""
    print("🧪 Testing PathSpec caching...")
    
    root_path = Path('.')
    patterns = ['.git', 'node_modules', '*.pyc']
    
    # Clear cache first
    clear_gitignore_cache()
    
    # First call
    spec1 = get_cached_pathspec(root_path, patterns)
    
    # Second call - should be cached
    spec2 = get_cached_pathspec(root_path, patterns)
    
    if spec1 is spec2:
        print("✅ PathSpec caching works correctly")
        return True
    else:
        print("❌ PathSpec caching failed")
        return False


def test_component_selection():
    """Test component selection based on tree size"""
    print("🧪 Testing component selection logic...")
    
    # Mock page object
    class MockPage:
        pass
    
    page = MockPage()
    
    # Test small tree (should use FileTreeComponent)
    small_tree = create_test_tree(100)
    small_count = count_items(small_tree)
    print(f"Small tree items: {small_count}")
    
    # Test large tree (should use VirtualFileTreeComponent)  
    large_tree = create_test_tree(6000)
    large_count = count_items(large_tree)
    print(f"Large tree items: {large_count}")
    
    # Import ContextView to test the logic
    from views.context_view import ContextView
    
    # Create mock ContextView
    context_view = ContextView(page, lambda: Path('.'))
    
    # Test small tree component selection
    context_view.tree = small_tree
    small_component = context_view._create_file_tree_component()
    is_small_regular = isinstance(small_component, FileTreeComponent)
    
    # Test large tree component selection
    context_view.tree = large_tree
    large_component = context_view._create_file_tree_component()
    is_large_virtual = isinstance(large_component, VirtualFileTreeComponent)
    
    print(f"Small tree uses FileTreeComponent: {is_small_regular}")
    print(f"Large tree uses VirtualFileTreeComponent: {is_large_virtual}")
    
    assert is_small_regular, "Small tree should use FileTreeComponent"
    assert is_large_virtual, "Large tree should use VirtualFileTreeComponent"
    print("✅ Component selection works correctly")


def main():
    """Run all tests"""
    print("🚀 Running Tier 1 implementation tests...\n")
    
    tests = [
        test_pathspec_caching,
        test_component_selection,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()  # Add spacing between tests
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            print()
    
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All Tier 1 implementations working correctly!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
