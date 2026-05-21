# -*- coding: utf-8 -*-
"""
Trigger script kiểm tra các lỗi trong lớp persistence:
1. Lỗi ghi đè trực tiếp (non-atomic write) trong settings_manager.py dẫn đến nguy cơ mất cấu hình khi crash/disk full.
2. Lỗi Race Condition trong history_service.py khi không có khóa đồng bộ hóa giữa các luồng.
3. Lỗi Race Condition trong recent_folders.py khi ghi đồng thời từ nhiều luồng.
"""

import sys
import time
import json
import shutil
import threading
from pathlib import Path

# Thêm workspace path vào sys.path để import các module của project
WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

# Lưu trữ lại đường dẫn gốc của app data để khôi phục sau khi test
from presentation.config import paths

# Thiết lập thư mục test tạm thời để không ảnh hưởng đến cấu hình thật của user
TEST_APP_DIR = WORKSPACE / "scratch" / "test_persistence_data"
if TEST_APP_DIR.exists():
    shutil.rmtree(TEST_APP_DIR)
TEST_APP_DIR.mkdir(parents=True, exist_ok=True)

# Ghi đè các hằng số paths để trỏ tới thư mục test
paths.APP_DIR = TEST_APP_DIR
paths.SETTINGS_FILE = TEST_APP_DIR / "settings.json"
paths.SESSION_FILE = TEST_APP_DIR / "session.json"
paths.HISTORY_FILE = TEST_APP_DIR / "history.json"
paths.RECENT_FOLDERS_FILE = TEST_APP_DIR / "recent_folders.json"

# Import các service cần test
from infrastructure.persistence import settings_manager
from infrastructure.persistence import history_service
from infrastructure.persistence import recent_folders
from presentation.config.app_settings import AppSettings


def test_settings_non_atomic_write():
    print(
        "\n--- 1. KIỂM TRA LỖI GHI ĐÈ TRỰC TIẾP (NON-ATOMIC WRITE) TRONG SETTINGS_MANAGER ---"
    )

    # Thiết lập cấu hình ban đầu
    settings = AppSettings(
        model_id="original-model-123", enable_security_check=True, use_gitignore=False
    )
    success = settings_manager.save_app_settings(settings)
    print(f"[TEST 1] Lưu cấu hình ban đầu: {success}")

    # Kiểm tra cấu hình đã lưu
    loaded = settings_manager.load_app_settings()
    print(f"[TEST 1] Đọc cấu hình ban đầu, model_id = '{loaded.model_id}'")

    # Giả lập tình trạng Disk Full hoặc Crash khi đang ghi đè file cấu hình
    print(
        "[TEST 1] Giả lập tiến trình bị tắt đột ngột (crash/power loss) hoặc đĩa đầy giữa chừng khi đang ghi đè settings.json..."
    )

    # Để giả lập điều này, ta mô phỏng việc mở file để ghi đè nhưng chỉ ghi một phần hoặc file trống
    # Trong settings_manager.py, việc ghi đè diễn ra trực tiếp qua write_text()
    # Khi write_text() được gọi, file bị truncated (độ dài = 0) và bắt đầu ghi dữ liệu
    # Nếu tiến trình bị kill ngay lúc này hoặc đĩa đầy, file settings.json sẽ trống rỗng hoặc không hợp lệ.
    try:
        # Mở file ghi đè nhưng bị lỗi nửa chừng (kết quả file trống)
        with open(paths.SETTINGS_FILE, "w", encoding="utf-8") as f:
            f.write('{ "model_id": "new-model", ')  # Ghi JSON dang dở, lỗi cú pháp
            # Giả sử bị kill đột ngột ở đây, không đóng file hoặc ghi tiếp được
    except Exception as e:
        print(f"[TEST 1] Lỗi giả lập: {e}")

    print(
        f"[TEST 1] Trạng thái file settings.json hiện tại: size={paths.SETTINGS_FILE.stat().st_size} bytes"
    )
    print(
        f"[TEST 1] Nội dung file settings.json bị hỏng: '{paths.SETTINGS_FILE.read_text(encoding='utf-8')}'"
    )

    # Load lại cấu hình xem có khôi phục được không
    print("[TEST 1] Thực hiện load_app_settings() sau khi file bị hỏng...")
    recovered = settings_manager.load_app_settings()

    print(f"[TEST 1] Kết quả khôi phục: model_id = '{recovered.model_id}'")
    if recovered.model_id != "original-model-123":
        print(
            "[LỖI NGHIÊM TRỌNG] THÀNH CÔNG TRIGGER: Toàn bộ cấu hình của người dùng đã bị reset về mặc định do file settings.json bị hỏng!"
        )
        print(
            "Nguyên nhân: settings_manager.py ghi đè trực tiếp lên settings.json mà không dùng file tạm (atomic write)."
        )
    else:
        print(
            "[TEST 1] THẤT BẠI: File cấu hình vẫn giữ được dữ liệu cũ (điều này không thể xảy ra do file đã bị hỏng hoàn toàn)."
        )


def test_history_race_condition():
    print("\n--- 2. KIỂM TRA LỖI RACE CONDITION TRONG HISTORY_SERVICE ---")

    # Reset file history
    if paths.HISTORY_FILE.exists():
        paths.HISTORY_FILE.unlink()

    # Tạo danh sách các thao tác để add liên tục từ nhiều luồng
    num_threads = 5
    items_per_thread = 20
    threads = []

    print(
        f"[TEST 2] Khởi chạy {num_threads} luồng ghi lịch sử đồng thời (mỗi luồng ghi {items_per_thread} entries)..."
    )

    def worker(thread_idx):
        for i in range(items_per_thread):
            action_results = [
                {
                    "action": "MODIFY",
                    "path": f"file_t{thread_idx}_{i}.py",
                    "success": True,
                    "message": "Success",
                }
            ]
            history_service.add_history_entry(
                workspace_path=f"/mock/workspace/t{thread_idx}",
                opx_content=f"OPX content {thread_idx} - {i}",
                action_results=action_results,
            )
            # Sleep siêu ngắn để tăng tỉ lệ race condition xen kẽ
            time.sleep(0.001)

    for idx in range(num_threads):
        t = threading.Thread(target=worker, args=(idx,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Đọc lại lịch sử và đếm số entry thực tế được lưu lại
    entries = history_service.get_history_entries(limit=200)
    expected_total = num_threads * items_per_thread
    actual_total = len(entries)

    print(f"[TEST 2] Dự kiến số entries ghi thành công: {expected_total}")
    print(
        f"[TEST 2] Số entries thực tế được lưu lại trong history.json: {actual_total}"
    )

    # Kiểm tra xem có bị lỗi JSON Decode Error do các thread ghi chồng chéo hay không
    try:
        content = paths.HISTORY_FILE.read_text(encoding="utf-8")
        data = json.loads(content)
        print(
            f"[TEST 2] Đọc file JSON thành công. Số entries trong JSON: {len(data.get('entries', []))}"
        )
    except Exception as e:
        print(
            f"[LỖI CỰC KỲ NGHIÊM TRỌNG] File history.json bị hỏng cấu trúc JSON hoàn toàn: {e}"
        )

    if actual_total < expected_total:
        print(
            f"[LỖI] THÀNH CÔNG TRIGGER: Race condition xảy ra! Đã mất mát {expected_total - actual_total} entries lịch sử."
        )
        print(
            "Nguyên nhân: history_service.py hoàn toàn không có cơ chế Lock đồng bộ hóa giữa các luồng khi đọc-ghi file JSON."
        )
    else:
        print(
            "[TEST 2] Số entries trùng khớp (có thể do hệ thống chạy quá nhanh hoặc luồng không xen kẽ đủ tốt)."
        )


def test_recent_folders_race_condition():
    print("\n--- 3. KIỂM TRA LỖI RACE CONDITION TRONG RECENT_FOLDERS ---")

    if paths.RECENT_FOLDERS_FILE.exists():
        paths.RECENT_FOLDERS_FILE.unlink()

    num_threads = 5
    folders_to_add = [str(TEST_APP_DIR / f"folder_{i}") for i in range(num_threads)]

    # Tạo các thư mục mock trên đĩa vì recent_folders.py kiểm tra sự tồn tại của thư mục
    for f in folders_to_add:
        Path(f).mkdir(parents=True, exist_ok=True)

    threads = []
    print(f"[TEST 3] Khởi chạy {num_threads} luồng thêm thư mục gần đây đồng thời...")

    def worker(folder_path):
        recent_folders.add_recent_folder(folder_path)

    for f in folders_to_add:
        t = threading.Thread(target=worker, args=(f,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Đọc lại danh sách folders
    actual_folders = recent_folders.load_recent_folders()
    print(f"[TEST 3] Danh sách folders thực tế được lưu: {actual_folders}")

    # Dọn dẹp thư mục mock
    for f in folders_to_add:
        try:
            shutil.rmtree(Path(f))
        except OSError:
            pass

    if len(actual_folders) < num_threads:
        print(
            f"[LỖI] THÀNH CÔNG TRIGGER: Race condition xảy ra! Chỉ có {len(actual_folders)}/{num_threads} folders được lưu."
        )
        print(
            "Nguyên nhân: recent_folders.py không có Lock luồng bảo vệ khi ghi đè file recent_folders.json."
        )
    else:
        print(
            "[TEST 3] Toàn bộ folders được lưu thành công (hoặc luồng không xen kẽ đủ tốt)."
        )


def cleanup():
    # Khôi phục lại các paths
    # Dọn dẹp thư mục test tạm
    try:
        shutil.rmtree(TEST_APP_DIR)
        print("\n[CLEANUP] Đã dọn dẹp thư mục kiểm thử tạm thời.")
    except Exception as e:
        print(f"\n[CLEANUP] Lỗi dọn dẹp: {e}")


if __name__ == "__main__":
    try:
        test_settings_non_atomic_write()
        test_history_race_condition()
        test_recent_folders_race_condition()
    finally:
        cleanup()
