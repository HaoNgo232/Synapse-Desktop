import pytest
from unittest.mock import MagicMock, patch

from application.services.ai_pick_files_worker import AIPickFilesWorker
from openai_codex import Sandbox


class DummyTurnResult:
    def __init__(
        self, error=None, final_response='{"paths": ["main.py", "utils/helper.py"]}'
    ) -> None:
        self.id = "turn-123"
        self.status = "completed"
        self.error = error
        self.started_at = 123
        self.completed_at = 456
        self.duration_ms = 100
        self.final_response = final_response
        self.items = []
        self.usage = None


class TestAIPickFilesWorker:
    @pytest.fixture
    def mock_codex(self):
        with patch("application.services.ai_pick_files_worker.Codex") as mock:
            yield mock

    def test_ai_pick_files_worker_success(self, mock_codex, tmp_path):
        # Setup workspace and mock files to pass validation
        workspace = tmp_path
        (workspace / "main.py").write_text("print('hello')", encoding="utf-8")
        (workspace / "utils").mkdir()
        (workspace / "utils" / "helper.py").write_text(
            "def helper(): pass", encoding="utf-8"
        )

        expected_paths = ["main.py", "utils/helper.py"]

        # Mock thread behavior: when _collect_stream_with_progress is called, return DummyTurnResult
        mock_thread = MagicMock()
        mock_turn = MagicMock()
        mock_turn.id = "turn-123"
        mock_thread.turn.return_value = mock_turn

        mock_codex_instance = MagicMock()
        mock_codex_instance.thread_start.return_value = mock_thread
        mock_codex.return_value = mock_codex_instance

        # Create worker
        worker = AIPickFilesWorker(
            api_key="mock-api-key",
            base_url="https://api.mock.ai/v1",
            model_id="mock-model",
            workspace=str(workspace),
            user_instruction="find helper files",
        )

        finished_paths = None

        def on_finished(paths):
            nonlocal finished_paths
            finished_paths = paths

        worker.signals.finished.connect(on_finished)

        # Patch _collect_stream_with_progress
        with patch.object(
            AIPickFilesWorker, "_collect_stream_with_progress"
        ) as mock_collect:
            mock_collect.return_value = DummyTurnResult()

            # Run worker
            worker.run()

        # Assertions
        assert finished_paths == expected_paths
        mock_codex_instance.thread_start.assert_called_once_with(
            cwd=str(workspace), sandbox=Sandbox.read_only
        )
        mock_codex_instance.close.assert_called_once()

    def test_ai_pick_files_worker_agent_error(self, mock_codex, tmp_path):
        workspace = tmp_path

        mock_thread = MagicMock()
        mock_turn = MagicMock()
        mock_turn.id = "turn-123"
        mock_thread.turn.return_value = mock_turn

        mock_codex_instance = MagicMock()
        mock_codex_instance.thread_start.return_value = mock_thread
        mock_codex.return_value = mock_codex_instance

        worker = AIPickFilesWorker(
            api_key="mock-api-key",
            base_url="https://api.mock.ai/v1",
            model_id="mock-model",
            workspace=str(workspace),
            user_instruction="find helper files",
        )

        error_message = None

        def on_error(msg):
            nonlocal error_message
            error_message = msg

        worker.signals.error.connect(on_error)

        with patch.object(
            AIPickFilesWorker, "_collect_stream_with_progress"
        ) as mock_collect:
            mock_collect.return_value = DummyTurnResult(error="LLM Connection Refused")
            worker.run()

        assert error_message is not None
        assert "Codex Agent error: LLM Connection Refused" in error_message
        mock_codex_instance.close.assert_called_once()

    def test_ai_pick_files_worker_cancelled(self, mock_codex, tmp_path):
        workspace = tmp_path

        mock_codex_instance = MagicMock()
        mock_codex.return_value = mock_codex_instance

        worker = AIPickFilesWorker(
            api_key="mock-api-key",
            base_url="https://api.mock.ai/v1",
            model_id="mock-model",
            workspace=str(workspace),
            user_instruction="find helper files",
        )

        worker.cancel()
        worker.run()

        # Since it was cancelled, Codex should not be initialized
        mock_codex.assert_not_called()

    def test_ai_pick_files_worker_exception(self, mock_codex, tmp_path):
        workspace = tmp_path

        # Simulate exception during initialization or execution
        mock_codex.side_effect = RuntimeError("Failed to start Codex daemon")

        worker = AIPickFilesWorker(
            api_key="mock-api-key",
            base_url="https://api.mock.ai/v1",
            model_id="mock-model",
            workspace=str(workspace),
            user_instruction="find helper files",
        )

        error_message = None

        def on_error(msg):
            nonlocal error_message
            error_message = msg

        worker.signals.error.connect(on_error)
        worker.run()

        assert error_message == "Failed to start Codex daemon"
