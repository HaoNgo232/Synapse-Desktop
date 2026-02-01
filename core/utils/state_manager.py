"""Global state manager to prevent race conditions"""
import threading
from typing import Set

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
            
    def set_counting_tokens(self, value: bool):
        with self._lock:
            self._counting_tokens = value
            
    def is_counting_tokens(self) -> bool:
        with self._lock:
            return self._counting_tokens
            
    def set_ui_updating(self, value: bool):
        with self._lock:
            self._ui_updating = value
            
    def is_ui_updating(self) -> bool:
        with self._lock:
            return self._ui_updating
    
    def set_loading(self, loading: bool):
        """
        Set loading state để block UI interactions.
        
        Sử dụng khi đang load tree hoặc heavy operations.
        """
        with self._lock:
            self._ui_updating = loading
    
    def is_loading(self) -> bool:
        """Check xem có đang loading không."""
        with self._lock:
            return self._ui_updating
            
    def can_interact(self) -> bool:
        """Check if UI interactions are allowed"""
        with self._lock:
            return not (self._scanning or self._ui_updating)

# Global instance
global_state = GlobalState()

