# Observability & Diagnostics — Design Spec

**Date:** 2026-06-17  
**Status:** Approved for implementation  
**Scope:** domain → infrastructure → application → presentation

---

## Background

Synapse Desktop đang nuốt âm thầm nhiều lỗi trong các background worker và
QTimer callback để tránh crash UI. Hậu quả: khi người dùng báo lỗi, developer
không có thông tin để tái hiện vấn đề, và người dùng không nhận được phản hồi
rõ ràng khi tác vụ nền thất bại.

**Khảo sát codebase (2026-06-17):**

| Layer | Số `except Exception:` câm (pass hoặc thiếu traceback) |
|---|---|
| `infrastructure/adapters/` | ~30+ |
| `infrastructure/git/` | ~7 |
| `presentation/` | ~14 |
| `application/` | ~11 |
| Tổng | **~62+** |

---

## Mục tiêu

1. **Dev experience:** Khi lỗi xảy ra, *luôn* thấy full traceback trên console — không cần đoán mò.
2. **User experience:** Khi background task thất bại mà caller không xử lý lỗi, người dùng thấy toast notification thay vì im lặng.
3. **Zero regression:** Không thay đổi behavior — chỉ thêm visibility. Tất cả `pass` hợp lý (shutdown path, icon fallback) được giữ nguyên nhưng ghi rõ lý do.

---

## Thiết kế — 3 tầng

### Tầng A: Infrastructure Safety Net (tự động, không cần sửa caller)

#### A1. `BackgroundWorker.run()` — thêm full traceback

**File:** `presentation/utils/qt_utils.py`

```python
# TRƯỚC:
except Exception as e:
    logger.error(f"BackgroundWorker error: {e}")

# SAU:
except Exception as e:
    logger.error(
        f"BackgroundWorker error in '{self.fn.__qualname__}': {e}",
        exc_info=True,  # full traceback in log
    )
```

#### A2. `schedule_background()` — default error handler

Khi caller không truyền `on_error`, hiện tại lỗi chỉ được log. Thêm fallback
tự động hiển thị toast cho người dùng:

```python
def _default_background_error_handler(msg: str) -> None:
    """Fallback khi schedule_background() không có on_error."""
    try:
        from presentation.components.toast.toast_qt import get_toast_manager
        mgr = get_toast_manager()
        if mgr:
            mgr.show_toast(f"Background task failed: {msg}", level="error")
    except Exception:
        pass  # intentionally silent — toast system may not be ready

def schedule_background(
    fn, on_result=None, on_error=None, on_finished=None, *args, **kwargs
):
    # ... existing code ...
    # Dùng default handler nếu caller không truyền on_error
    effective_on_error = on_error or _default_background_error_handler
    if effective_on_error:
        worker.signals.error.connect(effective_on_error)
    # ...
```

#### A3. `@guard_errors` decorator — cho QTimer và slot callback

**File mới:** `shared/error_guard.py`

```python
import functools
import logging
from typing import Callable, TypeVar, Any

F = TypeVar("F", bound=Callable[..., Any])
_logger = logging.getLogger("synapse-desktop")


def guard_errors(label: str | None = None) -> Callable[[F], F]:
    """
    Decorator bảo vệ hàm khỏi nuốt lỗi âm thầm.

    Khi hàm raise exception, decorator sẽ:
    - Log ERROR với full traceback (exc_info=True)
    - Trả về None (không propagate để tránh crash UI)

    Dùng cho: QTimer callback, @Slot method, bất kỳ hàm nào cần
    chạy không crash UI nhưng vẫn phải có visibility.

    Usage:
        @guard_errors("TokenCounter._on_timer")
        def _on_timer(self) -> None:
            ...

        @guard_errors()  # Dùng qualname tự động
        def my_callback() -> None:
            ...
    """
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except Exception:
                name = label or fn.__qualname__
                _logger.error(
                    f"Unhandled exception in '{name}'",
                    exc_info=True,
                )
                return None
        return wrapper  # type: ignore[return-value]
    return decorator
```

---

### Tầng B: Sweep `except Exception: pass` toàn bộ codebase

Phân loại và xử lý theo 3 tier:

#### Tier 1 — Critical: infrastructure/adapters (phải sửa hết)

Các file: `parallel_counter.py`, `safe_timer.py`, `async_queue.py`,
`background_processor.py`, `encoders.py`, `encoder_registry.py`,
`batch_updater.py`, `cache_registry.py`, `memory_monitor.py`,
`security_check.py`, `threading_utils.py`, `tokenization_service.py`,
`license_service.py`, `line_count_display.py`

**Pattern thay thế:**
```python
# TRƯỚC:
except Exception:
    pass

# SAU:
except Exception:
    logger.error("Context message describing what failed", exc_info=True)
```

#### Tier 2 — Important: infrastructure/git + infrastructure/filesystem + application/

Các file: `git_utils.py`, `repo_manager.py`, `file_scanner.py`,
`file_actions.py`, `history_service.py`, `settings_manager.py`,
`workflow_engine.py`, `apply_service.py`, `preview_analyzer.py`,
`workspace_config.py`, `workspace_index.py`, `plugins/registry.py`

**Pattern thay thế:** Giống Tier 1, với log message có context rõ ràng.

#### Tier 3 — Presentation + Defensive paths

Các file: `main_window.py`, `context_view_qt.py`, `copy_action_controller.py`,
`settings_view_qt.py`, `dialogs_qt.py`, `service_container.py`, v.v.

**Phân biệt 2 loại:**

a) **Shutdown/cleanup path** — giữ `pass` nhưng thêm comment:
```python
except Exception:
    pass  # intentionally silent — shutdown path, nothing we can do
```

b) **Runtime logic** — thêm log:
```python
except Exception:
    logger.warning("Failed to update UI component X", exc_info=True)
```

---

### Tầng C: Logging Context Enhancement

**File:** `shared/logging_config.py`

Thêm một helper để log kèm structured context (dùng cho các error phức tạp):

```python
def log_error_ctx(
    message: str,
    exc: Exception | None = None,
    **context: Any,
) -> None:
    """
    Log ERROR với full traceback và key-value context.

    Usage:
        log_error_ctx(
            "Token counter failed",
            exc,
            file=str(path),
            thread=threading.current_thread().name,
        )
    """
    logger = get_logger()
    ctx_str = " | ".join(f"{k}={v}" for k, v in context.items())
    full_msg = f"{message} [{ctx_str}]" if ctx_str else message
    logger.error(full_msg, exc_info=exc is not None or True)
```

---

## Quy tắc phân loại (để áp dụng nhất quán)

| Tình huống | Hành động |
|---|---|
| `except Exception: pass` trong background thread/worker | `logger.error(..., exc_info=True)` |
| `except Exception: pass` trong shutdown / `closeEvent` step | Giữ `pass`, thêm comment `# intentionally silent — shutdown` |
| `except Exception: pass` trong icon rendering / SVG fallback | Giữ `pass`, thêm comment `# intentionally silent — non-critical UI` |
| `except Exception as e: logger.error(str(e))` (thiếu traceback) | Thêm `exc_info=True` |
| `except RuntimeError: pass` trong signal emit khi shutdown | Giữ nguyên (đây là pattern đúng của Qt) |

---

## File thay đổi

### [NEW]
- `shared/error_guard.py` — `@guard_errors` decorator

### [MODIFY]
- `shared/logging_config.py` — thêm `log_error_ctx()`
- `presentation/utils/qt_utils.py` — nâng cấp `BackgroundWorker`, `schedule_background`

### [SWEEP — Tier 1] infrastructure/adapters/
- `parallel_counter.py` (~7 chỗ)
- `safe_timer.py` (~2 chỗ)
- `async_queue.py` (~1 chỗ)
- `background_processor.py` (~1 chỗ)
- `encoders.py` (~3 chỗ)
- `encoder_registry.py` (~2 chỗ)
- `batch_updater.py` (~3 chỗ)
- `cache_registry.py` (~1 chỗ)
- `memory_monitor.py` (~2 chỗ)
- `security_check.py` (~6 chỗ)
- `threading_utils.py` (~1 chỗ)
- `tokenization_service.py` (~1 chỗ)
- `license_service.py` (~1 chỗ)
- `line_count_display.py` (~2 chỗ)

### [SWEEP — Tier 2] infrastructure/git, filesystem, application/
- `git_utils.py` (~7 chỗ)
- `repo_manager.py` (~1 chỗ)
- `file_scanner.py` (~1 chỗ)
- `file_actions.py` (~2 chỗ)
- `history_service.py` (~1 chỗ)
- `settings_manager.py` (~2 chỗ)
- `workflow_engine.py` (~1 chỗ)
- `apply_service.py` (~1 chỗ)
- `preview_analyzer.py` (~3 chỗ)
- `workspace_config.py` (~3 chỗ)
- `workspace_index.py` (~1 chỗ)
- `plugins/registry.py` (~1 chỗ)

### [SWEEP — Tier 3] presentation/
- `main_window.py` (phân loại từng chỗ)
- `context_view_qt.py` (~3 chỗ)
- `copy_action_controller.py` (~3 chỗ)
- `settings_view_qt.py` (~3 chỗ)
- `dialogs_qt.py` (~4 chỗ)
- `service_container.py` (~1 chỗ)
- `ui_builder.py` (~1 chỗ)
- `file_tree_widget.py` (~1 chỗ)

---

## Verification Plan

### Automated

```bash
# 1. Sau khi sửa, không còn except Exception: pass không có comment
grep -rn "except Exception:\s*$" --include="*.py" domain/ infrastructure/ application/ presentation/ | grep -v "# intentionally"

# 2. Kiểm tra không có lỗi lint/type
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff check --fix .
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pyrefly check

# 3. Chạy toàn bộ test suite
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v
```

### Manual

1. Chạy app ở `SYNAPSE_DEBUG=1` mode, trigger một background task thất bại
   (vd: nhập API key sai → fetch models) → xác nhận toast hiện ra + traceback
   xuất hiện trên console
2. Kiểm tra `~/.synapse-desktop/logs/app.log` có đủ context sau khi restart
3. Đóng app đột ngột (Ctrl+C) → confirm không có exception mới từ shutdown path

---

## Open Questions

Không còn open question — tất cả đã được làm rõ trong buổi brainstorming.

---

*Spec được tạo bởi Antigravity, 2026-06-17*
