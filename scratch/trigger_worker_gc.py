import sys
import gc
import time
import os

# Thêm thư mục gốc của dự án vào sys.path để import các module

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import QCoreApplication, QTimer
from infrastructure.adapters.qt_utils import schedule_background


def heavy_task():
    # Giả lập một tác vụ nặng tốn thời gian
    time.sleep(0.5)
    return "done"


def on_result(res):
    # Callback xử lý kết quả trả về từ background thread
    print("SUCCESS: Callback đã được thực thi với kết quả:", res)


def run():
    print("Đang lên lịch chạy Background Worker...")
    # Lên lịch chạy tác vụ nhưng không lưu lại reference của worker
    schedule_background(heavy_task, on_result=on_result)

    # Ép buộc Python thực hiện Garbage Collection ngay lập tức
    # Việc này sẽ giải phóng Python wrapper của BackgroundWorker
    gc.collect()
    print("Garbage Collection đã được kích hoạt.")


if __name__ == "__main__":
    app = QCoreApplication(sys.argv)
    # Kích hoạt hàm chạy thử nghiệm
    QTimer.singleShot(0, run)
    # Tự động thoát ứng dụng sau 1 giây
    QTimer.singleShot(1000, app.quit)
    sys.exit(app.exec())
