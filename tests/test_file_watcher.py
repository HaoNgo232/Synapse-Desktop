"""
Unit tests cho FileWatcher service.

Test các chức năng:
- Start/Stop không gây crash
- Callback được gọi khi có file change
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import Mock


from services.file_watcher import FileWatcher


class TestFileWatcher:
    """Test suite cho FileWatcher"""

    def test_init_creates_instance(self):
        """Test khởi tạo FileWatcher không lỗi"""
        watcher = FileWatcher()
        assert watcher is not None
        assert watcher._observer is None
        assert watcher.current_path is None

    def test_start_stop_no_crash(self):
        """Test start và stop không gây crash"""
        watcher = FileWatcher()
        callback = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)

            # Start watcher
            watcher.start(path, on_change=callback)
            assert watcher.is_running()
            assert watcher.current_path == path

            # Stop watcher
            watcher.stop()
            assert not watcher.is_running()
            assert watcher.current_path is None

    def test_start_invalid_path(self):
        """Test start với path không tồn tại"""
        watcher = FileWatcher()
        callback = Mock()

        # Start với path không tồn tại
        watcher.start(Path("/nonexistent/path/12345"), on_change=callback)

        # Watcher không nên chạy
        assert not watcher.is_running()

    def test_callback_on_file_created(self):
        """Test callback được gọi khi tạo file mới"""
        watcher = FileWatcher()
        callback = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)

            # Start với debounce ngắn để test nhanh
            watcher.start(path, on_change=callback, debounce_seconds=0.1)

            # Tạo file mới
            test_file = path / "new_file.txt"
            test_file.write_text("hello")

            # Đợi debounce + xử lý
            time.sleep(0.5)

            # Callback phải được gọi
            assert callback.called, "Callback nên được gọi khi có file mới"

            watcher.stop()

    def test_double_stop_no_crash(self):
        """Test gọi stop nhiều lần không crash"""
        watcher = FileWatcher()
        callback = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            watcher.start(path, on_change=callback)

            # Stop nhiều lần
            watcher.stop()
            watcher.stop()
            watcher.stop()

            # Không crash
            assert not watcher.is_running()

    def test_restart_different_path(self):
        """Test chuyển sang path khác tự động stop path cũ"""
        watcher = FileWatcher()
        callback = Mock()

        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                path1 = Path(tmpdir1)
                path2 = Path(tmpdir2)

                # Start path 1
                watcher.start(path1, on_change=callback)
                assert watcher.current_path == path1

                # Start path 2 (phải tự động stop path 1)
                watcher.start(path2, on_change=callback)
                assert watcher.current_path == path2

                watcher.stop()
