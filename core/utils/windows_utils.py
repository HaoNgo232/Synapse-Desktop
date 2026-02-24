"""
Windows-specific utilities for Synapse Desktop.

Xử lý các vấn đề đặc thù của Windows như AppUserModelID để icon hiển thị đúng trên taskbar.
"""

import sys
import platform
from typing import Optional


def set_app_user_model_id(app_id: str) -> bool:
    """
    Set AppUserModelID cho Windows để icon hiển thị đúng trên taskbar.
    
    Windows nhóm ứng dụng theo AppUserModelID. Nếu không set ID này,
    Windows sẽ dùng icon của Python thay vì icon của app.
    
    Args:
        app_id: AppUserModelID string (ví dụ: "Synapse.SynapseDesktop")
    
    Returns:
        True nếu set thành công, False nếu không phải Windows hoặc có lỗi.
        Trên Linux/macOS, function này luôn return False mà không gây ảnh hưởng.
    """
    # Check platform TRƯỚC KHI import bất kỳ Windows-specific module nào
    # Đảm bảo không có side effect trên Linux/macOS
    if platform.system() != "Windows":
        return False
    
    try:
        # Import ctypes CHỈ KHI đã confirm là Windows
        # Điều này đảm bảo không có ImportError trên Linux
        from ctypes import windll
        
        # Set AppUserModelID - Windows API để taskbar hiển thị icon đúng
        # windll chỉ có trên Windows, nhưng đã check platform ở trên
        result = windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        
        # HRESULT S_OK = 0
        return result == 0
    except (ImportError, AttributeError, OSError):
        # ImportError: ctypes hoặc wintypes không available (rất hiếm)
        # AttributeError: windll không có (không phải Windows, nhưng đã check ở trên)
        # OSError: shell32.dll không load được
        # Tất cả đều safe - chỉ return False, không crash app
        return False
    except Exception:
        # Catch-all cho các lỗi khác - đảm bảo không bao giờ crash app
        return False


def get_default_app_user_model_id() -> str:
    """
    Trả về AppUserModelID mặc định cho Synapse Desktop.
    
    Format: CompanyName.ProductName
    """
    return "Synapse.SynapseDesktop"
