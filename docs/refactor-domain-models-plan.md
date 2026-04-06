# PLAN: Refactor Domain Models (Clean Architecture Alignment)

Mục tiêu: Di chuyển các Data Models/Enums đang nằm sai layer (Infrastructure/Presentation) về đúng Domain Layer để tuân thủ quy tắc phụ thuộc một chiều (Inwards Dependency Rule).

## 🛠 Các bước thực hiện

### Bước 1: Di chuyển `TreeItem`
- **Nguồn:** `infrastructure/filesystem/file_utils.py`
- **Đích:** `domain/models/workspace.py` (Tạo mới)
- **Lý do:** `TreeItem` đại diện cho cấu trúc workspace, là một domain entity/value object quan trọng mà các layer khác phụ thuộc vào.

### Bước 2: Di chuyển `GitDiffResult` và `GitLogResult`
- **Nguồn:** `infrastructure/git/git_utils.py`
- **Đích:** `domain/models/git.py` (Tạo mới)
- **Lý do:** Đây là các cấu trúc dữ liệu chứa kết quả từ Git, được sử dụng trong business logic build prompt.

### Bước 3: Di chuyển `OutputStyle`
- **Nguồn:** `presentation/config/output_format.py`
- **Đích:** `domain/models/output.py` (Tạo mới)
- **Lý do:** Định dạng đầu ra (XML, JSON, Markdown) ảnh hưởng trực tiếp đến logic format trong Domain layer.

### Bước 4: Cập nhật Import toàn bộ dự án
- Cập nhật tất cả các file đang import các model này từ vị trí cũ sang vị trí mới.
- Ưu tiên sử dụng absolute imports.

### Bước 5: Kiểm chứng (Verification)
- Chạy `ruff check .` để kiểm tra linting.
- Chạy `pytest tests/test_prompt_generator.py` và các test liên quan để đảm bảo không làm hỏng logic hiện tại.

## 👥 Các Agent tham gia
- **Explorer Agent**: Đã quét toàn bộ dự án để tìm các file cần cập nhật import.
- **Backend Specialist**: Thực hiện việc di chuyển code và fix imports.
- **Test Engineer**: Chạy test và kiểm tra chất lượng code sau refactor.

## ⚠️ Rủi ro & Lưu ý
- **Circular Imports**: Cần cẩn thận khi di chuyển `TreeItem` vì nó có thể được import ở nhiều nơi. Sử dụng `TYPE_CHECKING` nếu cần.
- **Breaking Changes**: Đảm bảo cập nhật cả các file test.
