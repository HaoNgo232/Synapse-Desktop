# Spec: Refactoring Clean Architecture cho Synapse Desktop

- **Ngày tạo**: 2026-06-15
- **Trạng thái**: Chờ duyệt
- **Mục tiêu**: Refactor codebase để loại bỏ hoàn toàn các vi phạm kiến trúc (17 Import Violations và 2 Layer Cycles) được ghi nhận trong [baseline.json](file:///home/hao/Desktop/labs/Synapse-Desktop/tools/architecture/baseline.json).

---

## 1. Vấn đề Hiện tại

Theo báo cáo kiến trúc của Synapse Desktop:
* **Import Violations**: 17 vi phạm do lớp `presentation` (giao diện Qt) import trực tiếp từ lớp `infrastructure` (cơ sở dữ liệu, file system, git adapters, AI providers). Theo nguyên lý Clean Architecture, lớp Presentation và Infrastructure là các chi tiết bên ngoài, không được phép phụ thuộc trực tiếp vào nhau.
* **Layer Cycles**: Có 2 vòng lặp phụ thuộc (`application -> infrastructure -> application` và `infrastructure -> application -> infrastructure`) do lớp nghiệp vụ `application` import trực tiếp các concrete implementations của `infrastructure`, trong khi `infrastructure` lại import các interface và error định nghĩa tại `application`.

---

## 2. Giải pháp Đề xuất (Strict Clean Architecture)

Để giải quyết triệt để các vấn đề trên, chúng ta áp dụng mô hình **Dependency Inversion** kết hợp với **Service Locator (DomainRegistry)** làm composition root bổ sung:

```
                  ┌──────────────────────────────┐
                  │            Domain            │
                  │ (Models, Ports, Registry)    │
                  └──────────────▲───────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 │          Application          │
                 │    (Use Cases, Services)      │
                 └───────────────▲───────────────┘
                                 │
         ┌───────────────────────┴───────────────────────┐
         │                                               │
┌────────────────┐                               ┌────────────────┐
│  Presentation  │                               │ Infrastructure │
│ (Views, UI,    │─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─▶ (Adapters,      │
│  Container)    │    (Sử dụng DomainRegistry    │  Persistence)  │
└────────────────┘     để tránh import trực tiếp)└────────────────┘
```

---

## 3. Chi tiết các Thay đổi

### A. Lớp Domain & Application (Định nghĩa Interface và Models)

Chúng ta di chuyển các kiểu dữ liệu và định nghĩa các interface mới vào `domain/ports` để ngắt các import trực tiếp:

1. **`domain/ports/action_result.py`** [NEW]:
   * Định nghĩa dataclass `ActionResult` (di chuyển từ `infrastructure/filesystem/file_actions.py`).
2. **`domain/ports/ai_port.py`** [NEW]:
   * Định nghĩa dataclass `LLMMessage`, `LLMResponse` (di chuyển từ `infrastructure/ai/base_provider.py`).
   * Định nghĩa interface `IAIProvider` cho các LLM Operations.
3. **`domain/ports/repo_manager_port.py`** [NEW]:
   * Định nghĩa các dataclass `RemoteRepoInfo`, `CloneProgress`, `CachedRepo`.
   * Định nghĩa interface `IRepoManager` với các thao tác clone, cache.
4. **`domain/ports/settings_service_port.py`** [NEW]:
   * Định nghĩa interface `ISettingsService` kế thừa việc update/read setting, lưu history instruction.
5. **`domain/ports/ignore_engine_port.py`** [NEW]:
   * Định nghĩa interface `IIgnoreEngine` (thay thế cho concrete `IgnoreEngine`).
6. **`domain/ports/cache_registry_port.py`** [NEW]:
   * Định nghĩa interface `ICacheRegistry`.
7. **`domain/ports/file_actions_port.py`** [NEW]:
   * Định nghĩa interface `IFileActionsService` để thực thi file operations.
8. **`domain/ports/recent_folders_port.py`** [NEW]:
   * Định nghĩa interface `IRecentFoldersService`.
9. **`domain/ports/session_state_port.py`** [NEW]:
   * Định nghĩa interface `ISessionStateService`.

### B. Cập nhật `DomainRegistry` ([registry.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/ports/registry.py))

Bổ sung các phương thức đăng ký và truy xuất tĩnh cho các dịch vụ mới:
* `register_security_scanner` / `security_scanner`
* `register_repo_manager` / `repo_manager`
* `register_settings_service` / `settings_service`
* `register_recent_folders` / `recent_folders`
* `register_session_state` / `session_state`
* `register_cache_registry` / `cache_registry`
* `register_file_actions_service` / `file_actions_service`
* `register_file_watcher_service` / `file_watcher_service`
* `register_clipboard_service` / `clipboard_service`

### C. Cài đặt các Concrete Adapters trong `Infrastructure`

Chỉnh sửa các file ở `infrastructure/` để implement các interfaces được định nghĩa tại `domain/ports`:
* [repo_manager.py](file:///home/hao/Desktop/labs/Synapse-Desktop/infrastructure/git/repo_manager.py) implement `IRepoManager`.
* [settings_manager.py](file:///home/hao/Desktop/labs/Synapse-Desktop/infrastructure/persistence/settings_manager.py) implement `ISettingsService`.
* [recent_folders.py](file:///home/hao/Desktop/labs/Synapse-Desktop/infrastructure/persistence/recent_folders.py) implement `IRecentFoldersService`.
* [session_state.py](file:///home/hao/Desktop/labs/Synapse-Desktop/infrastructure/persistence/session_state.py) implement `ISessionStateService`.
* [file_watcher_facade.py](file:///home/hao/Desktop/labs/Synapse-Desktop/infrastructure/filesystem/file_watcher_facade.py) implement `IFileWatcherService`.
* [file_actions.py](file:///home/hao/Desktop/labs/Synapse-Desktop/infrastructure/filesystem/file_actions.py) implement `IFileActionsService`.
* [security_check.py](file:///home/hao/Desktop/labs/Synapse-Desktop/infrastructure/adapters/security_check.py) implement `ISecurityScanner`.

### D. Tách biệt UI Utility khỏi Infrastructure
* Tạo file [presentation/utils/clipboard.py](file:///home/hao/Desktop/labs/Synapse-Desktop/presentation/utils/clipboard.py) [NEW] và di chuyển hàm `copy_to_clipboard` sang đây để không dùng `clipboard_utils` của infrastructure.

### E. Tách biệt Composition Root ([service_container.py](file:///home/hao/Desktop/labs/Synapse-Desktop/presentation/service_container.py))
* Đăng ký tất cả concrete implementation của `infrastructure` vào `DomainRegistry` trong quá trình khởi tạo container.
* Đây là file duy nhất trong `presentation` được phép import từ `infrastructure` (được loại trừ trong script kiểm tra kiến trúc).

### F. Cập nhật Imports trong `Application` và `Presentation`
* Thay thế toàn bộ các import trực tiếp từ `infrastructure` bằng cách gọi qua `DomainRegistry.<service_name>()` hoặc import các models từ `domain/ports`.

---

## 4. Kế hoạch Kiểm thử & Xác minh

### A. Kiểm tra kiến trúc tĩnh
* Chạy script govern kiến trúc ở chế độ strict:
  ```bash
  python tools/architecture/check_architecture.py --strict
  ```
  * **Mong đợi**: Script exit code = 0 (Không còn vi phạm kiến trúc nào so với baseline trống).
  * Chạy `--write-baseline` để cập nhật baseline về trạng thái không có vi phạm (hoặc xóa các vi phạm cũ).

### B. Unit Testing
* Chạy toàn bộ các bài kiểm thử hiện có bằng pytest để đảm bảo tính năng không bị ảnh hưởng:
  ```bash
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v
  ```
  * **Mong đợi**: 100% test case (hơn 590+ tests) đều vượt qua.
