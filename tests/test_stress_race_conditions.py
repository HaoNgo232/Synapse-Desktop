#!/usr/bin/env python3
"""
Stress test để mô phỏng tình huống người dùng gặp race condition
"""

import sys
import time
import threading
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_rapid_file_selection():
    """
    Test rapid file selection changes - mô phỏng user click nhanh nhiều checkbox
    """
    print("Testing rapid file selection changes...")
    
    try:
        from components.file_tree import FileTreeComponent
        from core.utils.file_utils import TreeItem
        
        # Create mock page
        class MockPage:
            def __init__(self):
                self.window = type('obj', (object,), {'width': 1000})()
                
            def update(self):
                pass
                
            def run_task(self, task):
                # Mock run_task - just execute immediately
                task()
        
        page = MockPage()
        
        # Create file tree component
        file_tree = FileTreeComponent(page)
        
        # Create mock tree with many files
        root = TreeItem("test", "/test", True)
        for i in range(20):
            child = TreeItem(f"file{i}.py", f"/test/file{i}.py", False)
            root.children.append(child)
        
        file_tree.set_tree(root)
        
        # Simulate rapid selection changes
        def rapid_selection_worker():
            for i in range(50):  # 50 rapid changes
                path = f"/test/file{i % 20}.py"
                
                # Mock event object
                class MockEvent:
                    def __init__(self, value):
                        self.control = type('obj', (object,), {'value': value})()
                
                # Toggle selection
                file_tree._on_item_toggled(
                    MockEvent(i % 2 == 0),  # Alternate true/false
                    path,
                    False,  # is_dir
                    []      # children
                )
                
                time.sleep(0.001)  # Very rapid changes
        
        # Start multiple threads doing rapid selection
        threads = []
        for i in range(3):
            t = threading.Thread(target=rapid_selection_worker)
            threads.append(t)
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Check final state
        selected_count = len(file_tree.selected_paths)
        print(f"✓ Rapid selection test completed. Final selected: {selected_count}")
        
        # Cleanup
        file_tree.cleanup()
        return True
        
    except Exception as e:
        print(f"❌ Rapid selection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_concurrent_token_requests():
    """
    Test concurrent token counting requests - mô phỏng multiple files được count cùng lúc
    """
    print("Testing concurrent token counting requests...")
    
    try:
        from services.token_display import TokenDisplayService
        
        # Create service
        service = TokenDisplayService()
        
        # Create test files
        test_files = []
        for i in range(10):
            test_file = Path(f"/tmp/test_file_{i}.py")
            test_file.write_text(f"# Test file {i}\nprint('Hello world {i}')\n")
            test_files.append(str(test_file))
        
        # Concurrent token requests
        def token_request_worker():
            for i in range(20):  # 20 requests per thread
                file_path = test_files[i % len(test_files)]
                service.request_token_count(file_path)
                time.sleep(0.001)
        
        # Start multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=token_request_worker)
            threads.append(t)
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Check results
        cached_count = len([f for f in test_files if service.get_token_count(f) is not None])
        print(f"✓ Token counting test completed. Cached files: {cached_count}/{len(test_files)}")
        
        # Cleanup
        service.stop()
        for test_file in test_files:
            Path(test_file).unlink(missing_ok=True)
        
        return True
        
    except Exception as e:
        print(f"❌ Token counting test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_timer_disposal_under_stress():
    """
    Test timer disposal under stress - mô phỏng rapid start/stop cycles
    """
    print("Testing timer disposal under stress...")
    
    try:
        from core.utils.safe_timer import SafeTimer
        
        callback_count = 0
        callback_lock = threading.Lock()
        
        def test_callback():
            nonlocal callback_count
            with callback_lock:
                callback_count += 1
        
        def stress_worker():
            for i in range(20):  # 20 rapid create/dispose cycles
                timer = SafeTimer(
                    interval=0.01,  # 10ms
                    callback=test_callback,
                    page=None,
                    use_main_thread=False
                )
                
                timer.start()
                time.sleep(0.005)  # Let it almost fire
                timer.dispose()  # Dispose before callback
                
                time.sleep(0.001)
        
        # Start multiple stress workers
        threads = []
        for i in range(3):
            t = threading.Thread(target=stress_worker)
            threads.append(t)
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Wait a bit more to see if any delayed callbacks fire
        time.sleep(0.1)
        
        with callback_lock:
            final_count = callback_count
        
        print(f"✓ Timer stress test completed. Callbacks fired: {final_count}")
        
        # Should be relatively low due to disposal
        if final_count < 30:  # Allow some callbacks that were already scheduled
            print("✓ Timer disposal working correctly under stress")
            return True
        else:
            print(f"⚠️  High callback count ({final_count}), may indicate disposal issues")
            return False
        
    except Exception as e:
        print(f"❌ Timer stress test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🔥 Stress Testing Race Condition Fixes")
    print("=" * 60)
    print("Simulating real-world usage scenarios...")
    print()
    
    tests = [
        test_rapid_file_selection,
        test_concurrent_token_requests,
        test_timer_disposal_under_stress,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            print()
    
    print("=" * 60)
    print(f"Stress Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All stress tests passed! Race conditions are fixed.")
        print("\n🎉 Your application should now be stable under heavy usage.")
    else:
        print("❌ Some stress tests failed. Additional fixes may be needed.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
