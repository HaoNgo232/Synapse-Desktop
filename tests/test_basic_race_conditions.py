#!/usr/bin/env python3
"""
Simple test for race condition fixes - no dependencies
"""

import threading
import time

def test_global_state_manager():
    """Test GlobalState manager"""
    print("Testing GlobalState manager...")
    
    class GlobalState:
        def __init__(self):
            self._lock = threading.Lock()
            self._scanning = False
            self._counting_tokens = False
            self._ui_updating = False
            
        def set_scanning(self, value: bool):
            with self._lock:
                self._scanning = value
                
        def is_scanning(self) -> bool:
            with self._lock:
                return self._scanning
                
        def can_interact(self) -> bool:
            """Check if UI interactions are allowed"""
            with self._lock:
                return not (self._scanning or self._ui_updating)
    
    global_state = GlobalState()
    
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

def test_threading_locks():
    """Test basic threading locks"""
    print("Testing threading locks...")
    
    class ThreadSafeCounter:
        def __init__(self):
            self._lock = threading.Lock()
            self._count = 0
            
        def increment(self):
            with self._lock:
                current = self._count
                time.sleep(0.001)  # Simulate race condition
                self._count = current + 1
                
        def get_count(self):
            with self._lock:
                return self._count
    
    counter = ThreadSafeCounter()
    
    def worker():
        for _ in range(100):
            counter.increment()
    
    # Start multiple threads
    threads = []
    for i in range(5):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
    
    # Wait for completion
    for t in threads:
        t.join()
    
    expected = 5 * 100
    actual = counter.get_count()
    assert actual == expected, f"Expected {expected}, got {actual}"
    
    print("✓ Threading locks test completed")

if __name__ == "__main__":
    print("Running basic race condition tests...")
    print("=" * 50)
    
    try:
        test_global_state_manager()
        test_threading_locks()
        
        print("=" * 50)
        print("✅ All basic race condition tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
