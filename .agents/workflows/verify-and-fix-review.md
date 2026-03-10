---
description: Workflow để tự động kiểm chứng các bug từ báo cáo review (Real-world testing) và tiến hành fix.
---

Workflow này giúp bạn xác minh xem các bug được báo cáo trong Review có thực sự tồn tại trong môi trường thực tế (Real-world project) hay không, sau đó tiến hành sửa lỗi một cách bài bản.

### Các bước thực hiện:

1. **Phân tích báo cáo Review**:
   - Đọc kỹ danh sách bug.
   - Xác định file, hàm và điều kiện gây lỗi.

2. **Tạo kịch bản tái hiện (Trigger Script)**:
   - Tạo một script Python (thường lưu vào `/tmp/trigger_bugs.py`) để gọi trực tiếp các module nghiệp vụ của Synapse.
   - Sử dụng một dự án thực tế (ví dụ: project hiện tại) làm workspace đầu vào cho script.
   - Script phải in ra rõ ràng trạng thái: `CONFIRMED` (nếu lỗi xảy ra) hoặc `NOT TRIGGERED`.

3. **Chạy script để kiểm chứng**:
// turbo
   - Chạy lệnh: `.venv/bin/python /tmp/trigger_bugs.py`
   - Ghi lại kết quả các bug đã được xác nhận.

4. **Tiến hành sửa lỗi (Fixing Phase)**:
   - Sử dụng công cụ `replace_file_content` hoặc `multi_replace_file_content` để áp dụng các bản vá.
   - Đảm bảo tuân thủ "Phần mềm sạch" (Clean Code) và comment tiếng Việt giải thích chức năng.

5. **Xác minh sau khi fix (Verification Phase)**:
   - Cập nhật script trigger ban đầu thành script xác minh (`/tmp/verify_fixes.py`).
   - Chạy script xác minh để đảm bảo trạng thái chuyển thành `FIXED`.
// turbo
   - Chạy bộ test suite của hệ thống: `.venv/bin/python -m pytest tests/test_workflows/` để tránh regression.

6. **Commit và Hoàn tất**:
   - Sử dụng skill `commit` để lưu lại các thay đổi với message chuẩn Conventional Commits.
   - Cập nhật thông tin vào Memory MCP.

### Gợi ý cho Script Trigger mẫu:
```python
import sys
from pathlib import Path
sys.path.append("/home/hao/Desktop/labs/Synapse-Desktop")
# Import các module cần test...

def test_bug_x():
    # Logic tái hiện lỗi
    pass

if __name__ == "__main__":
    test_bug_x()
```