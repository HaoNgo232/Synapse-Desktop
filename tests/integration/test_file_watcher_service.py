"""
Integration tests cho FileWatcher service.

Test viec inject custom IIgnoreStrategy va
tich hop giua Observer, Handler, Debouncer.
"""

import time
from pathlib import Path

from services.file_watcher_pkg.service import FileWatcher
from services.interfaces.file_watcher_service import (
    IIgnoreStrategy,
    WatcherCallbacks,
)


class CustomIgnoreStrategy(IIgnoreStrategy):
    """
    Custom strategy chi bo qua cac file co duoi .ignoreme
    va cac thu muc ten la 'secret_folder'.
    """

    def should_ignore(self, path: str) -> bool:
        path_obj = Path(path)
        if path_obj.suffix == ".ignoreme":
            return True
        if "secret_folder" in path_obj.parts:
            return True
        return False


class TestFileWatcherIntegration:
    """Test tich hop giua FileWatcher va custom strategy."""

    def test_custom_ignore_strategy_integration(self, tmp_path):
        """
        Test inject custom IgnoreStrategy vao FileWatcher
        dam bao cac file/folder do bi bo qua, con cac file khac duoc trigger.
        """
        # Tao file/folder
        normal_file = tmp_path / "normal.txt"
        ignored_file = tmp_path / "test.ignoreme"

        secret_dir = tmp_path / "secret_folder"
        secret_dir.mkdir()
        secret_file = secret_dir / "hidden.txt"

        # Tracker de theo doi cac events
        received_events = []

        def on_file_created(path: str):
            received_events.append(("created", path))

        callbacks = WatcherCallbacks(on_file_created=on_file_created)

        # Inject custom strategy
        custom_strategy = CustomIgnoreStrategy()
        watcher = FileWatcher(ignore_strategy=custom_strategy)

        # Start watcher voi debounce ngan
        watcher.start(tmp_path, callbacks=callbacks, debounce_seconds=0.1)

        try:
            # Tao cac file (trigger events)
            normal_file.write_text("hello")
            ignored_file.write_text("ignore me")
            secret_file.write_text("secret")

            # Doi watchdog bat events va debouncer trigger callback
            time.sleep(0.5)

            # Verification
            # Chi co normal.txt tao ra event, 2 file kia phai bi ignore boi strategy
            created_paths = [Path(path).name for _, path in received_events]

            assert "normal.txt" in created_paths, "Normal file phai duoc trigger"
            assert "test.ignoreme" not in created_paths, "Ignore file phai bi bo qua"
            assert "hidden.txt" not in created_paths, "Secret file phai bi bo qua"

        finally:
            watcher.stop()
