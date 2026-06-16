# Hướng Dẫn Sử Dụng Tính Năng Bản Quyền (Licensing Guide)

Tài liệu này hướng dẫn cách khởi chạy ứng dụng Synapse Desktop với các chế độ bản quyền, cách cấu hình sản phẩm trên Gumroad và cơ chế kích hoạt trực tuyến.

---

## Bước 1: Khởi chạy ứng dụng (Bật/Tắt kiểm tra bản quyền)

Mặc định ứng dụng sẽ kiểm tra xem đã có key bản quyền trong cài đặt hay chưa. Tuy nhiên, lập trình viên có thể tùy chọn bật/tắt tính năng này để thuận tiện cho việc phát triển.

### 1.1 Khởi chạy chế độ phát triển (Bỏ qua kiểm tra bản quyền)
Script khởi chạy mặc định của dự án đã được tích hợp sẵn tham số `--no-license`:
```bash
./start.sh
```
Hoặc chạy trực tiếp bằng python:
```bash
PYTHONPATH=. .venv/bin/python main.py --no-license
```
* **Kết quả:** Ứng dụng bỏ qua tất cả kiểm tra bản quyền và vào thẳng màn hình chính.

### 1.2 Khởi chạy chế độ kiểm thử bản quyền (Bật kiểm tra bản quyền)
Để kiểm tra giao diện kích hoạt hoặc luồng xác thực thực tế với Gumroad API:
```bash
PYTHONPATH=. .venv/bin/python main.py
```
* **Kết quả:** Nếu chưa có key bản quyền lưu trong cài đặt, hộp thoại **"Activate Synapse Desktop"** sẽ xuất hiện yêu cầu bạn nhập License Key để kích hoạt.

---

## Bước 2: Tạo sản phẩm và License Key trên Gumroad

Thay vì tự sinh key offline bằng tool, chúng ta sử dụng hệ thống quản lý bản quyền của Gumroad:

1. Đăng nhập vào tài khoản Gumroad của bạn và chọn **New Product**.
2. Chọn loại sản phẩm là **Digital product**.
3. Trong phần cấu hình sản phẩm, hãy bật tùy chọn **Generate unique license keys per sale** (Gumroad sẽ tự động tạo key cho mỗi đơn hàng của khách hàng).
4. Lưu và xuất bản sản phẩm. Lấy **Product ID** từ trang chi tiết sản phẩm của Gumroad.
5. Cập nhật Product ID vào class `GumroadLicenseService` tại file `infrastructure/adapters/license_service.py`:
   ```python
   DEFAULT_PRODUCT_ID = "YOUR_GUMROAD_PRODUCT_ID"  # Thay bằng ID sản phẩm thực tế của bạn
   ```

---

## Bước 3: Kích hoạt ứng dụng

1. Chạy ứng dụng ở chế độ kiểm thử (Bước 1.2).
2. Nhập key bản quyền nhận được từ Gumroad (định dạng thường là `XXXX-XXXX-XXXX-XXXX`).
3. Click **Activate**.
4. Ứng dụng sẽ gọi API trực tuyến của Gumroad (`POST https://api.gumroad.com/v2/licenses/verify`) để kiểm tra:
   - Nếu Key hợp lệ: Key sẽ được lưu vào file cấu hình `settings.json`, hộp thoại đóng lại và màn hình chính hiện ra.
   - Nếu Key không hợp lệ hoặc đã bị hoàn tiền (Refunded)/Tranh chấp (Disputed): Thông báo lỗi chi tiết sẽ được hiển thị.

---

## Bước 4: Kiểm tra và Hủy kích hoạt (Deactivate)

1. Trên giao diện chính của Synapse Desktop, chọn tab **Settings** (biểu tượng bánh răng ở góc dưới).
2. Tại phần **Product Licensing**, bạn sẽ thấy thông tin chi tiết bản quyền:
   - Key bản quyền đã được che bớt ký tự để bảo mật.
   - Email người mua bản quyền.
   - Trạng thái bản quyền.
3. Để hủy kích hoạt bản quyền trên thiết bị hiện tại (ví dụ: khi muốn chuyển sang máy khác):
   - Nhấp vào nút **Deactivate License**.
   - Xác nhận **Yes**.
   - **Kết quả:** Ứng dụng xóa key bản quyền khỏi cài đặt cục bộ và thoát chương trình. Lần chạy tiếp theo sẽ yêu cầu kích hoạt lại.

* **Mẹo gỡ License nhanh bằng dòng lệnh (CLI) để test:**
  Nếu bạn muốn gỡ nhanh license key mà không cần mở giao diện của phần mềm, hãy chạy lệnh Python một dòng sau trong Terminal:
  ```bash
  python3 -c "import json, pathlib; p = pathlib.Path.home() / '.config/synapse-desktop/settings.json'; d = json.loads(p.read_text()) if p.exists() else {}; d['license_key'] = ''; p.write_text(json.dumps(d, indent=4))"
  ```

---

## Lưu ý kỹ thuật cho Lập trình viên

* **Vị trí lưu Key:** Key sau khi kích hoạt thành công được lưu tại `~/.config/synapse-desktop/settings.json` (trường `"license_key"`).
* **Cơ chế offline:** Ứng dụng **chỉ gọi API Gumroad trực tuyến 1 lần duy nhất lúc kích hoạt**. Khi khởi động các lần tiếp theo, ứng dụng chỉ kiểm tra xem trường `license_key` trong cài đặt có khác rỗng hay không, giúp khởi động cực kỳ nhanh và hoạt động offline hoàn toàn.
* **Cơ chế Feature Flag:** Để đóng gói sản phẩm thương mại (AppImage trên Linux, EXE trên Windows), quá trình build mặc định sẽ không truyền tham số `--no-license`, bắt buộc ứng dụng phải được kích hoạt bản quyền qua giao diện để có thể sử dụng.
* **Hướng dẫn đóng gói (Build) sản phẩm:**
  * **Trên Linux (AppImage):**
    * **Build bình thường** (yêu cầu kích hoạt bản quyền khi khởi chạy):
      ```bash
      ./build-appimage.sh
      ```
    * **Build bỏ qua bản quyền** (bản cá nhân):
      ```bash
      ./build-appimage.sh --no-license
      ```
  * **Trên Windows (EXE - chạy qua PowerShell):**
    * **Build bình thường** (yêu cầu kích hoạt bản quyền khi khởi chạy):
      ```powershell
      .\build-windows.ps1
      ```
    * **Build bỏ qua bản quyền** (bản cá nhân):
      ```powershell
      .\build-windows.ps1 -NoLicense
      ```

