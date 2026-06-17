# tests/infrastructure/test_observability_sweep_tier1.py
import logging
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
