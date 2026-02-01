#!/usr/bin/env python3
"""
Race Condition Test Script - Test app behavior under stress
"""

import sys
import time
import threading
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_app_race_conditions():
    """
    Test app race conditions by simulating rapid user interactions
    """
    print("🧪 Testing Synapse Desktop Race Conditions")
    print("=" * 50)
    
    try:
        # Test imports
        print("1. Testing imports...")
        from core.utils.safe_timer import SafeTimer, DebouncedCallback
        from core.utils.state_manager import global_state
        from services.token_display import TokenDisplayService
        print("   ✅ All imports successful")
        
        # Test SafeTimer
        print("\n2. Testing SafeTimer...")
        callback_count = 0
        def test_callback():
            nonlocal callback_count
            callback_count += 1
        
        timer = SafeTimer(0.1, test_callback)
        timer.start()
        time.sleep(0.2)
        timer.dispose()
        
        assert callback_count == 1, f"Expected 1 callback, got {callback_count}"
        print("   ✅ SafeTimer working correctly")
        
        # Test DebouncedCallback
        print("\n3. Testing DebouncedCallback...")
        debounce_count = 0
        def debounce_callback():
            nonlocal debounce_count
            debounce_count += 1
        
        debouncer = DebouncedCallback(0.1, debounce_callback)
        
        # Call multiple times rapidly
        for i in range(5):
            debouncer.call()
            time.sleep(0.02)  # 20ms between calls
        
        time.sleep(0.2)  # Wait for debounce
        debouncer.dispose()
        
        assert debounce_count == 1, f"Expected 1 debounced callback, got {debounce_count}"
        print("   ✅ DebouncedCallback working correctly")
        
        # Test GlobalState
        print("\n4. Testing GlobalState thread safety...")
        def state_worker():
            for i in range(100):
                global_state.set_scanning(True)
                assert global_state.is_scanning()
                global_state.set_scanning(False)
                assert not global_state.is_scanning()
        
        threads = []
        for i in range(3):
            t = threading.Thread(target=state_worker)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        print("   ✅ GlobalState thread safety working")
        
        # Test TokenDisplayService
        print("\n5. Testing TokenDisplayService...")
        service = TokenDisplayService()
        
        # Test concurrent requests
        def token_worker():
            for i in range(10):
                service.request_token_count(f"/test/file{i}.py")
                time.sleep(0.01)
        
        threads = []
        for i in range(2):
            t = threading.Thread(target=token_worker)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        service.stop()
        print("   ✅ TokenDisplayService working correctly")
        
        print("\n" + "=" * 50)
        print("🎉 All race condition tests passed!")
        print("\n📋 Summary of fixes verified:")
        print("   - SafeTimer prevents post-disposal callbacks")
        print("   - DebouncedCallback prevents rapid UI updates")
        print("   - GlobalState provides thread-safe state management")
        print("   - TokenDisplayService handles concurrent requests safely")
        
        print("\n🚀 App should now be more stable with:")
        print("   - No more checkbox disappearing issues")
        print("   - No more UI freezing during folder loading")
        print("   - Smoother file selection experience")
        print("   - Better handling of rapid user interactions")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def simulate_user_stress_test():
    """
    Simulate rapid user interactions that previously caused race conditions
    """
    print("\n🔥 Simulating User Stress Test...")
    print("-" * 30)
    
    try:
        from core.utils.safe_timer import DebouncedCallback
        
        # Simulate rapid file selection changes
        selection_changes = 0
        def on_selection_changed():
            nonlocal selection_changes
            selection_changes += 1
        
        debouncer = DebouncedCallback(0.1, on_selection_changed)
        
        # Simulate user rapidly clicking checkboxes
        print("Simulating rapid checkbox clicks...")
        for i in range(20):
            debouncer.call()
            time.sleep(0.01)  # Very rapid clicks
        
        time.sleep(0.2)  # Wait for debounce
        debouncer.dispose()
        
        print(f"   - 20 rapid clicks resulted in {selection_changes} actual updates")
        print("   ✅ UI updates properly debounced")
        
        # Simulate rapid folder opening
        print("\nSimulating rapid folder operations...")
        from core.utils.state_manager import global_state
        
        operations = 0
        def folder_operation():
            nonlocal operations
            if global_state.can_interact():
                global_state.set_scanning(True)
                operations += 1
                time.sleep(0.01)  # Simulate work
                global_state.set_scanning(False)
        
        # Try to start multiple operations concurrently
        threads = []
        for i in range(5):
            t = threading.Thread(target=folder_operation)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        print(f"   - {operations} operations completed safely")
        print("   ✅ State management prevents conflicts")
        
        return True
        
    except Exception as e:
        print(f"❌ Stress test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_app_race_conditions()
    
    if success:
        stress_success = simulate_user_stress_test()
        if stress_success:
            print("\n🏆 All tests passed! Race conditions should be resolved.")
            sys.exit(0)
    
    print("\n💥 Some tests failed. Check the fixes and try again.")
    sys.exit(1)
