"""
Unit tests cho Recent Folders Service
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import shutil

from services.recent_folders import (
    load_recent_folders,
    add_recent_folder,
    remove_recent_folder,
    clear_recent_folders,
    get_folder_display_name,
    RECENT_FOLDERS_FILE,
    MAX_RECENT_FOLDERS,
)


class TestGetFolderDisplayName:
    """Test get_folder_display_name function"""
    
    def test_simple_folder(self):
        """Test với folder đơn giản"""
        result = get_folder_display_name("/home/user/projects/myapp")
        assert "myapp" in result
        assert "projects" in result
    
    def test_root_folder(self):
        """Test với folder ở root"""
        result = get_folder_display_name("/myapp")
        assert result == "myapp"


class TestRecentFoldersIntegration:
    """Integration tests với temp file"""
    
    @pytest.fixture
    def temp_settings_dir(self):
        """Tạo temp directory cho tests"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def temp_folders(self, temp_settings_dir):
        """Tạo temp folders để test"""
        folders = []
        for i in range(5):
            folder = temp_settings_dir / f"project_{i}"
            folder.mkdir()
            folders.append(str(folder))
        return folders
    
    def test_add_and_load(self, temp_settings_dir, temp_folders):
        """Test add và load recent folders"""
        with patch('services.recent_folders.RECENT_FOLDERS_FILE', 
                   temp_settings_dir / "recent.json"):
            # Clear first
            clear_recent_folders()
            
            # Add folders
            for folder in temp_folders[:3]:
                assert add_recent_folder(folder)
            
            # Load và verify
            loaded = load_recent_folders()
            assert len(loaded) == 3
            
            # Verify order (mới nhất đầu tiên)
            assert loaded[0] == temp_folders[2]
    
    def test_max_folders_limit(self, temp_settings_dir, temp_folders):
        """Test giới hạn số lượng folders"""
        with patch('services.recent_folders.RECENT_FOLDERS_FILE',
                   temp_settings_dir / "recent.json"):
            with patch('services.recent_folders.MAX_RECENT_FOLDERS', 3):
                clear_recent_folders()
                
                # Add nhiều hơn limit
                for folder in temp_folders:
                    add_recent_folder(folder)
                
                loaded = load_recent_folders()
                assert len(loaded) <= 3
    
    def test_remove_folder(self, temp_settings_dir, temp_folders):
        """Test xóa folder khỏi list"""
        with patch('services.recent_folders.RECENT_FOLDERS_FILE',
                   temp_settings_dir / "recent.json"):
            clear_recent_folders()
            
            add_recent_folder(temp_folders[0])
            add_recent_folder(temp_folders[1])
            
            remove_recent_folder(temp_folders[0])
            
            loaded = load_recent_folders()
            assert temp_folders[0] not in loaded
            assert temp_folders[1] in loaded


if __name__ == "__main__":
    pytest.main([__file__, "-v"])