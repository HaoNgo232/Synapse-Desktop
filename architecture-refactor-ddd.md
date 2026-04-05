# Kế hoạch Tái cấu trúc Toàn diện (Clean Architecture + DDD)

## Tổng quan
Mục tiêu là tái cấu trúc toàn bộ dự án **Synapse-Desktop** theo mô hình **Clean Architecture** và **Domain-Driven Design (DDD)** nghiêm ngặt. Việc này giúp tách biệt logic nghiệp vụ khỏi các ràng buộc của framework (PySide6) và các chi tiết hạ tầng (Git, Filesystem, AI APIs), từ đó giúp việc debug, bảo trì và thêm tính năng trở nên dễ dàng hơn.

## Nguyên tắc cốt lõi
1. **Dependency Rule**: Luôn trỏ vào bên trong. Domain là trung tâm, không phụ thuộc vào bất kỳ layer nào khác.
2. **Abstractions over Concretions**: Application layer sử dụng các interfaces (Ports) thay vì gọi trực tiếp các module hạ tầng.
3. **Domain-Centric**: Logic quan trọng phải nằm trong Domain Entities/Aggregates.
4. **PySide6 Isolation**: Framework UI chỉ nằm ở outermost layer (Presentation).

## Cấu trúc thư mục mục tiêu
```plaintext
synapse_desktop/
├── domain/                # Core business logic (Pure Python)
│   ├── models/            # Entities, Value Objects, Aggregates
│   ├── services/          # Domain services (logic đa entity)
│   └── ports/             # Interfaces cho Repository, External Services
├── application/           # Use Cases (Orchestration)
│   ├── use_cases/         # Chứa các lớp xử lý một nghiệp vụ cụ thể
│   ├── dtos/              # Data Transfer Objects
│   └── interfaces/        # Application-specific ports
├── infrastructure/        # Adapters (Implementation)
│   ├── persistence/       # SQLite, Settings, File storage
│   ├── external/          # Git, MCP, AI Provider adapters
│   └── di/                # Dependency Injection container
├── presentation/          # Outermost layer (Frameworks)
│   ├── qt/                # PySide6 Widgets, Windows, Styles
│   └── cli/               # (Nếu có) Interface dòng lệnh
└── shared/                # Common utilities, constants, types
```

## Lộ trình thực hiện (Phases)

### Phase 1: Nền tảng & Cấu trúc (Infrastructure & Foundation)
- [ ] Thiết lập hệ thống Dependency Injection (DI) hoàn chỉnh.
- [ ] Chuyển `ServiceContainer` từ `application` ra `infrastructure/di` hoặc dùng một composition root tại điểm khởi đầu của app.
- [ ] Định nghĩa các Ports (Abstractions) cho: `IFileSystem`, `IGitRepository`, `ITokenizer`, `ISettingsProvider`.

### Phase 2: Domain Layer Rebuilding
- [ ] Phân tích và chuyển logic từ `PromptBuildService`, `GraphService` vào các Domain Aggregates.
- [ ] Đảm bảo `domain/` không chứa bất kỳ import nào từ `infrastructure` hoặc `PySide6`.

### Phase 3: Application Layer (Use Cases)
- [ ] Chia nhỏ các service lớn thành các Use Case Handler (Single Responsibility).
- [ ] Ví dụ: `BuildPromptUseCase`, `AnalyzeProjectStructureUseCase`.
- [ ] Xóa bỏ mọi sự phụ thuộc trực tiếp vào các module cụ thể của `infrastructure`.

### Phase 4: Infrastructure Layer (Adapters)
- [ ] Thực hiện các lớp Adapter cụ thể cho các interface đã định nghĩa ở Phase 1.
- [ ] Tách biệt logic xử lý File (vốn đang bị trộn lẫn) vào `LocalFileSystemAdapter`.

### Phase 5: Presentation Layer (PySide6 Refactoring)
- [ ] Refactor `main_window.py` để sử dụng các Use Cases thông thông qua DI.
- [ ] Đảm bảo View không chứa logic nghiệp vụ, chỉ chứa logic hiển thị và gọi Application layer.

### Phase 6: Kiểm chứng (Verification)
- [ ] Chạy lại toàn bộ unit/integration tests.
- [ ] Kiểm tra linting (`ruff`) và type-checking (`pyrefly`).

## Công việc hiện tại (Task List)
- [x] Tạo nhánh mới `arch/clean-ddd-refactor`.
- [x] Tạo ADR-001 (Architectural Decision Record).
- [ ] Task 1: Thiết lập cấu trúc thư mục mới và bắt đầu di chuyển các interface cơ bản.
- [ ] Task 2: Refactor `PromptBuildService` thành Use Case và định nghĩa các Ports phụ thuộc.
- [ ] Task 3: Chỉnh sửa DI container để inject các concrete adapters vào Use Case.

## Tiêu chí thành công
1. `pyrefly check` pass 100% với cấu trúc mới.
2. `pytest` pass toàn bộ.
3. Không có bất kỳ liên kết ngược (Inward imports violation).
4. App khởi động và hoạt động mượt mà với UI không bị block.

## Trọng tâm hiện tại: Tái cấu trúc UI (Presentation Layer)
Chúng ta sẽ chia nhỏ `SynapseMainWindow` vốn đang quá cồng kềnh thành các thành phần (components) độc lập, sử dụng mô hình **MVP (Model-View-Presenter)** hoặc **MVVM** (thông qua QObjects) để tách biệt logic hiển thị khỏi logic ứng dụng.

### Các thành phần cần tách:
- **TopBar**: Chứa thông tin project, memory, actions.
- **StatusBar**: Chứa thông tin Git, Version, Token count.
- **SideBar/Navigation**: Nếu cần mở rộng điều hướng.
- **ViewManager**: Quản lý việc chuyển đổi giữa các Tab/View.

### Quy trình thực hiện UI:
1. Tách `TopBar` thành component riêng.
2. Tách `StatusBar` thành component riêng.
3. Chuyển logic Session và Memory Monitor vào Application services.
4. Refactor `MainWindow` thành lớp điều phối tối giản.
