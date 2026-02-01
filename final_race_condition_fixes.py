#!/usr/bin/env python3
"""
Final Race Condition Fixes - Apply these changes to resolve remaining issues
"""

# ============================================
# 1. Fix TokenDisplayService - Replace Timer with SafeTimer
# ============================================

def apply_token_service_safe_timer_fix():
    """
    Apply SafeTimer fix to TokenDisplayService
    """
    print("Applying TokenDisplayService SafeTimer fix...")
    
    # File: services/token_display.py
    # Replace import section
    token_service_imports = '''from pathlib import Path
from typing import Dict, Callable, Set, Optional
import threading

from core.utils.file_utils import TreeItem
from core.token_counter import count_tokens_for_file
from core.utils.safe_timer import SafeTimer  # RACE CONDITION FIX'''

    # Replace _schedule_ui_update method
    schedule_ui_update_fix = '''    def _schedule_ui_update(self):
        """Schedule a debounced UI update - RACE CONDITION SAFE"""
        with self._update_lock:
            if self._update_timer:
                self._update_timer.cancel()
            
            # RACE CONDITION FIX: Use SafeTimer instead of Timer
            self._update_timer = SafeTimer(
                interval=0.1,
                callback=self._do_ui_update,
                page=getattr(self, '_page', None),
                use_main_thread=True
            )
            self._update_timer.start()'''

    # Replace stop method
    stop_method_fix = '''    def stop(self):
        """
        Stop processing và cleanup.
        
        RACE CONDITION FIX: Set disposal flag TRƯỚC khi cancel timers.
        """
        # Set disposal flag FIRST
        self._is_disposed = True
        
        stop_token_counting()
        self._loading_paths.clear()
        with self._update_lock:
            self._pending_updates.clear()
            if self._update_timer:
                self._update_timer.dispose()  # Use dispose instead of cancel
                self._update_timer = None'''

    return {
        "imports": token_service_imports,
        "schedule_ui_update": schedule_ui_update_fix,
        "stop_method": stop_method_fix
    }

# ============================================
# 2. Fix ContextView - Add debounced token updates
# ============================================

def apply_context_view_debounce_fix():
    """
    Apply debounced token update fix to ContextView
    """
    print("Applying ContextView debounce fix...")
    
    # Add to __init__ method
    init_addition = '''        # Race condition prevention
        self._loading_lock = threading.Lock()
        self._is_loading = False
        self._pending_refresh: bool = False
        self._is_disposed: bool = False
        
        # RACE CONDITION FIX: Debounced token updates
        from core.utils.safe_timer import DebouncedCallback
        self._token_update_debouncer = DebouncedCallback(
            delay=0.2,  # 200ms debounce
            callback=self._do_update_token_count,
            page=self.page
        )'''

    # Replace _update_token_count method
    update_token_count_fix = '''    def _update_token_count(self):
        """
        Update token count với debouncing - RACE CONDITION SAFE.
        
        Debounce multiple rapid calls thành một update duy nhất.
        """
        if hasattr(self, '_token_update_debouncer'):
            self._token_update_debouncer.call()
        else:
            # Fallback nếu debouncer chưa được khởi tạo
            self._do_update_token_count()'''

    # Add new method
    do_update_token_count_method = '''    def _do_update_token_count(self):
        """Actual token count update - được gọi sau debounce"""
        if not self.file_tree_component or self._is_disposed:
            return
            
        try:
            selected_paths = self.file_tree_component.get_selected_paths()
            if self.token_stats_panel:
                self.token_stats_panel.update_stats(selected_paths)
        except Exception as e:
            from core.logging_config import log_error
            log_error(f"Error updating token count: {e}")'''

    # Update cleanup method
    cleanup_addition = '''        # RACE CONDITION FIX: Set disposal flag FIRST
        self._is_disposed = True
        
        # Dispose debouncer
        if hasattr(self, '_token_update_debouncer'):
            self._token_update_debouncer.dispose()'''

    return {
        "init_addition": init_addition,
        "update_token_count": update_token_count_fix,
        "do_update_method": do_update_token_count_method,
        "cleanup_addition": cleanup_addition
    }

# ============================================
# 3. Fix FileWatcher - Debounce file events
# ============================================

def apply_file_watcher_debounce_fix():
    """
    Apply debounced file event fix to FileWatcher
    """
    print("Applying FileWatcher debounce fix...")
    
    # Add to __init__ method
    init_addition = '''        # RACE CONDITION FIX: Debounce file change events
        from core.utils.safe_timer import DebouncedCallback
        self._refresh_debouncer = DebouncedCallback(
            delay=0.5,  # 500ms debounce cho file changes
            callback=self._do_refresh,
            page=None  # Will be set when callback is provided
        )
        self._pending_callback = None'''

    # Replace _trigger_callback method
    trigger_callback_fix = '''    def _trigger_callback(self, event: FileChangeEvent):
        """Trigger callback với debouncing - RACE CONDITION SAFE"""
        if not self.callbacks or not self.callbacks.on_change:
            return
        
        # Store callback for debounced execution
        self._pending_callback = lambda: self.callbacks.on_change(event)
        
        # Debounce the callback
        if hasattr(self, '_refresh_debouncer'):
            self._refresh_debouncer.call()'''

    # Add new method
    do_refresh_method = '''    def _do_refresh(self):
        """Execute pending callback sau debounce"""
        if hasattr(self, '_pending_callback') and self._pending_callback:
            try:
                self._pending_callback()
            except Exception as e:
                from core.logging_config import log_error
                log_error(f"Error in file watcher callback: {e}")
            finally:
                self._pending_callback = None'''

    # Update stop method
    stop_addition = '''        # RACE CONDITION FIX: Dispose debouncer
        if hasattr(self, '_refresh_debouncer'):
            self._refresh_debouncer.dispose()'''

    return {
        "init_addition": init_addition,
        "trigger_callback": trigger_callback_fix,
        "do_refresh_method": do_refresh_method,
        "stop_addition": stop_addition
    }

# ============================================
# 4. Improved session restore with exponential backoff
# ============================================

def apply_session_restore_improvement():
    """
    Apply improved session restore with exponential backoff
    """
    print("Applying session restore improvement...")
    
    session_restore_fix = '''                def _restore_selection_after_load():
                    """
                    Restore selection sau khi tree load xong - IMPROVED VERSION.
                    
                    Sử dụng exponential backoff thay vì fixed polling.
                    """
                    try:
                        # Wait for loading completion với exponential backoff
                        max_wait = 30  # Max 30 giây
                        wait_time = 0.1
                        total_waited = 0
                        
                        while total_waited < max_wait:
                            with self.context_view._loading_lock:
                                if not self.context_view._is_loading:
                                    break
                            
                            time.sleep(wait_time)
                            total_waited += wait_time
                            wait_time = min(wait_time * 1.2, 1.0)  # Exponential backoff, max 1s
                        
                        # Restore session data
                        pending = getattr(self, "_pending_session_restore", None)
                        if pending and self.context_view.file_tree_component:
                            try:
                                # Restore selected files
                                if pending.get("selected_files"):
                                    valid_selected = set(
                                        f for f in pending["selected_files"]
                                        if Path(f).exists()
                                    )
                                    # Use proper lock if available
                                    if hasattr(self.context_view.file_tree_component, '_ui_lock'):
                                        with self.context_view.file_tree_component._ui_lock:
                                            self.context_view.file_tree_component.selected_paths = valid_selected
                                    else:
                                        self.context_view.file_tree_component.selected_paths = valid_selected

                                # Restore expanded folders
                                if pending.get("expanded_folders"):
                                    valid_expanded = set(
                                        f for f in pending["expanded_folders"]
                                        if Path(f).exists()
                                    )
                                    if self.context_view.tree:
                                        valid_expanded.add(self.context_view.tree.path)
                                    self.context_view.file_tree_component.expanded_paths = valid_expanded

                                # Render tree với restored state
                                self.context_view.file_tree_component._render_tree()
                                self.context_view._update_token_count()
                                
                            except Exception as restore_error:
                                from core.logging_config import log_error
                                log_error(f"Error during session restore: {restore_error}")

                        # Clear pending data
                        self._pending_session_restore = None

                    except Exception as e:
                        from core.logging_config import log_error
                        log_error(f"Error restoring session selection: {e}")'''

    return {"session_restore": session_restore_fix}

# ============================================
# Main application function
# ============================================

def main():
    print("🔧 Final Race Condition Fixes for Synapse Desktop")
    print("=" * 60)
    
    fixes = {
        "1. TokenDisplayService SafeTimer": apply_token_service_safe_timer_fix(),
        "2. ContextView Debounce": apply_context_view_debounce_fix(),
        "3. FileWatcher Debounce": apply_file_watcher_debounce_fix(),
        "4. Session Restore Improvement": apply_session_restore_improvement(),
    }
    
    print("\n📋 Summary of fixes to apply:")
    print("-" * 40)
    
    for fix_name, fix_data in fixes.items():
        print(f"✅ {fix_name}")
        if isinstance(fix_data, dict):
            for component, _ in fix_data.items():
                print(f"   - {component}")
    
    print("\n🎯 Key improvements:")
    print("- SafeTimer replaces threading.Timer for disposal-safe callbacks")
    print("- Debounced updates prevent rapid UI thrashing")
    print("- Exponential backoff for session restore polling")
    print("- Proper disposal flags to prevent post-cleanup callbacks")
    print("- Thread-safe state management with locks")
    
    print("\n⚠️  Manual application required:")
    print("- Apply these changes to the respective files")
    print("- Test thoroughly after each change")
    print("- Monitor for any remaining race conditions")
    
    print("\n🧪 Test with:")
    print("- python test_race_conditions.py")
    print("- python test_basic_race_conditions.py")
    print("- Manual testing: rapid folder opening/closing")
    print("- Manual testing: rapid file selection changes")

if __name__ == "__main__":
    main()
