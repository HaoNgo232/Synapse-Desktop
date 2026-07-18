import json
import pytest
from unittest.mock import MagicMock, patch

from application.services.ai_pick_files_worker import AIPickFilesWorker
from openai_codex import Sandbox


class DummyTurnResult:
    def __init__(self, error=None, final_response="Done") -> None:
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
        # Setup workspace and selection.json mock data
        workspace = tmp_path
        synapse_dir = workspace / ".synapse"
        synapse_dir.mkdir()
        selection_file = synapse_dir / "selection.json"

        expected_paths = ["main.py", "utils/helper.py"]
        selection_data = {
            "version": 2,
            "paths": expected_paths,
            "provenance": {p: "agent" for p in expected_paths},
        }

        # Mock thread behavior: when thread.run is called, simulate selection.json creation
        mock_thread = MagicMock()

        def mock_run(prompt):
            with open(selection_file, "w", encoding="utf-8") as f:
                json.dump(selection_data, f, indent=2)
            return DummyTurnResult()

        mock_thread.run.side_effect = mock_run

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

        # Run worker
        worker.run()

        # Assertions
        assert finished_paths == expected_paths
        mock_codex_instance.thread_start.assert_called_once_with(
            cwd=str(workspace), sandbox=Sandbox.workspace_write
        )
        mock_codex_instance.close.assert_called_once()

        # Check corrected format was written
        with open(selection_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data["version"] == 2
        assert saved_data["paths"] == expected_paths
        assert saved_data["provenance"]["main.py"] == "agent"

    def test_ai_pick_files_worker_agent_error(self, mock_codex, tmp_path):
        workspace = tmp_path

        mock_thread = MagicMock()
        mock_thread.run.return_value = DummyTurnResult(error="LLM Connection Refused")

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
