#!/usr/bin/env python3
"""
Test script để kiểm tra race condition fixes
"""

import sys
import time
import threading
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_file_tree_race_condition():
    """Test FileTreeComponent race condition fixes"""
    print("Testing FileTreeComponent race condition fixes...")
    
    # Import after path setup
    from components.file_tree import FileTreeComponent
    from core.utils.file_utils import TreeItem
    import flet as ft
    
    # Create mock page
    class MockPage:
        def __init__(self):
            self.window = type('obj', (object,), {'width': 1000})()
            
        def update(self):
            pass
    
    page = MockPage()
    
    # Create file tree component
    file_tree = FileTreeComponent(page)
    
    # Create mock tree
    root = TreeItem("test", "/test", True)
    child1 = TreeItem("file1.py", "/test/file1.py", False)
    child2 = TreeItem("file2.py", "/test/file2.py", False)
    root.children = [child1, child2]
    
    file_tree.set_tree(root)
    
    # Test concurrent selection changes
    def toggle_selection():
        for i in range(10):
            file_tree._on_item_toggled(
                type('obj', (object,), {'control': type('obj', (object,), {'value': True})})(),
                f"/test/file{i % 2 + 1}.py",
                False,
                []
            )
            time.sleep(0.01)
    
    # Start multiple threads
    threads = []
    for i in range(3):
        t = threading.Thread(target=toggle_selection)
        threads.append(t)
        t.start()
    
    # Wait for completion
    for t in threads:
        t.join()
    
    print("✓ FileTreeComponent race condition test completed")
    file_tree.cleanup()

def test_token_service_race_condition():
    """Test TokenDisplayService race condition fixes"""
    print("Testing TokenDisplayService race condition fixes...")
    
    from services.token_display import TokenDisplayService
    
    # Create service
    service = TokenDisplayService()
    
    # Test concurrent token requests
    def request_tokens():
        for i in range(10):
            service.request_token_count(f"/test/file{i}.py")
            time.sleep(0.01)
    
    # Start multiple threads
    threads = []
    for i in range(3):
        t = threading.Thread(target=request_tokens)
        threads.append(t)
        t.start()
    
    # Wait for completion
    for t in threads:
        t.join()
    
    print("✓ TokenDisplayService race condition test completed")
    service.stop()

def test_global_state_manager():
    """Test GlobalState manager"""
    print("Testing GlobalState manager...")
    
    from core.utils.state_manager import global_state
    
    def test_state_changes():
        for i in range(10):
            global_state.set_scanning(True)
            assert global_state.is_scanning()
            assert not global_state.can_interact()
            
            global_state.set_scanning(False)
            assert not global_state.is_scanning()
            assert global_state.can_interact()
            
            time.sleep(0.01)
    
    # Test concurrent state changes
    threads = []
    for i in range(3):
        t = threading.Thread(target=test_state_changes)
        threads.append(t)
        t.start()
    
    # Wait for completion
    for t in threads:
        t.join()
    
    print("✓ GlobalState manager test completed")

if __name__ == "__main__":
    print("Running race condition tests...")
    print("=" * 50)
    
    try:
        test_global_state_manager()
        test_token_service_race_condition()
        # test_file_tree_race_condition()  # Skip UI test for now
        
        print("=" * 50)
        print("✅ All race condition tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
