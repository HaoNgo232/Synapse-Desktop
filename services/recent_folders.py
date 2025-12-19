"""
Recent Folders Service - Lưu trữ và quản lý lịch sử các thư mục đã mở

Lưu tối đa 10 thư mục gần nhất vào settings file.
"""

import json
from pathlib import Path
from typing import List
from datetime import datetime

from core.logging_config import log_error, log_debug


# Settings file path (cùng thư mục với settings chính)
RECENT_FOLDERS_FILE = Path.home() / ".overwrite-desktop" / "recent_folders.json"

# Số lượng tối đa folders lưu trữ
MAX_RECENT_FOLDERS = 10


def load_recent_folders() -> List[str]:
    """
    Load danh sách recent folders từ file.
    
    Returns:
        List các đường dẫn thư mục (mới nhất đầu tiên)
    """
    try:
        if RECENT_FOLDERS_FILE.exists():
            content = RECENT_FOLDERS_FILE.read_text(encoding="utf-8")
            data = json.loads(content)
            folders = data.get("folders", [])
            
            # Filter chỉ giữ các folders còn tồn tại
            valid_folders = [f for f in folders if Path(f).exists() and Path(f).is_dir()]
            
            return valid_folders[:MAX_RECENT_FOLDERS]
    except (OSError, json.JSONDecodeError) as e:
        log_debug(f"Could not load recent folders: {e}")
    
    return []


def add_recent_folder(folder_path: str) -> bool:
    """
    Thêm folder vào đầu danh sách recent.
    Nếu folder đã tồn tại, di chuyển lên đầu.
    
    Args:
        folder_path: Đường dẫn thư mục
        
    Returns:
        True nếu lưu thành công
    """
    try:
        # Normalize path
        folder_path = str(Path(folder_path).resolve())
        
        # Load existing
        folders = load_recent_folders()
        
        # Remove if already exists (sẽ add lại ở đầu)
        if folder_path in folders:
            folders.remove(folder_path)
        
        # Add to beginning
        folders.insert(0, folder_path)
        
        # Trim to max size
        folders = folders[:MAX_RECENT_FOLDERS]
        
        # Save
        RECENT_FOLDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "folders": folders,
            "updated_at": datetime.now().isoformat()
        }
        
        RECENT_FOLDERS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        
        log_debug(f"Added recent folder: {folder_path}")
        return True
        
    except (OSError, IOError) as e:
        log_error(f"Failed to save recent folder: {e}")
        return False


def remove_recent_folder(folder_path: str) -> bool:
    """
    Xóa folder khỏi danh sách recent.
    
    Args:
        folder_path: Đường dẫn thư mục cần xóa
        
    Returns:
        True nếu xóa thành công
    """
    try:
        folder_path = str(Path(folder_path).resolve())
        folders = load_recent_folders()
        
        if folder_path in folders:
            folders.remove(folder_path)
            
            data = {
                "folders": folders,
                "updated_at": datetime.now().isoformat()
            }
            
            RECENT_FOLDERS_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            return True
            
    except (OSError, IOError) as e:
        log_error(f"Failed to remove recent folder: {e}")
    
    return False


def clear_recent_folders() -> bool:
    """
    Xóa toàn bộ lịch sử recent folders.
    
    Returns:
        True nếu xóa thành công
    """
    try:
        if RECENT_FOLDERS_FILE.exists():
            RECENT_FOLDERS_FILE.unlink()
        return True
    except OSError as e:
        log_error(f"Failed to clear recent folders: {e}")
        return False


def get_folder_display_name(folder_path: str) -> str:
    """
    Lấy tên hiển thị ngắn gọn cho folder.
    
    Args:
        folder_path: Đường dẫn đầy đủ
        
    Returns:
        Tên hiển thị (folder name + parent)
    """
    path = Path(folder_path)
    
    if path.parent.name:
        return f"{path.name} ({path.parent.name})"
    return path.name