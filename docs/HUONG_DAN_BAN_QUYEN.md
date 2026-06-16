# Hướng Dẫn Sử Dụng Tính Năng Bản Quyền (Licensing Guide)

Tài liệu này hướng dẫn bạn cách khởi chạy, tạo mã kích hoạt (License Key) và kích hoạt/hủy kích hoạt bản quyền cho ứng dụng **Synapse Desktop** trên nhánh phát triển `feature/licensing-integration`.

---

## Bước 1: Chuyển sang nhánh tính năng bản quyền
Nếu bạn đang ở nhánh khác, hãy mở terminal tại thư mục dự án và chuyển sang nhánh `feature/licensing-integration`:
```bash
git checkout feature/licensing-integration
```

---

## Bước 2: Khởi chạy ứng dụng (Khi chưa kích hoạt)
Khởi động ứng dụng bằng script có sẵn:
```bash
./start.sh
```
Hoặc dùng lệnh python trực tiếp:
```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/python main.py
```
**Kết quả mong đợi:** 
Cửa sổ chính của ứng dụng sẽ **không** hiện lên. Thay vào đó, một hộp thoại màu tối sang trọng mang tên **"Activate Synapse Desktop"** sẽ xuất hiện yêu cầu bạn nhập License Key để kích hoạt.

---

## Bước 3: Tạo License Key hợp lệ (Developer Tool)
Mở một cửa sổ terminal mới (hoặc tạm dừng app) và chạy lệnh sau để sinh ra một mã kích hoạt dùng thử:

* **Tạo Key có thời hạn 365 ngày (cho email `dev@test.com`):**
  ```bash
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/python tools/license_generator.py --id LIC-DEV-99 --email dev@test.com --days 365
  ```

* **Tạo Key trọn đời (Lifetime - Mua 1 lần):**
  ```bash
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/python tools/license_generator.py --id LIC-LIFE-99 --email dev@test.com --lifetime
  ```

* **Kết quả hiển thị trên terminal:**
  ```text
  === GENERATED LICENSE KEY ===
  SYNAPSE-KEY.eyJsaWNlbnNlX2lkIjoiTElDLURFVi05OSIsImVtYWlsIjoiZGV2QHN5bmFwc2UuY29tIiwiZXhwaXJ5X2RhdGUiOiIyMDI3LTA2LTE2IiwicHJvZHVjdCI6IlN5bmFwc2UgRGVza3RvcCJ9._5HUQ2FSsfevsNnZ59c_HEMwYD8sdElU58LLcxkepdwYt8QIVGKYIoNqzPCFC3GJAA6HP7Pe515p_-eZjCF9Dw
  =============================
  ```
  *(Hãy bôi đen và copy toàn bộ chuỗi ký tự bắt đầu bằng `SYNAPSE-KEY.` cho đến hết)*

---

## Bước 4: Kích hoạt ứng dụng
1. Quay lại hộp thoại **Activate Synapse Desktop** đang mở.
2. Dán (Paste) chuỗi License Key vừa copy ở Bước 3 vào ô nhập liệu.
3. Nhấp vào nút **Activate**.
4. **Kết quả:** Hộp thoại sẽ đóng lại và cửa sổ chính của Synapse Desktop sẽ xuất hiện!

---

## Bước 5: Kiểm tra và Hủy kích hoạt (Deactivate)
1. Trên giao diện chính của Synapse Desktop, chọn tab **Settings** (biểu tượng bánh răng ở góc dưới).
2. Tại cột thứ 3 (phía dưới mục *MCP Server Integration*), bạn sẽ thấy một thẻ mới mang tên **Product Licensing** hiển thị chi tiết thông tin bản quyền của bạn (Mã số bản quyền, Email sở hữu, Ngày hết hạn).
3. Để gỡ bỏ bản quyền (ví dụ khi muốn chuyển sang máy khác):
   - Nhấp vào nút **Deactivate License**.
   - Hộp thoại xác nhận sẽ hiện ra. Chọn **Yes**.
   - **Kết quả:** Ứng dụng sẽ tự động xóa key bản quyền trong file cài đặt và đóng phần mềm. Lần khởi chạy kế tiếp sẽ tiếp tục yêu cầu nhập key bản quyền từ đầu.

---

## Lưu ý kỹ thuật cho Lập trình viên
* **Vị trí lưu Key:** Key bản quyền sau khi kích hoạt thành công sẽ được lưu tại file `~/.synapse-desktop/settings.json` dưới trường `"license_key"`.
* **Cơ chế bảo mật:** Thuật toán sử dụng là **Ed25519** (mật mã hóa bất đối xứng). 
  - Khóa công khai (**Public Key**) được nhúng cứng trong file `infrastructure/adapters/license_service.py`.
  - Khóa bí mật (**Private Key**) nằm trong công cụ `tools/license_generator.py` dùng để ký số ra License Key. Khi triển khai thực tế trên môi trường Production, khóa bí mật này phải được cất giữ trên server kích hoạt và không được đóng gói cùng ứng dụng.
