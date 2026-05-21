import sys
import os
import time
import threading
from pathlib import Path
import shutil

# Thêm thư mục gốc của dự án vào sys.path để import các module

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from infrastructure.filesystem.file_watcher.service import FileWatcher
from application.interfaces.file_watcher_port import WatcherCallbacks
from watchdog.events import FileModifiedEvent


class MockController:
    def __init__(self):
        self.widget_alive = True

    def on_file_modified(self, path: str) -> None:
        # Hàm xử lý khi nhận được thông báo file bị sửa đổi
        print(f"Callback on_file_modified được gọi với path: {path}")
        if not self.widget_alive:
            print(
                "CRITICAL ERROR: Đang cố gắng truy cập vào Widget/Controller đã bị hủy!"
            )
            # Ném ra lỗi tương tự như lỗi của PySide6 khi truy cập C++ object đã bị xóa
            raise RuntimeError(
                "wrapped C/C++ object of type ContextViewQt has been deleted"
            )


def run_trigger():
    # Tạo thư mục tạm để theo dõi
    temp_dir = Path(__file__).resolve().parent.parent / "scratch_temp_watcher"
    temp_dir.mkdir(parents=True, exist_ok=True)

    test_file = temp_dir / "test.txt"
    test_file.write_text("nội dung ban đầu")

    controller = MockController()
    watcher = FileWatcher()

    print("Đang khởi động File Watcher...")
    watcher.start(
        temp_dir,
        callbacks=WatcherCallbacks(on_file_modified=controller.on_file_modified),
        debounce_seconds=0.1,
    )

    time.sleep(0.1)  # Chờ watchdog observer khởi động xong

    # Lưu lại reference của handler trước khi watcher xóa nó trong lúc stop
    handler = watcher._handler

    print("Đang dừng File Watcher...")
    watcher.stop()

    # Giả lập sự kiện hủy/giải phóng widget trong UI thread
    controller.widget_alive = False

    print("Mô phỏng sự kiện sửa đổi file đồng thời / ngay sau khi stop...")
    mock_event = FileModifiedEvent(str(test_file))

    # Chạy việc dispatch sự kiện trên một thread nền riêng biệt (giống hành vi của Watchdog)
    def dispatch_event():
        handler.on_modified(mock_event)

    t = threading.Thread(target=dispatch_event)
    t.start()
    t.join()

    # Chờ debouncer timer kích hoạt callback (nếu timer được lên lịch thành công sau khi stop)
    time.sleep(0.5)

    # Dọn dẹp thư mục tạm
    shutil.rmtree(temp_dir)
    print("Kết thúc chạy thử nghiệm.")


if __name__ == "__main__":
    run_trigger()
