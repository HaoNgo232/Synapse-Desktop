# tests/presentation/test_qt_utils_observability.py
"""Tests for BackgroundWorker observability improvements."""

import logging
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
            assert not any(
                c is _default_background_error_handler for c in connect_calls
            )
