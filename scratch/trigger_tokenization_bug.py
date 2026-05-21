import sys

# Thêm thư mục gốc của dự án vào sys.path để import các module domain
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from domain.tokenization.cache import TokenCache


def test_cache_underutilization_bug():
    print("=== Test 1: Lỗi sử dụng dưới dung lượng Cache (Under-utilization) ===")
    # Khởi tạo cache với kích thước tối đa là 2
    cache = TokenCache(max_size=2)

    # 1. Đưa vào 2 entries (cache hiện tại đã đầy)
    print("Đưa vào a.py và b.py...")
    cache.put("a.py", 1.0, 10)
    cache.put("b.py", 1.0, 20)
    print(f"Kích thước Cache: {len(cache)}")
    print(f"Trạng thái store: {list(cache._store.keys())}")

    # 2. Cập nhật b.py. Vì b.py đã tồn tại, số lượng key riêng biệt trong cache
    # vẫn là 2. Chúng ta KHÔNG cần loại biên (evict) bất kỳ entry nào.
    print("\nCập nhật b.py (update key đã tồn tại)...")
    cache.put("b.py", 2.0, 25)

    # Kiểm tra xem a.py còn trong cache không
    a_val = cache.get("a.py", 1.0)
    b_val = cache.get("b.py", 2.0)

    print(f"Kích thước Cache sau khi update: {len(cache)}")
    print(f"Trạng thái store: {list(cache._store.keys())}")
    print(f"Giá trị của a.py (kỳ vọng 10): {a_val}")
    print(f"Giá trị của b.py (kỳ vọng 25): {b_val}")

    if a_val is None:
        print("❌ XÁC NHẬN LỖI: a.py đã bị loại biên sớm khỏi cache khi cập nhật b.py!")
    else:
        print("✅ Thành công: cả hai item vẫn còn trong cache.")


def test_cache_lru_violation_bug():
    print("\n=== Test 2: Lỗi vi phạm thứ tự LRU (Least Recently Used) ===")
    # Khởi tạo cache với kích thước tối đa là 3
    cache = TokenCache(max_size=3)

    print("Đưa vào a.py và b.py (kích thước hiện tại = 2 < 3)...")
    cache.put("a.py", 1.0, 10)
    cache.put("b.py", 1.0, 20)
    print(f"Store ban đầu: {list(cache._store.keys())}")

    # Cập nhật a.py. Trong thuật toán LRU chuẩn, a.py phải được chuyển về cuối (MRU - Most Recently Used).
    # Tuy nhiên, trong code hiện tại, hàm put() chỉ gán self._store[path] = (mtime, count) mà không thay đổi thứ tự.
    print("\nCập nhật a.py (lẽ ra phải đưa a.py thành MRU - chuyển về sau b.py)...")
    cache.put("a.py", 2.0, 15)
    print(f"Store sau khi cập nhật a.py: {list(cache._store.keys())}")

    # Đưa vào c.py để đầy cache (kích thước = 3)
    print("\nĐưa vào c.py để đầy cache...")
    cache.put("c.py", 1.0, 30)
    print(f"Store sau khi thêm c.py: {list(cache._store.keys())}")

    # Thêm d.py (sẽ kích hoạt việc loại biên phần tử đầu tiên vì kích thước đã đạt 3)
    print("\nThêm d.py (sẽ kích hoạt loại biên phần tử đầu tiên)...")
    cache.put("d.py", 1.0, 40)
    print(f"Store sau khi thêm d.py: {list(cache._store.keys())}")

    # Vì a.py vẫn đứng đầu OrderedDict, nó bị loại biên mặc dù b.py mới là phần tử cũ nhất!
    if "a.py" not in cache._store:
        print(
            "❌ XÁC NHẬN LỖI: a.py bị loại biên dù đã được cập nhật gần đây nhất (b.py cũ hơn nhưng không bị loại biên)!"
        )
    else:
        print("✅ Thành công: Thứ tự LRU được đảm bảo.")


if __name__ == "__main__":
    test_cache_underutilization_bug()
    test_cache_lru_violation_bug()
