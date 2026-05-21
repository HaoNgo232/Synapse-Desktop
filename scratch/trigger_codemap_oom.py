import os
import sys
from pathlib import Path
import shutil
import time

# Thêm workspace vào python path để import được các domain modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from infrastructure.filesystem.file_utils import scan_directory
from infrastructure.filesystem.ignore_engine import IgnoreEngine

temp_dir = Path(PROJECT_ROOT) / "temp_oom_test"
if temp_dir.exists():
    shutil.rmtree(temp_dir)
temp_dir.mkdir()

try:
    # Tạo 2 thư mục con
    dir_a = temp_dir / "dirA"
    dir_b = temp_dir / "dirB"
    dir_a.mkdir()
    dir_b.mkdir()

    # Tạo circular symlink trỏ ngược lên thư mục cha ở cả 2 thư mục
    os.symlink(temp_dir, dir_a / "loop")
    os.symlink(temp_dir, dir_b / "loop")

    print("Đã tạo cấu trúc symlink lũy thừa (2 nhánh trỏ ngược lên cha).")
    print("Chuẩn bị quét thư mục bằng scan_directory...")

    ignore_engine = IgnoreEngine()

    start_time = time.time()
    # Chạy scan_directory (kỳ vọng sẽ bị treo hoặc tốn cực kỳ nhiều thời gian/bộ nhớ)
    # Ta sẽ đo thời gian, nếu vượt quá 3 giây thì coi như bị treo vĩnh viễn (do số lượng node là 2^40)
    result = scan_directory(temp_dir, ignore_engine, use_gitignore=False)
    end_time = time.time()

    print(f"Hoàn thành trong {end_time - start_time:.4f} giây.")

except Exception as e:
    print(f"Lỗi xảy ra: {type(e).__name__}: {e}")
finally:
    # Dọn dẹp symlinks trước để tránh rmtree bị lặp vô hạn
    try:
        if (dir_a / "loop").exists(follow_symlinks=False):
            (dir_a / "loop").unlink()
        if (dir_b / "loop").exists(follow_symlinks=False):
            (dir_b / "loop").unlink()
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    except Exception as e:
        print(f"Lỗi dọn dẹp: {e}")
