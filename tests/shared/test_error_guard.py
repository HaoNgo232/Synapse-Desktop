# tests/shared/test_error_guard.py
import logging
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
        is_empty = not rec.exc_info or rec.exc_info == (None, None, None)
        assert is_empty
