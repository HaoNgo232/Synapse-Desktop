#!/usr/bin/env python3
"""
Minimal Race Condition Fix - Apply only essential changes
"""

def apply_context_view_safe_timer_fix():
    """
    Fix ContextView to use SafeTimer instead of threading.Timer
    """
    
    # File: views/context_view.py
    # Replace import
    import_fix = """from core.utils.safe_timer import SafeTimer"""
    
    # Replace _on_selection_changed method
    method_fix = """    def _on_selection_changed(self, selected_paths: Set[str]):
        \"\"\"Callback khi selection thay doi - debounced with SafeTimer\"\"\"
        # Cancel previous timer if exists
        if self._selection_update_timer is not None:
            self._selection_update_timer.dispose()

        # For small selections, update immediately
        if len(selected_paths) < 10:
            self._update_token_count()
            return

        # For larger selections, debounce with SafeTimer
        self._selection_update_timer = SafeTimer(
            interval=self._selection_debounce_ms / 1000.0,
            callback=self._do_update_token_count,
            page=self.page,
            use_main_thread=True
        )
        self._selection_update_timer.start()"""
    
    # Update cleanup method
    cleanup_fix = """        if self._selection_update_timer is not None:
            try:
                self._selection_update_timer.dispose()  # Use dispose instead of cancel
            except Exception:
                pass
            self._selection_update_timer = None"""
    
    return {
        "import": import_fix,
        "method": method_fix,
        "cleanup": cleanup_fix
    }

def apply_file_tree_safe_timer_fix():
    """
    Fix FileTreeComponent to use SafeTimer instead of threading.Timer
    """
    
    # File: components/file_tree.py
    # Replace import
    import_fix = """from core.utils.safe_timer import SafeTimer"""
    
    # Replace _schedule_render method
    schedule_render_fix = """    def _schedule_render(self):
        \"\"\"Schedule a debounced render - RACE CONDITION SAFE\"\"\"
        with self._ui_lock:
            if self._render_timer:
                self._render_timer.dispose()
            
            # Use SafeTimer instead of Timer
            self._render_timer = SafeTimer(
                interval=0.1,
                callback=self._do_render,
                page=getattr(self, 'page', None),
                use_main_thread=True
            )
            self._render_timer.start()"""
    
    # Update cleanup method
    cleanup_fix = """        # Cancel render timer safely
        render_timer = self._render_timer
        self._render_timer = None
        if render_timer is not None:
            try:
                render_timer.dispose()  # Use dispose instead of cancel
            except Exception:
                pass"""
    
    return {
        "import": import_fix,
        "schedule_render": schedule_render_fix,
        "cleanup": cleanup_fix
    }

def main():
    print("🔧 Minimal Race Condition Fix")
    print("=" * 40)
    
    print("Key issues identified:")
    print("1. ContextView still uses threading.Timer")
    print("2. FileTreeComponent still uses threading.Timer")
    print("3. These can cause callbacks after disposal")
    
    print("\nMinimal fixes needed:")
    print("- Replace Timer with SafeTimer in ContextView")
    print("- Replace Timer with SafeTimer in FileTreeComponent")
    print("- Use dispose() instead of cancel() for cleanup")
    
    context_fix = apply_context_view_safe_timer_fix()
    file_tree_fix = apply_file_tree_safe_timer_fix()
    
    print("\n✅ Fix data generated")
    print("Apply these changes manually to resolve race conditions")

if __name__ == "__main__":
    main()
