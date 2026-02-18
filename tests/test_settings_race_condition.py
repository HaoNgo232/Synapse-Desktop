"""
Test race condition trong settings manager.

Verify rằng concurrent save_settings() calls không làm mất data.
"""

import threading
import time
from services.settings_manager import save_settings, load_settings


def test_concurrent_save_settings():
    """Test concurrent save_settings không làm mất data."""

    # Setup: Clear và set initial excluded patterns
    initial_patterns = "node_modules\ndist\nbuild"
    save_settings({"excluded_folders": initial_patterns})

    results = []
    errors = []

    def save_model(model_id: str):
        """Thread 1: Save model setting"""
        try:
            for i in range(10):
                success = save_settings({"model_id": model_id})
                results.append(("model", success))
                time.sleep(0.001)  # Small delay to increase race chance
        except Exception as e:
            errors.append(("model", str(e)))

    def save_format(format_id: str):
        """Thread 2: Save format setting"""
        try:
            for i in range(10):
                success = save_settings({"output_format": format_id})
                results.append(("format", success))
                time.sleep(0.001)
        except Exception as e:
            errors.append(("format", str(e)))

    def save_security(enabled: bool):
        """Thread 3: Save security setting"""
        try:
            for i in range(10):
                success = save_settings({"enable_security_check": enabled})
                results.append(("security", success))
                time.sleep(0.001)
        except Exception as e:
            errors.append(("security", str(e)))

    # Run 3 threads concurrently
    threads = [
        threading.Thread(target=save_model, args=("claude-sonnet-4.5",)),
        threading.Thread(target=save_format, args=("xml",)),
        threading.Thread(target=save_security, args=(True,)),
    ]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # Verify no errors
    assert len(errors) == 0, f"Errors occurred: {errors}"

    # Verify all saves succeeded
    assert all(success for _, success in results), "Some saves failed"

    # CRITICAL: Verify excluded_folders không bị mất
    final_settings = load_settings()
    assert "excluded_folders" in final_settings, "excluded_folders key missing!"
    assert final_settings["excluded_folders"] == initial_patterns, (
        f"excluded_folders bị thay đổi! Expected: {initial_patterns!r}, Got: {final_settings['excluded_folders']!r}"
    )

    # Verify các settings khác cũng được lưu
    assert final_settings["model_id"] == "claude-sonnet-4.5"
    assert final_settings["output_format"] == "xml"
    assert final_settings["enable_security_check"] is True

    print("✅ Race condition test passed: No data loss in concurrent saves")


def test_rapid_sequential_saves():
    """Test rapid sequential saves không làm mất data."""

    initial_patterns = "test1\ntest2\ntest3"
    save_settings({"excluded_folders": initial_patterns})

    # Rapid saves
    for i in range(50):
        save_settings({"model_id": f"model-{i}"})

    # Verify excluded_folders vẫn còn
    final = load_settings()
    assert final["excluded_folders"] == initial_patterns
    assert final["model_id"] == "model-49"

    print("✅ Rapid sequential saves test passed")


if __name__ == "__main__":
    test_concurrent_save_settings()
    test_rapid_sequential_saves()
    print("\n✅ All settings race condition tests passed!")
