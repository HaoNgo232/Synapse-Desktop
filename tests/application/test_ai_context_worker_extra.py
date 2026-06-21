import pytest
import json
from unittest.mock import MagicMock, patch
from domain.ports.ai_port import LLMResponse
from domain.ports.registry import DomainRegistry
from application.services.ai_context_worker import AIContextWorker


class DummyAIProvider:
    def __init__(self, content: str = "{}", usage: dict = None) -> None:
        self.structured_response = LLMResponse(content=content, usage=usage)
        self.api_key = ""
        self.base_url = ""

    def configure(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url

    def generate_structured(
        self, messages, model_id, json_schema, temperature=0.0
    ) -> LLMResponse:
        return self.structured_response


class TestAIContextWorkerExtra:
    @pytest.fixture(autouse=True)
    def setup_registry(self):
        self.old_factory = None
        self.old_ci = None
        try:
            self.old_factory = DomainRegistry.ai_provider_factory()
        except RuntimeError:
            pass
        try:
            self.old_ci = DomainRegistry.code_intelligence()
        except RuntimeError:
            pass
        yield
        if self.old_factory is not None:
            DomainRegistry.register_ai_provider_factory(self.old_factory)
        if self.old_ci is not None:
            DomainRegistry.register_code_intelligence(self.old_ci)

    def test_repo_map_generation_exception_and_empty(self, tmp_path):
        # 1. Exception during repo map generation (lines 139-140)
        mock_ast = MagicMock()
        mock_ast.generate_repo_map.side_effect = Exception("Parsing crash")
        DomainRegistry.register_code_intelligence(mock_ast)

        provider = DummyAIProvider(
            content=json.dumps({"selected_paths": ["main.py"], "reasoning": "ok"})
        )
        DomainRegistry.register_ai_provider_factory(lambda: provider)

        worker = AIContextWorker(
            api_key="key",
            base_url="url",
            model_id="model",
            file_tree="root",
            user_query="query",
            all_file_paths=["main.py"],
            workspace_root=tmp_path,
        )
        worker.run()
        # Verify it still succeeded and finished because repo map exception is caught
        assert worker._cancelled is False

        # 2. Empty repo_map_str sets it to None (lines 137-138)
        mock_ast.generate_repo_map.side_effect = None
        mock_ast.generate_repo_map.return_value = "   "
        worker2 = AIContextWorker(
            api_key="key",
            base_url="url",
            model_id="model",
            file_tree="root",
            user_query="query",
            all_file_paths=["main.py"],
            workspace_root=tmp_path,
        )
        worker2.run()
        assert worker2._cancelled is False

    def test_cancellation_checkpoints(self, tmp_path):
        # Setup provider
        provider = DummyAIProvider(
            content=json.dumps({"selected_paths": ["main.py"], "reasoning": "ok"})
        )
        DomainRegistry.register_ai_provider_factory(lambda: provider)

        # 1. Cancel after repo map (line 143)
        mock_ast = MagicMock()
        mock_ast.generate_repo_map.return_value = "repo map content"
        DomainRegistry.register_code_intelligence(mock_ast)

        worker = AIContextWorker(
            api_key="key",
            base_url="url",
            model_id="model",
            file_tree="root",
            user_query="query",
            all_file_paths=["main.py"],
            workspace_root=tmp_path,
        )

        # Intercept signals.progress to trigger cancel midway
        def on_progress_cancel(status):
            if status == "Generating Repo Map...":
                worker.cancel()

        worker.signals.progress.connect(on_progress_cancel)

        finished_called = False
        worker.signals.finished.connect(
            lambda p, r, u: setattr(finished_called, "val", True)
        )
        worker.run()
        assert worker._cancelled is True
        assert finished_called is False

        # 2. Cancel after configuring provider / before calling generate_structured (line 169)
        worker2 = AIContextWorker(
            api_key="key",
            base_url="url",
            model_id="model",
            file_tree="root",
            user_query="query",
            workspace_root=tmp_path,
        )

        def on_progress_cancel2(status):
            if status == "Connecting to LLM...":
                worker2.cancel()

        worker2.signals.progress.connect(on_progress_cancel2)
        worker2.run()
        assert worker2._cancelled is True

        # 3. Cancel after generate_structured (line 183)
        worker3 = AIContextWorker(
            api_key="key",
            base_url="url",
            model_id="model",
            file_tree="root",
            user_query="query",
            workspace_root=tmp_path,
        )

        def on_progress_cancel3(status):
            if status == "Waiting for AI response...":
                worker3.cancel()

        worker3.signals.progress.connect(on_progress_cancel3)
        worker3.run()
        assert worker3._cancelled is True

        # 4. Cancel after parsing response (line 208)
        worker4 = AIContextWorker(
            api_key="key",
            base_url="url",
            model_id="model",
            file_tree="root",
            user_query="query",
            workspace_root=tmp_path,
        )

        def on_progress_cancel4(status):
            if status == "Parsing response...":
                worker4.cancel()

        worker4.signals.progress.connect(on_progress_cancel4)
        worker4.run()
        assert worker4._cancelled is True

    def test_empty_model_id_error(self, tmp_path):
        # Empty model ID raises ValueError caught in run() (line 164)
        worker = AIContextWorker(
            api_key="key",
            base_url="url",
            model_id="",  # Empty
            file_tree="root",
            user_query="query",
            workspace_root=tmp_path,
        )

        error_msg = ""

        def on_error(msg):
            nonlocal error_msg
            error_msg = msg

        worker.signals.error.connect(on_error)
        worker.run()
        assert "Invalid AI model configuration" in error_msg

    def test_hallucination_path_filter(self, tmp_path):
        # LLM returns path "ghost.py" which isn't in all_file_paths (line 196)
        provider = DummyAIProvider(
            content=json.dumps(
                {"selected_paths": ["main.py", "ghost.py"], "reasoning": "ok"}
            )
        )
        DomainRegistry.register_ai_provider_factory(lambda: provider)

        worker = AIContextWorker(
            api_key="key",
            base_url="url",
            model_id="model",
            file_tree="root",
            user_query="query",
            all_file_paths=["main.py"],
            workspace_root=tmp_path,
        )

        valid_paths = []
        worker.signals.finished.connect(lambda paths, r, u: valid_paths.extend(paths))
        worker.run()
        assert "main.py" in valid_paths
        assert "ghost.py" not in valid_paths  # Hallucinated path filtered out

    def test_run_exceptions_handling(self, tmp_path):
        # 1. ConnectionError / PermissionError (line 212-214)
        with patch.object(
            DummyAIProvider,
            "generate_structured",
            side_effect=ConnectionError("Host unreachable"),
        ):
            provider = DummyAIProvider()
            DomainRegistry.register_ai_provider_factory(lambda: provider)

            worker = AIContextWorker(
                "key", "url", "model", "root", "query", workspace_root=tmp_path
            )
            error_msg = ""
            worker.signals.error.connect(lambda msg: setattr(worker, "err_msg", msg))
            worker.run()
            assert "Host unreachable" in getattr(worker, "err_msg", "")

        # 2. Unexpected Exception (line 215-217)
        with patch.object(
            DummyAIProvider,
            "generate_structured",
            side_effect=RuntimeError("Unexpected crash"),
        ):
            provider = DummyAIProvider()
            DomainRegistry.register_ai_provider_factory(lambda: provider)

            worker2 = AIContextWorker(
                "key", "url", "model", "root", "query", workspace_root=tmp_path
            )
            worker2.signals.error.connect(lambda msg: setattr(worker2, "err_msg", msg))
            worker2.run()
            assert "Unexpected error: Unexpected crash" in getattr(
                worker2, "err_msg", ""
            )

    def test_parse_response_markdown_and_errors(self, tmp_path):
        worker = AIContextWorker(
            "key", "url", "model", "root", "query", workspace_root=tmp_path
        )

        # 1. Markdown code fences with/without json (lines 235-237)
        c1 = '```json\n{\n  "selected_paths": ["main.py"],\n  "reasoning": "md json"\n}\n```'
        paths1, reasoning1 = worker._parse_response(c1)
        assert paths1 == ["main.py"]
        assert reasoning1 == "md json"

        c2 = '```\n{\n  "selected_paths": ["main.py"],\n  "reasoning": "md raw"\n}\n```'
        paths2, reasoning2 = worker._parse_response(c2)
        assert paths2 == ["main.py"]
        assert reasoning2 == "md raw"

        # 2. Invalid JSON (lines 241-245)
        with pytest.raises(ValueError, match="LLM tra ve response khong phai JSON"):
            worker._parse_response("not-json")

        # 3. JSON is not a dict (lines 247-248)
        with pytest.raises(ValueError, match="Expected JSON object"):
            worker._parse_response('["main.py"]')

        # 4. selected_paths is not a list (lines 254-257)
        with pytest.raises(ValueError, match="selected_paths phai la array"):
            worker._parse_response(
                json.dumps({"selected_paths": "main.py", "reasoning": ""})
            )

    def test_immediate_cancellation(self, tmp_path):
        worker = AIContextWorker(
            "key", "url", "model", "root", "query", workspace_root=tmp_path
        )
        worker.cancel()
        worker.run()
        # Should return immediately and not call LLM or do anything
        assert worker._cancelled is True
