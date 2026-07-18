import pytest
import json
from unittest.mock import patch
from domain.ports.ai_port import LLMResponse
from domain.ports.registry import DomainRegistry
from application.services.improve_instructions_worker import ImproveInstructionsWorker


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


class TestImproveInstructionsWorkerExtra:
    @pytest.fixture(autouse=True)
    def setup_registry(self):
        self.old_factory = None
        try:
            self.old_factory = DomainRegistry.ai_provider_factory()
        except RuntimeError:
            pass
        yield
        if self.old_factory is not None:
            DomainRegistry.register_ai_provider_factory(self.old_factory)

    def test_cancellation_checkpoints(self):
        # Setup provider
        provider = DummyAIProvider(
            content=json.dumps(
                {
                    "improved_instructions": "improved instructions",
                    "explanation": "ok",
                }
            )
        )
        DomainRegistry.register_ai_provider_factory(lambda: provider)

        # 1. Cancel before calling generate_structured (line after connecting to LLM)
        worker = ImproveInstructionsWorker(
            api_key="key",
            base_url="url",
            model_id="model",
            user_query="query",
        )

        def on_progress_cancel(status):
            if status == "Connecting to LLM...":
                worker.cancel()

        worker.signals.progress.connect(on_progress_cancel)

        finished_called = False
        worker.signals.finished.connect(
            lambda imp, exp, u: setattr(finished_called, "val", True)
        )
        worker.run()
        assert worker._cancelled is True
        assert finished_called is False

        # 2. Cancel after configuring provider / before calling generate_structured
        worker2 = ImproveInstructionsWorker(
            api_key="key",
            base_url="url",
            model_id="model",
            user_query="query",
        )

        def on_progress_cancel2(status):
            if status == "Connecting to LLM...":
                # Cancel immediately
                worker2.cancel()

        worker2.signals.progress.connect(on_progress_cancel2)
        worker2.run()
        assert worker2._cancelled is True

        # 3. Cancel after generate_structured
        worker3 = ImproveInstructionsWorker(
            api_key="key",
            base_url="url",
            model_id="model",
            user_query="query",
        )

        def on_progress_cancel3(status):
            if status == "Waiting for AI response...":
                worker3.cancel()

        worker3.signals.progress.connect(on_progress_cancel3)
        worker3.run()
        assert worker3._cancelled is True

        # 4. Cancel after parsing response
        worker4 = ImproveInstructionsWorker(
            api_key="key",
            base_url="url",
            model_id="model",
            user_query="query",
        )

        def on_progress_cancel4(status):
            if status == "Parsing response...":
                worker4.cancel()

        worker4.signals.progress.connect(on_progress_cancel4)
        worker4.run()
        assert worker4._cancelled is True

    def test_empty_model_id_error(self):
        worker = ImproveInstructionsWorker(
            api_key="key",
            base_url="url",
            model_id="",  # Empty
            user_query="query",
        )

        error_msg = ""

        def on_error(msg):
            nonlocal error_msg
            error_msg = msg

        worker.signals.error.connect(on_error)
        worker.run()
        assert "Invalid AI model configuration" in error_msg

    def test_run_exceptions_handling(self):
        # 1. ConnectionError / PermissionError
        with patch.object(
            DummyAIProvider,
            "generate_structured",
            side_effect=ConnectionError("Host unreachable"),
        ):
            provider = DummyAIProvider()
            DomainRegistry.register_ai_provider_factory(lambda: provider)

            worker = ImproveInstructionsWorker("key", "url", "model", "query")
            worker.signals.error.connect(lambda msg: setattr(worker, "err_msg", msg))
            worker.run()
            assert "Host unreachable" in getattr(worker, "err_msg", "")

        # 2. Unexpected Exception
        with patch.object(
            DummyAIProvider,
            "generate_structured",
            side_effect=RuntimeError("Unexpected crash"),
        ):
            provider = DummyAIProvider()
            DomainRegistry.register_ai_provider_factory(lambda: provider)

            worker2 = ImproveInstructionsWorker("key", "url", "model", "query")
            worker2.signals.error.connect(lambda msg: setattr(worker2, "err_msg", msg))
            worker2.run()
            assert "Unexpected error: Unexpected crash" in getattr(
                worker2, "err_msg", ""
            )

    def test_parse_response_markdown_and_errors(self):
        worker = ImproveInstructionsWorker("key", "url", "model", "query")

        # 1. Markdown code fences with/without json
        c1 = '```json\n{\n  "improved_instructions": "imp instructions",\n  "explanation": "md json"\n}\n```'
        imp1, exp1 = worker._parse_response(c1)
        assert imp1 == "imp instructions"
        assert exp1 == "md json"

        c2 = '```\n{\n  "improved_instructions": "imp instructions",\n  "explanation": "md raw"\n}\n```'
        imp2, exp2 = worker._parse_response(c2)
        assert imp2 == "imp instructions"
        assert exp2 == "md raw"

        # 2. Invalid JSON
        with pytest.raises(ValueError, match="LLM tra ve response khong phai JSON"):
            worker._parse_response("not-json")

        # 3. JSON is not a dict
        with pytest.raises(ValueError, match="Expected JSON object"):
            worker._parse_response('["main.py"]')

        # 4. improved_instructions is not a string
        with pytest.raises(ValueError, match="improved_instructions phai la string"):
            worker._parse_response(
                json.dumps({"improved_instructions": 123, "explanation": ""})
            )

    def test_immediate_cancellation(self):
        worker = ImproveInstructionsWorker("key", "url", "model", "query")
        worker.cancel()
        worker.run()
        # Should return immediately
