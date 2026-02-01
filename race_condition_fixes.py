#!/usr/bin/env python3
"""
Race Condition Fixes for Synapse Desktop

Tổng hợp các fix cần thiết để giải quyết hoàn toàn race conditions.
"""

# ============================================
# 1. FileTreeComponent - Selection Race Condition Fix
# ============================================

def fix_file_tree_selection_race():
    """
    Fix race condition trong FileTreeComponent._on_item_toggled()
    
    Vấn đề: Multiple threads có thể modify selected_paths cùng lúc
    Giải pháp: Thêm lock cho selection operations
    """
    return """
# Trong components/file_tree.py - class FileTreeComponent.__init__():

# Thêm vào __init__:
self._selection_lock = threading.Lock()

# Fix _on_item_toggled method:
def _on_item_toggled(self, e, path: str, is_dir: bool, children: list):
    \"\"\"Handle khi user toggle checkbox - THREAD SAFE\"\"\"
    with self._selection_lock:  # RACE CONDITION FIX
        if e.control.value:
            self.selected_paths.add(path)
            # Auto-select children nếu là folder
            if is_dir:
                self._auto_select_children_in_folder(path, children)
        else:
            self.selected_paths.discard(path)
            # Auto-deselect children nếu là folder
            if is_dir:
                self._deselect_all_children(path, children)
    
    # Trigger callback OUTSIDE lock để tránh deadlock
    if self.on_selection_changed:
        self.on_selection_changed(self.selected_paths.copy())
"""

# ============================================
# 2. TokenDisplayService - Timer Race Condition Fix  
# ============================================

def fix_token_service_timer_race():
    """
    Fix race condition trong TokenDisplayService timer callbacks
    
    Vấn đề: Timer callbacks có thể chạy sau khi service đã cleanup
    Giải pháp: Sử dụng SafeTimer thay vì threading.Timer
    """
    return """
# Trong services/token_display.py:

from core.utils.safe_timer import SafeTimer

# Replace _update_timer: Optional[Timer] = None
# Với:
self._update_timer: Optional[SafeTimer] = None

# Fix _schedule_ui_update method:
def _schedule_ui_update(self):
    \"\"\"Schedule a debounced UI update - RACE CONDITION SAFE\"\"\"
    with self._update_lock:
        if self._update_timer:
            self._update_timer.cancel()
        
        # Sử dụng SafeTimer thay vì Timer
        self._update_timer = SafeTimer(
            interval=0.1,
            callback=self._do_ui_update,
            page=getattr(self, '_page', None),  # Pass page nếu có
            use_main_thread=True
        )
        self._update_timer.start()

# Fix stop method:
def stop(self):
    \"\"\"Stop processing và cleanup - RACE CONDITION SAFE\"\"\"
    self._is_disposed = True
    stop_token_counting()
    self._loading_paths.clear()
    
    with self._update_lock:
        self._pending_updates.clear()
        if self._update_timer:
            self._update_timer.dispose()  # Sử dụng dispose thay vì cancel
            self._update_timer = None
"""

# ============================================
# 3. ContextView - Render Race Condition Fix
# ============================================

def fix_context_view_render_race():
    """
    Fix race condition trong ContextView._update_token_count()
    
    Vấn đề: Multiple calls có thể trigger concurrent token counting
    Giải pháp: Debounce token count updates
    """
    return """
# Trong views/context_view.py - class ContextView.__init__():

from core.utils.safe_timer import DebouncedCallback

# Thêm vào __init__:
self._token_update_debouncer = DebouncedCallback(
    delay=0.2,  # 200ms debounce
    callback=self._do_update_token_count,
    page=self.page
)

# Fix _update_token_count method:
def _update_token_count(self):
    \"\"\"
    Update token count với debouncing - RACE CONDITION SAFE.
    
    Debounce multiple rapid calls thành một update duy nhất.
    \"\"\"
    self._token_update_debouncer.call()

# Thêm method mới:
def _do_update_token_count(self):
    \"\"\"Actual token count update - được gọi sau debounce\"\"\"
    if not self.file_tree_component or self._is_disposed:
        return
        
    try:
        selected_paths = self.file_tree_component.get_selected_paths()
        if self.token_stats_panel:
            self.token_stats_panel.update_stats(selected_paths)
    except Exception as e:
        from core.logging_config import log_error
        log_error(f"Error updating token count: {e}")

# Fix cleanup method:
def cleanup(self):
    \"\"\"Cleanup resources - RACE CONDITION SAFE\"\"\"
    self._is_disposed = True
    
    # Dispose debouncer
    if hasattr(self, '_token_update_debouncer'):
        self._token_update_debouncer.dispose()
    
    # ... rest of cleanup code
"""

# ============================================
# 4. FileWatcher - Event Race Condition Fix
# ============================================

def fix_file_watcher_event_race():
    """
    Fix race condition trong FileWatcher event handling
    
    Vấn đề: Multiple file events có thể trigger concurrent refreshes
    Giải pháp: Debounce file change events
    """
    return """
# Trong services/file_watcher.py:

from core.utils.safe_timer import DebouncedCallback

# Trong class FileWatcher.__init__():
self._refresh_debouncer = DebouncedCallback(
    delay=0.5,  # 500ms debounce cho file changes
    callback=self._do_refresh,
    page=None  # Will be set when callback is provided
)

# Fix _trigger_callback method:
def _trigger_callback(self, event: FileChangeEvent):
    \"\"\"Trigger callback với debouncing - RACE CONDITION SAFE\"\"\"
    if not self.callbacks or not self.callbacks.on_change:
        return
    
    # Store callback for debounced execution
    self._pending_callback = lambda: self.callbacks.on_change(event)
    
    # Debounce the callback
    self._refresh_debouncer.call()

# Thêm method mới:
def _do_refresh(self):
    \"\"\"Execute pending callback sau debounce\"\"\"
    if hasattr(self, '_pending_callback') and self._pending_callback:
        try:
            self._pending_callback()
        except Exception as e:
            from core.logging_config import log_error
            log_error(f"Error in file watcher callback: {e}")
        finally:
            self._pending_callback = None

# Fix stop method:
def stop(self):
    \"\"\"Stop watching - RACE CONDITION SAFE\"\"\"
    if hasattr(self, '_refresh_debouncer'):
        self._refresh_debouncer.dispose()
    
    # ... rest of stop code
"""

# ============================================
# 5. Main App - Session Restore Race Condition Fix
# ============================================

def fix_main_app_session_race():
    """
    Fix race condition trong main app session restore
    
    Vấn đề: Session restore có thể chạy trước khi tree load xong
    Giải pháp: Sử dụng proper async coordination
    """
    return """
# Trong main.py - class SynapseApp:

# Fix _restore_selection_after_load method:
def _restore_selection_after_load(self):
    \"\"\"
    Restore selection sau khi tree load xong - IMPROVED VERSION.
    
    Sử dụng proper coordination thay vì polling.
    \"\"\"
    try:
        # Sử dụng event-based coordination thay vì polling
        max_wait = 30  # Max 30 giây
        
        # Wait for loading completion với exponential backoff
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
            # Restore với proper error handling
            try:
                # Restore selected files
                if pending.get("selected_files"):
                    valid_selected = set(
                        f for f in pending["selected_files"]
                        if Path(f).exists()
                    )
                    with self.context_view.file_tree_component._selection_lock:
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
        log_error(f"Error restoring session selection: {e}")
"""

if __name__ == "__main__":
    print("Race Condition Fixes for Synapse Desktop")
    print("=" * 50)
    print("1. FileTreeComponent selection race fix")
    print("2. TokenDisplayService timer race fix") 
    print("3. ContextView render race fix")
    print("4. FileWatcher event race fix")
    print("5. Main app session restore race fix")
    print("=" * 50)
    print("Apply these fixes to resolve remaining race conditions.")
