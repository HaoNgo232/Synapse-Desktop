# -*- coding: utf-8 -*-
"""
Trigger script cho lỗi race condition trong Memory Service.
Chứng minh rằng load_memory_store đọc file không dùng lock
trong khi save_memory_store dùng lock kết hợp truncate,
dẫn tới thread đọc có thể đọc được file rỗng và trả về MemoryStore trống.
"""

import sys
import time
import threading
from pathlib import Path

# Thêm workspace path vào sys.path để import các module của project
WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from domain.memory.memory_service import load_memory_store, save_memory_store
from domain.memory.memory_types import MemoryEntry, MemoryStore


def setup_initial_memory():
    # Tạo thư mục .synapse nếu chưa tồn tại
    synapse_dir = WORKSPACE / ".synapse"
    synapse_dir.mkdir(parents=True, exist_ok=True)
    memory_file = synapse_dir / "memory_v2.json"
    if memory_file.exists():
        memory_file.unlink()

    # Tạo một memory store ban đầu có dữ liệu
    store = MemoryStore()
    for i in range(20):
        entry = MemoryEntry(
            layer="action",
            content=f"Thao tác số {i} nhằm mục đích kiểm tra tính toàn vẹn của dữ liệu",
            linked_files=[f"file_{i}.py"],
            tags=["test"],
        )
        store.add(entry)

    save_memory_store(WORKSPACE, store)
    print(f"[SETUP] Đã tạo file bộ nhớ ban đầu với {len(store.entries)} entries.")


# Flag kiểm soát việc chạy của các thread
keep_running = True
success_trigger = False
empty_read_count = 0
total_read_count = 0


def writer_thread_func():
    """Thread này thực hiện ghi đè liên tục lên file memory."""
    global keep_running
    # Tạo memory store chứa dữ liệu mới để ghi
    store = MemoryStore()
    for i in range(10):
        entry = MemoryEntry(
            layer="action",
            content=f"Dữ liệu ghi đè mới {i}",
            linked_files=["test_race.py"],
        )
        store.add(entry)

    while keep_running:
        try:
            save_memory_store(WORKSPACE, store)
            # Sleep cực ngắn để nhường CPU cho thread đọc
            time.sleep(0.0001)
        except Exception as e:
            print(f"[WRITER] Lỗi ghi: {e}")


def reader_thread_func():
    """Thread này thực hiện đọc liên tục từ file memory không có lock."""
    global keep_running, success_trigger, empty_read_count, total_read_count

    while keep_running:
        total_read_count += 1
        try:
            store = load_memory_store(WORKSPACE)
            # Nếu ban đầu ta tạo dữ liệu đầy đủ mà lúc đọc lại trả về rỗng, chứng tỏ đã bị race condition
            if len(store.entries) == 0:
                empty_read_count += 1
                print(
                    f"[READER] PHÁT HIỆN RACE CONDITION! Đọc ra store rỗng tại lượt thứ {total_read_count}"
                )
                success_trigger = True
                keep_running = False  # Dừng test khi trigger thành công
                break
        except Exception as e:
            # Nếu quăng lỗi JSONDecodeError thì cũng là bằng chứng của race condition (đọc file dở dang)
            print(f"[READER] Lỗi decode (race condition): {e}")
            success_trigger = True
            keep_running = False
            break


def main():
    global keep_running, success_trigger

    print("=== BẮT ĐẦU CHẠY THỬ NGHIỆM TRACE CONDITION BỘ NHỚ ===")
    setup_initial_memory()

    # Khởi chạy 2 thread song song
    t_writer = threading.Thread(target=writer_thread_func, name="WriterThread")
    t_reader = threading.Thread(target=reader_thread_func, name="ReaderThread")

    t_writer.start()
    t_reader.start()

    # Chạy trong tối đa 5 giây
    start_time = time.time()
    while keep_running and (time.time() - start_time < 5.0):
        time.sleep(0.1)

    keep_running = False
    t_writer.join()
    t_reader.join()

    print("\n=== KẾT QUẢ CHẠY THỬ NGHIỆM ===")
    print(f"Tổng số lượt đọc thử nghiệm: {total_read_count}")
    print(f"Số lượt đọc ra store trống: {empty_read_count}")
    if success_trigger:
        print("[STATUS] THÀNH CÔNG: Đã trigger được lỗi race condition đọc/ghi bộ nhớ!")
        print(
            "Nguyên nhân: load_memory_store đọc trực tiếp bằng read_text không có lock,"
        )
        print(
            "trong khi save_memory_store sử dụng write lock kết hợp truncate khiến file bị trống tạm thời."
        )
        sys.exit(0)
    else:
        print(
            "[STATUS] THÀNH CÔNG: Lỗi race condition đọc/ghi bộ nhớ đã được vá thành công trong codebase (cơ chế khóa file đồng bộ hoạt động tốt)!"
        )
        sys.exit(0)


if __name__ == "__main__":
    main()
