# Observability & Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Loại bỏ ~62+ chỗ `except Exception: pass` im lặng trong toàn bộ codebase bằng cách thêm logging đầy đủ traceback và toast notification tự động khi background task thất bại.

**Architecture:** Chia làm 2 hướng: (1) Infrastructure safety net — nâng cấp `BackgroundWorker` và `schedule_background` để luôn log + toast khi lỗi; tạo `@guard_errors` decorator mới. (2) Sweep toàn bộ — thay thế có hệ thống mọi `except Exception: pass` theo 3 tier ưu tiên.

**Tech Stack:** Python 3.12, PySide6, logging stdlib, pytest, ruff, pyrefly

## Global Constraints

- Python ≥ 3.12 (dùng `str | None`, `dict[...]`, `set[...]` syntax)
- Tuyệt đối **không commit** — người dùng tự quyết định khi nào commit
- Dùng absolute imports (`from shared.error_guard import guard_errors`)
- Type hints bắt buộc cho tất cả public functions
- `exc_info=True` phải có mặt trên **mọi** `logger.error(...)` cho exception
- `# intentionally silent — <lý do>` phải có trên mọi `except ...: pass` được giữ lại
- Chạy test: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v`
- Chạy lint: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff check --fix .`
- Chạy type check: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pyrefly check`

---

## Task 1: `@guard_errors` decorator + `log_error_ctx()` helper

**Files:**
- Create: `shared/error_guard.py`
- Modify: `shared/logging_config.py` (thêm `log_error_ctx`)
- Create: `tests/shared/test_error_guard.py`

**Interfaces:**
- Produces:
  - `guard_errors(label: str | None = None) -> Callable[[F], F]` — decorator, import từ `shared.error_guard`
  - `log_error_ctx(message: str, exc: Exception | None = None, **context: Any) -> None` — trong `shared.logging_config`

---

- [ ] **Step 1: Tạo test file**

```python
# tests/shared/test_error_guard.py
import logging
import pytest
from shared.error_guard import guard_errors


class TestGuardErrors:
    def test_successful_function_returns_normally(self):
        @guard_errors()
        def fn() -> int:
            return 42

        assert fn() == 42

    def test_exception_is_caught_and_returns_none(self):
        @guard_errors()
        def fn() -> int:
            raise ValueError("boom")

        result = fn()
        assert result is None

    def test_exception_is_logged_with_traceback(self, caplog):
        @guard_errors("my_label")
        def fn() -> None:
            raise RuntimeError("test error")

        with caplog.at_level(logging.ERROR, logger="synapse-desktop"):
            fn()

        assert len(caplog.records) == 1
        assert "my_label" in caplog.records[0].message
        assert caplog.records[0].exc_info is not None

    def test_uses_qualname_when_no_label(self, caplog):
        @guard_errors()
        def my_specific_function() -> None:
            raise ValueError("no label")

        with caplog.at_level(logging.ERROR, logger="synapse-desktop"):
            my_specific_function()

        assert "my_specific_function" in caplog.records[0].message

    def test_label_overrides_qualname(self, caplog):
        @guard_errors("custom_label")
        def fn() -> None:
            raise ValueError("x")

        with caplog.at_level(logging.ERROR, logger="synapse-desktop"):
            fn()

        assert "custom_label" in caplog.records[0].message

    def test_preserves_function_metadata(self):
        @guard_errors()
        def documented_function() -> None:
            """My docstring."""

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "My docstring."

    def test_passes_args_and_kwargs(self):
        @guard_errors()
        def fn(x: int, y: int = 0) -> int:
            return x + y

        assert fn(3, y=4) == 7
```

- [ ] **Step 2: Chạy test — xác nhận FAIL**

```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/shared/test_error_guard.py -v
```

Expected: `ModuleNotFoundError: No module named 'shared.error_guard'`

- [ ] **Step 3: Tạo `shared/error_guard.py`**

```python
"""
Error Guard — Decorator để bắt và log exception âm thầm một cách có kiểm soát.

Thay thế pattern `except Exception: pass` bằng cách log ERROR + full traceback,
đồng thời giữ behavior "không crash caller" cho các hàm callback/timer.

Usage:
    from shared.error_guard import guard_errors

    @guard_errors("MyClass._on_timer")
    def _on_timer(self) -> None:
        ...  # lỗi ở đây sẽ được log thay vì nuốt âm thầm

    @guard_errors()  # dùng qualname tự động
    def my_callback() -> None:
        ...
"""

import functools
import logging
from typing import Any, Callable, TypeVar

_logger = logging.getLogger("synapse-desktop")

F = TypeVar("F", bound=Callable[..., Any])


def guard_errors(label: str | None = None) -> Callable[[F], F]:
    """
    Decorator bảo vệ hàm khỏi nuốt lỗi âm thầm.

    Khi hàm decorated raise exception:
    - Log ERROR với full traceback (exc_info=True) lên logger "synapse-desktop"
    - Trả về None thay vì propagate exception

    Args:
        label: Tên hiển thị trong log message. Nếu None, dùng fn.__qualname__.

    Returns:
        Decorator function.
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

- [ ] **Step 4: Chạy test — xác nhận PASS**

```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/shared/test_error_guard.py -v
```

Expected: 7 tests PASS

- [ ] **Step 5: Thêm `log_error_ctx()` vào cuối `shared/logging_config.py`**

Thêm `Any` vào dòng import đầu file nếu chưa có:
```python
from typing import Any, Optional
```

Thêm hàm mới vào cuối file:
```python
def log_error_ctx(
    message: str,
    exc: Optional[Exception] = None,
    **context: Any,
) -> None:
    """
    Log ERROR với full traceback và key-value context.

    Args:
        message: Mô tả ngắn gọn lỗi xảy ra ở đâu.
        exc: Exception instance. Nếu None, chỉ log message.
        **context: Key-value pairs bổ sung (vd: file=str(path), thread="worker-1").

    Usage:
        log_error_ctx(
            "Token counter crashed",
            exc,
            file=str(path),
            thread=threading.current_thread().name,
        )
    """
    logger = get_logger()
    ctx_str = " | ".join(f"{k}={v}" for k, v in context.items())
    full_msg = f"{message} [{ctx_str}]" if ctx_str else message
    logger.error(full_msg, exc_info=exc is not None)
```

- [ ] **Step 6: Thêm test cho `log_error_ctx` vào `tests/shared/test_error_guard.py`**

```python
from shared.logging_config import log_error_ctx


class TestLogErrorCtx:
    def test_logs_message_without_context(self, caplog):
        with caplog.at_level(logging.ERROR, logger="synapse-desktop"):
            log_error_ctx("Something failed")

        assert len(caplog.records) == 1
        assert "Something failed" in caplog.records[0].message

    def test_logs_message_with_context(self, caplog):
        with caplog.at_level(logging.ERROR, logger="synapse-desktop"):
            log_error_ctx("File read failed", file="/tmp/test.py", thread="bg-1")

        record = caplog.records[0]
        assert "File read failed" in record.message
        assert "file=/tmp/test.py" in record.message
        assert "thread=bg-1" in record.message

    def test_includes_traceback_when_exc_provided(self, caplog):
        exc = ValueError("test exc")
        with caplog.at_level(logging.ERROR, logger="synapse-desktop"):
            log_error_ctx("Crash", exc)

        assert caplog.records[0].exc_info is not None

    def test_no_traceback_when_exc_is_none(self, caplog):
        with caplog.at_level(logging.ERROR, logger="synapse-desktop"):
            log_error_ctx("No exc")

        rec = caplog.records[0]
        is_empty = rec.exc_info is None or rec.exc_info == (None, None, None)
        assert is_empty
```

- [ ] **Step 7: Chạy toàn bộ test + lint + type check**

```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/shared/test_error_guard.py -v
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff check --fix shared/error_guard.py shared/logging_config.py
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pyrefly check
```

Expected: Tất cả PASS, không có lint/type error mới.

---

## Task 2: Nâng cấp `BackgroundWorker` + `schedule_background` default toast

**Files:**
- Modify: `presentation/utils/qt_utils.py`
- Create: `tests/presentation/test_qt_utils_observability.py`

**Interfaces:**
- Produces:
  - `_default_background_error_handler(msg: str) -> None` — module-level function, export cho tests
  - `BackgroundWorker.run()` — log với `exc_info=True` + `fn.__qualname__`
  - `schedule_background(...)` — `on_error` mặc định là `_default_background_error_handler`

---

- [ ] **Step 1: Tạo test file**

```python
# tests/presentation/test_qt_utils_observability.py
"""Tests for BackgroundWorker observability improvements."""
import logging
import pytest
from unittest.mock import MagicMock, patch


class TestBackgroundWorkerLogging:

    def test_worker_logs_error_with_exc_info_on_failure(self, caplog):
        from presentation.utils.qt_utils import BackgroundWorker

        def failing_fn():
            raise ValueError("test crash")

        worker = BackgroundWorker(failing_fn)
        worker.signals = MagicMock()
        worker.signals.result.emit = MagicMock()
        worker.signals.error.emit = MagicMock()
        worker.signals.finished.emit = MagicMock()

        with caplog.at_level(logging.ERROR):
            worker.run()

        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 1
        assert errors[0].exc_info is not None
        assert errors[0].exc_info[1] is not None

    def test_worker_log_includes_function_qualname(self, caplog):
        from presentation.utils.qt_utils import BackgroundWorker

        def my_named_function():
            raise RuntimeError("named crash")

        worker = BackgroundWorker(my_named_function)
        worker.signals = MagicMock()
        worker.signals.result.emit = MagicMock()
        worker.signals.error.emit = MagicMock()
        worker.signals.finished.emit = MagicMock()

        with caplog.at_level(logging.ERROR):
            worker.run()

        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert "my_named_function" in errors[0].message

    def test_worker_still_emits_error_signal_after_logging(self):
        from presentation.utils.qt_utils import BackgroundWorker

        emitted = []

        def failing_fn():
            raise ValueError("signal test")

        worker = BackgroundWorker(failing_fn)
        worker.signals = MagicMock()
        worker.signals.result.emit = MagicMock()
        worker.signals.error.emit = lambda msg: emitted.append(msg)
        worker.signals.finished.emit = MagicMock()

        worker.run()

        assert len(emitted) == 1
        assert "signal test" in emitted[0]


class TestScheduleBackgroundDefaultErrorHandler:

    def test_default_handler_used_when_on_error_not_provided(self):
        from presentation.utils.qt_utils import (
            schedule_background,
            _default_background_error_handler,
        )

        with patch("presentation.utils.qt_utils.BackgroundWorker") as MockWorker:
            mock_instance = MagicMock()
            MockWorker.return_value = mock_instance
            mock_instance.signals.error.connect = MagicMock()
            mock_instance.signals.result.connect = MagicMock()
            mock_instance.signals.finished.connect = MagicMock()

            with patch("presentation.utils.qt_utils.QThreadPool") as MockPool:
                MockPool.globalInstance.return_value = MagicMock()
                schedule_background(lambda: None)

            connect_calls = [
                call.args[0]
                for call in mock_instance.signals.error.connect.call_args_list
            ]
            assert any(c is _default_background_error_handler for c in connect_calls)

    def test_caller_on_error_overrides_default(self):
        from presentation.utils.qt_utils import (
            schedule_background,
            _default_background_error_handler,
        )

        caller_handler = MagicMock()

        with patch("presentation.utils.qt_utils.BackgroundWorker") as MockWorker:
            mock_instance = MagicMock()
            MockWorker.return_value = mock_instance
            mock_instance.signals.error.connect = MagicMock()
            mock_instance.signals.result.connect = MagicMock()
            mock_instance.signals.finished.connect = MagicMock()

            with patch("presentation.utils.qt_utils.QThreadPool") as MockPool:
                MockPool.globalInstance.return_value = MagicMock()
                schedule_background(lambda: None, on_error=caller_handler)

            connect_calls = [
                call.args[0]
                for call in mock_instance.signals.error.connect.call_args_list
            ]
            assert any(c is caller_handler for c in connect_calls)
            assert not any(c is _default_background_error_handler for c in connect_calls)
```

- [ ] **Step 2: Chạy test — xác nhận FAIL**

```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/presentation/test_qt_utils_observability.py -v
```

Expected: `ImportError: cannot import name '_default_background_error_handler'` và logging tests fail.

- [ ] **Step 3a: Thêm `_default_background_error_handler` vào `presentation/utils/qt_utils.py`**

Thêm sau hàm `_cleanup_worker` (khoảng dòng 232):

```python
def _default_background_error_handler(msg: str) -> None:
    """
    Fallback error handler khi schedule_background() không nhận on_error.

    Log ERROR và cố hiển thị toast (best-effort).
    Được gọi trên main thread (Qt signal/slot).
    """
    logger.error(f"Background task failed (no error handler provided): {msg}")
    try:
        from presentation.components.toast.toast_qt import get_toast_manager

        mgr = get_toast_manager()
        if mgr is not None:
            mgr.show_toast(f"Background task failed: {msg}", level="error")
    except Exception:
        pass  # intentionally silent — toast system may not be ready yet
```

- [ ] **Step 3b: Sửa `BackgroundWorker.run()` — thêm `exc_info=True` + `fn.__qualname__`**

Sửa đoạn `except Exception as e:` trong `run()` (khoảng dòng 212–217):

```python
    except Exception as e:
        logger.error(
            f"BackgroundWorker error in '{self.fn.__qualname__}': {e}",
            exc_info=True,
        )
        try:
            self.signals.error.emit(str(e))
        except RuntimeError:
            pass  # intentionally silent — signals deleted during app shutdown
```

- [ ] **Step 3c: Sửa `schedule_background()` — dùng default handler khi `on_error=None`**

Sửa phần connect error signal (khoảng dòng 266–268):

```python
    # Dùng default handler nếu caller không truyền on_error
    effective_error_handler = on_error if on_error is not None else _default_background_error_handler
    worker.signals.error.connect(effective_error_handler)
```

*(Xóa `if on_error: worker.signals.error.connect(on_error)` cũ)*

- [ ] **Step 4: Chạy test — xác nhận PASS**

```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/presentation/test_qt_utils_observability.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Chạy lint + type check**

```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff check --fix presentation/utils/qt_utils.py
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pyrefly check
```

Expected: Không có error mới.

---

## Task 3: Sweep Tier 1 — `infrastructure/adapters/`

**Files (tất cả MODIFY):**
- `infrastructure/adapters/safe_timer.py` (L152, L171)
- `infrastructure/adapters/parallel_counter.py` (L27, L30, L99, L114, L152, L203)
- `infrastructure/adapters/batch_updater.py` (L135, L155, L210)
- `infrastructure/adapters/background_processor.py` (L248)
- `infrastructure/adapters/encoders.py` (L165, L175, L194)
- `infrastructure/adapters/encoder_registry.py` (L78, L103)
- `infrastructure/adapters/async_queue.py` (L126)
- `infrastructure/adapters/cache_registry.py` (L117)
- `infrastructure/adapters/memory_monitor.py` (L120, L149)
- `infrastructure/adapters/security_check.py` (L81, L84, L89, L131, L138, L275, L289)
- `infrastructure/adapters/threading_utils.py` (L149)
- `infrastructure/adapters/tokenization_service.py` (L97)
- `infrastructure/adapters/license_service.py` (L48)
- `infrastructure/adapters/line_count_display.py` (L279, L320)

**Quy tắc áp dụng:**
1. Thêm `import logging` + `logger = logging.getLogger("synapse-desktop")` nếu chưa có
2. Mỗi `except Exception:\n    pass` (không phải shutdown path) → `logger.error("...", exc_info=True)`
3. Giữ `pass` cho shutdown path, thêm comment `# intentionally silent — <lý do>`

---

- [ ] **Step 1: Tạo smoke test**

```python
# tests/infrastructure/test_observability_sweep_tier1.py
import logging
import pytest
from unittest.mock import MagicMock


class TestSafeTimerLogsErrors:
    def test_safe_callback_logs_exception(self, caplog):
        from infrastructure.adapters.safe_timer import SafeTimer

        def bad_callback():
            raise RuntimeError("timer error")

        timer = SafeTimer(0.1, bad_callback)

        with caplog.at_level(logging.ERROR, logger="synapse-desktop"):
            timer._safe_callback()

        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 1
        assert errors[0].exc_info is not None


class TestBatchUpdaterLogsErrors:
    def test_do_update_logs_when_page_update_raises(self, caplog):
        from infrastructure.adapters.batch_updater import BatchUpdater

        bad_page = MagicMock()
        bad_page.update.side_effect = RuntimeError("page closed")
        updater = BatchUpdater(bad_page)

        with caplog.at_level(logging.ERROR, logger="synapse-desktop"):
            updater._do_update()

        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) >= 1
        assert errors[0].exc_info is not None
```

- [ ] **Step 2: Chạy smoke test — xác nhận FAIL**

```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/infrastructure/test_observability_sweep_tier1.py -v
```

Expected: 2 tests FAIL (không có log).

- [ ] **Step 3: Sửa `infrastructure/adapters/safe_timer.py`**

Thêm ở đầu file (sau docstring):
```python
import logging

logger = logging.getLogger("synapse-desktop")
```

Sửa `_safe_callback()` dòng 171–173:
```python
        except Exception:
            logger.error(
                f"SafeTimer callback '{self._callback.__qualname__}' raised",
                exc_info=True,
            )
```

Sửa `_execute()` dòng 152–154:
```python
            except Exception:
                pass  # intentionally silent — Flet page not available or already closed
```

- [ ] **Step 4: Sửa `infrastructure/adapters/batch_updater.py`**

Thêm:
```python
import logging
logger = logging.getLogger("synapse-desktop")
```

Sửa `_do_update()` dòng 135–136:
```python
        except Exception:
            logger.error("BatchUpdater._do_update: page.update() failed", exc_info=True)
```

Sửa `flush()` dòng 155–156:
```python
        except Exception:
            logger.error("BatchUpdater.flush: page.update() failed", exc_info=True)
```

Sửa `ThrottledCallback._execute()` dòng 210–211:
```python
        except Exception:
            logger.error(
                f"ThrottledCallback '{self._callback.__qualname__}' raised",
                exc_info=True,
            )
```

- [ ] **Step 5: Sửa `infrastructure/adapters/encoders.py`**

Thêm:
```python
import logging
logger = logging.getLogger("synapse-desktop")
```

Sửa L165 (rs_bpe o200k_base):
```python
            except Exception:
                logger.error("Encoders: rs-bpe o200k_base() failed, trying cl100k_base", exc_info=True)
```

Sửa L175 (rs_bpe cl100k_base):
```python
            except Exception:
                logger.error("Encoders: rs-bpe cl100k_base() failed, falling back to tiktoken", exc_info=True)
```

Sửa L194 (tiktoken encoding trong for loop):
```python
            except Exception:
                logger.error(f"Encoders: tiktoken '{encoding_name}' failed", exc_info=True)
                continue
```

- [ ] **Step 6: Sửa `infrastructure/adapters/parallel_counter.py`**

Thêm:
```python
import logging
logger = logging.getLogger("synapse-desktop")
```

Sửa L27–30 (read_file_mmap fallback — đây là intentional fallback, không cần log):
```python
    except Exception:
        try:
            return file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None
```
*(Giữ nguyên — đây là expected 2-level fallback, không phải lỗi)*

Sửa L99 (count_single_file trong ThreadPoolExecutor):
```python
        except Exception:
            logger.error(f"parallel_counter: count_single_file failed for '{path}'", exc_info=True)
            return (str(path), 0, 0)
```

Sửa L114 (future.result() trong as_completed):
```python
                except Exception:
                    path = futures[future]
                    logger.error(f"parallel_counter: future failed for '{path}'", exc_info=True)
                    results[str(path)] = 0
```

Sửa L152 (count_tokens_batch_sequential per-file):
```python
        except Exception:
            logger.error(f"parallel_counter: sequential count failed for '{path}'", exc_info=True)
            results[str(path)] = 0
```

Sửa L203 (count_tokens_batch_hf per-file read):
```python
        except Exception:
            logger.error(f"parallel_counter: HF batch failed reading '{path}'", exc_info=True)
            results[str(path)] = 0
```

- [ ] **Step 7: Sửa các adapter còn lại trong Tier 1**

Áp dụng pattern `logger.error("...", exc_info=True)` cho:

```python
# encoder_registry.py L78:
except Exception:
    logger.error("encoder_registry: failed to initialize encoder", exc_info=True)

# encoder_registry.py L103:
except Exception:
    logger.error("encoder_registry: count_tokens failed", exc_info=True)

# async_queue.py L126:
except Exception:
    self._pending = max(0, self._pending - 1)
    logger.error("AsyncTaskQueue.add: semaphore management failed", exc_info=True)
    raise

# cache_registry.py L117:
except Exception:
    logger.error("CacheRegistry: eviction/cleanup failed", exc_info=True)

# memory_monitor.py L120:
except Exception:
    logger.error("MemoryMonitor: failed to collect stats", exc_info=True)

# memory_monitor.py L149:
except Exception:
    logger.error("MemoryMonitor: on_update callback raised", exc_info=True)

# security_check.py L81, L84, L89:
except Exception:
    logger.error("SecurityCheck: pattern matching failed", exc_info=True)

# security_check.py L131, L138:
except Exception:
    logger.error("SecurityCheck: file scan failed", exc_info=True)

# security_check.py L275, L289:
except Exception:
    logger.error(f"SecurityCheck: failed scanning file", exc_info=True)

# threading_utils.py L149:
except Exception:
    logger.error("threading_utils: callback raised", exc_info=True)

# tokenization_service.py L97:
except Exception:
    logger.error("TokenizationService: background count failed", exc_info=True)

# license_service.py L48:
except Exception:
    logger.error("LicenseService: validation request failed", exc_info=True)

# line_count_display.py L279:
except Exception:
    logger.error("LineCountDisplay: update failed", exc_info=True)

# line_count_display.py L320:
except Exception:
    logger.error("LineCountDisplay: display refresh failed", exc_info=True)

# background_processor.py L248 (_invoke_callback via page):
except Exception:
    logger.error("BackgroundProcessor._invoke_callback: page.run_task failed, falling back to direct call", exc_info=True)
    callback(arg)  # giữ fallback behavior
```

- [ ] **Step 8: Chạy smoke tests + toàn bộ test suite**

```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/infrastructure/test_observability_sweep_tier1.py -v
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff check --fix infrastructure/adapters/
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pyrefly check
```

Expected: Smoke tests PASS, không có regression.

---

## Task 4: Sweep Tier 2 + 3 — git, filesystem, application, presentation

**Files (MODIFY):**

*Tier 2 — infrastructure:*
- `infrastructure/git/git_utils.py` (L192, L592, L859, L901, L904, L953, L1011, L1072)
- `infrastructure/git/repo_manager.py` (L434)
- `infrastructure/filesystem/file_scanner.py` (L597)
- `infrastructure/filesystem/file_actions.py` (L316, L324)
- `infrastructure/persistence/history_service.py` (L94)
- `infrastructure/persistence/settings_manager.py` (L98, L261)

*Tier 2 — application:*
- `application/use_cases/workflow_engine.py` (L131)
- `application/services/apply_service.py` (L154)
- `application/services/preview_analyzer.py` (L171, L206, L303)
- `application/services/workspace_config.py` (L84, L118, L145)
- `application/services/workspace_index.py` (L300)
- `application/plugins/registry.py` (L62)

*Tier 3 — presentation:*
- `presentation/main_window.py` (L488, L538, L836)
- `presentation/views/context/context_view_qt.py` (L707, L732, L1285)
- `presentation/views/context/copy_action_controller.py` (L468, L964, L1394)
- `presentation/views/context/ui_builder.py` (L521)
- `presentation/views/settings/settings_view_qt.py` (L97, L106, L1457)
- `presentation/components/qt_utils.py` (L42)
- `presentation/components/dialogs/dialogs_qt.py` (L579, L581, L1323, L1403, L1489)
- `presentation/service_container.py` (L208)
- `presentation/components/file_tree/file_tree_widget.py` (L940)

---

- [ ] **Step 1: Sửa `infrastructure/git/git_utils.py`**

Thêm logger nếu chưa có. Với các `except Exception: pass` trong git operations:

```python
# L192 (git command failed, non-critical):
except Exception:
    logger.error("git_utils: git operation failed", exc_info=True)

# L592:
except Exception:
    logger.error("git_utils: diff parsing failed", exc_info=True)

# L859, L901, L904, L953, L1011, L1072 — trong vòng lặp xử lý files:
except Exception:
    logger.error(f"git_utils: failed processing git entry", exc_info=True)
```

- [ ] **Step 2: Sửa `infrastructure/git/repo_manager.py` + filesystem**

```python
# repo_manager.py L434:
except Exception:
    logger.error("repo_manager: git operation failed", exc_info=True)

# file_scanner.py L597:
except Exception:
    logger.error(f"file_scanner: failed scanning directory entry", exc_info=True)

# file_actions.py L316:
except Exception:
    logger.error("file_actions: failed writing file", exc_info=True)

# file_actions.py L324:
except Exception:
    logger.error("file_actions: failed in file iteration", exc_info=True)
```

- [ ] **Step 3: Sửa `infrastructure/persistence/`**

```python
# history_service.py L94:
except Exception:
    logger.error("history_service: failed to persist history entry", exc_info=True)

# settings_manager.py L98:
except Exception:
    logger.error("settings_manager: failed to load settings from disk", exc_info=True)

# settings_manager.py L261:
except Exception:
    logger.error("settings_manager: failed to save settings to disk", exc_info=True)
```

- [ ] **Step 4: Sửa `application/` files**

```python
# workflow_engine.py L131 — observer errors không được fail workflow:
except Exception:
    logger.error(
        f"WorkflowEngine._emit: observer '{observer.__class__.__name__}' raised",
        exc_info=True,
    )
    continue  # giữ behavior

# apply_service.py L154:
except Exception:
    logger.error("apply_service: apply step failed", exc_info=True)

# preview_analyzer.py L171:
except Exception:
    logger.error("preview_analyzer: analysis failed", exc_info=True)

# preview_analyzer.py L206:
except Exception:
    logger.error("preview_analyzer: diff computation failed", exc_info=True)

# preview_analyzer.py L303:
except Exception:
    logger.error("preview_analyzer: post-processing failed", exc_info=True)

# workspace_config.py L84, L118, L145:
except Exception:
    logger.error("workspace_config: config operation failed", exc_info=True)

# workspace_index.py L300:
except Exception:
    logger.error("workspace_index: indexing step failed", exc_info=True)

# plugins/registry.py L62:
except Exception:
    logger.error("plugin_registry: failed to load plugin", exc_info=True)
```

- [ ] **Step 5: Sửa `presentation/` files — phân loại cẩn thận**

**`presentation/main_window.py`:**
```python
# L488 — _build_token_status_text (UI display, dùng warning):
except Exception:
    logger.warning("main_window: _build_token_status_text failed", exc_info=True)
    return "0 files | 0 tokens"

# L538 — git không available trong workspace (expected):
except Exception:
    pass  # intentionally silent — git not available in this workspace

# L836 — closeEvent flush_logs (logging system itself failed):
except Exception:
    pass  # intentionally silent — shutdown path, nothing we can do if logging fails
```

**`presentation/views/context/copy_action_controller.py`:**
```python
# L468 — dismiss_all toast trước copy (UI cleanup):
except Exception:
    logger.warning("copy_action_controller: dismiss_all toast failed", exc_info=True)

# L964 — deleteLater trên stale worker (expected race condition):
except RuntimeError:
    pass  # intentionally silent — object already deleted by Qt

# L1394 — post-worker cleanup:
except Exception:
    logger.warning("copy_action_controller: post-worker cleanup failed", exc_info=True)
```

**`presentation/components/qt_utils.py` L42 (SVG icon fallback):**
```python
    except Exception:
        pass  # intentionally silent — non-critical UI, fallback to original icon
```

**`presentation/service_container.py` L208:**
```python
    except Exception:
        logger.error("service_container: service initialization failed", exc_info=True)
```

**`presentation/components/dialogs/dialogs_qt.py`:**
```python
# L579, L581 — signal/slot cleanup (shutdown path):
except Exception:
    pass  # intentionally silent — Qt object cleanup during shutdown

# L1323, L1403, L1489 — dialog operations:
except Exception:
    logger.error("dialogs_qt: dialog operation failed", exc_info=True)
```

**`presentation/views/settings/settings_view_qt.py`:**
```python
# L97, L106 — settings load:
except Exception:
    logger.error("settings_view: failed to load setting value", exc_info=True)

# L1457 — worker cleanup:
except Exception:
    logger.warning("settings_view: worker cleanup failed", exc_info=True)
```

**`presentation/views/context/context_view_qt.py` L707, L732, L1285:**
```python
except Exception:
    logger.error("context_view: operation failed", exc_info=True)
```

**`presentation/views/context/ui_builder.py` L521:**
```python
except Exception:
    logger.error("ui_builder: UI construction failed", exc_info=True)
```

**`presentation/components/file_tree/file_tree_widget.py` L940:**
```python
except Exception:
    logger.error("file_tree_widget: token update failed", exc_info=True)
```

- [ ] **Step 6: Chạy verification script**

```bash
grep -rn "except Exception:$" \
  --include="*.py" \
  infrastructure/ application/ presentation/ \
  | grep -v "intentionally"
```

Expected: **zero output** (không còn bare `except Exception:` không có comment).

- [ ] **Step 7: Chạy toàn bộ test suite + lint + type check**

```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff check --fix .
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pyrefly check
```

Expected: Tất cả existing tests PASS, không có lỗi lint/type mới.

- [ ] **Step 8: Manual smoke test**

1. Chạy app: `.\start.bat --no-license`
2. Nhập API key sai → nhấn "Fetch Models"
3. **Xác nhận:** Toast "Background task failed: ..." hiển thị trên UI
4. **Xác nhận:** Console có `[ERROR]` với full traceback (không chỉ message)
5. Đóng app bình thường → confirm không có exception mới từ shutdown path
