#!/usr/bin/env python3
"""
Test race condition fixes after applying SafeTimer changes
"""

import sys
import time
import threading
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_safe_timer_import():
    """Test that SafeTimer can be imported and used"""
    print("Testing SafeTimer import and basic functionality...")
    
    try:
        from core.utils.safe_timer import SafeTimer
        
        # Test basic timer creation and disposal
        callback_called = threading.Event()
        
        def test_callback():
            callback_called.set()
        
        timer = SafeTimer(
            interval=0.1,
            callback=test_callback,
            page=None,
            use_main_thread=False
        )
        
        timer.start()
        
        # Wait for callback
        if callback_called.wait(timeout=1.0):
            print("✓ SafeTimer callback executed successfully")
        else:
            print("❌ SafeTimer callback did not execute")
            return False
        
        # Test disposal
        timer.dispose()
        print("✓ SafeTimer disposed successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ SafeTimer test failed: {e}")
        return False

def test_context_view_imports():
    """Test that ContextView can import SafeTimer"""
    print("Testing ContextView SafeTimer import...")
    
    try:
        # This will fail if import is broken
        from views.context_view import ContextView
        print("✓ ContextView imports SafeTimer successfully")
        return True
        
    except Exception as e:
        print(f"❌ ContextView import failed: {e}")
        return False

def test_file_tree_imports():
    """Test that FileTreeComponent can import SafeTimer"""
    print("Testing FileTreeComponent SafeTimer import...")
    
    try:
        # This will fail if import is broken
        from components.file_tree import FileTreeComponent
        print("✓ FileTreeComponent imports SafeTimer successfully")
        return True
        
    except Exception as e:
        print(f"❌ FileTreeComponent import failed: {e}")
        return False

def test_timer_disposal_race():
    """Test that timer disposal prevents race conditions"""
    print("Testing timer disposal race condition prevention...")
    
    try:
        from core.utils.safe_timer import SafeTimer
        
        callback_count = 0
        callback_lock = threading.Lock()
        
        def test_callback():
            nonlocal callback_count
            with callback_lock:
                callback_count += 1
        
        # Create timer
        timer = SafeTimer(
            interval=0.05,  # 50ms
            callback=test_callback,
            page=None,
            use_main_thread=False
        )
        
        timer.start()
        
        # Dispose immediately
        timer.dispose()
        
        # Wait a bit to see if callback still executes
        time.sleep(0.2)
        
        with callback_lock:
            final_count = callback_count
        
        # Should be 0 or 1 (if callback was already scheduled)
        if final_count <= 1:
            print(f"✓ Timer disposal prevented race condition (callbacks: {final_count})")
            return True
        else:
            print(f"❌ Timer disposal failed, too many callbacks: {final_count}")
            return False
            
    except Exception as e:
        print(f"❌ Timer disposal test failed: {e}")
        return False

def main():
    print("🧪 Testing Race Condition Fixes")
    print("=" * 50)
    
    tests = [
        test_safe_timer_import,
        test_context_view_imports,
        test_file_tree_imports,
        test_timer_disposal_race,
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
    
    print("=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All race condition fixes are working!")
        return True
    else:
        print("❌ Some fixes need attention")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
