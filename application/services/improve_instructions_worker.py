"""
Improve Instructions Worker - Background worker cho viec goi LLM API de cai thien instructions.

Su dung QRunnable + QThreadPool de goi LLM API tren secondary thread.
"""

import json
import logging
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from domain.ports.ai_port import LLMResponse
from domain.prompt.improve_instructions_prompts import (
    IMPROVE_INSTRUCTIONS_SCHEMA,
    build_improve_instructions_messages,
)

logger = logging.getLogger(__name__)


class ImproveInstructionsWorkerSignals(QObject):
    """
    Signals de giao tiep giua background worker va Main UI thread.
    """

    # Emit khi LLM tra ve thanh cong: (improved_instructions, explanation, usage_dict)
    finished = Signal(str, str, dict)
    # Emit khi co loi: (error_message)
    error = Signal(str)
    # Emit de thong bao tien do: (status_text)
    progress = Signal(str)


class ImproveInstructionsWorker(QRunnable):
    """
    Background worker goi LLM API de cai thien instructions cua nguoi dung.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_id: str,
        user_query: str,
        file_tree: Optional[str] = None,
        git_diff: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.signals = ImproveInstructionsWorkerSignals()
        self.setAutoDelete(True)
        self._cancelled = False

        self._api_key = api_key
        self._base_url = base_url
        self._model_id = model_id
        self._user_query = user_query
        self._file_tree = file_tree
        self._git_diff = git_diff

    def cancel(self) -> None:
        """Yeu cau worker dung som."""
        self._cancelled = True

    @Slot()
    def run(self) -> None:
        try:
            if self._cancelled:
                return

            self.signals.progress.emit("Connecting to LLM...")

            from domain.ports.registry import DomainRegistry

            # Khoi tao provider rieng cho worker nay (khong chia se state)
            provider_factory = DomainRegistry.ai_provider_factory()
            provider = provider_factory()
            provider.configure(api_key=self._api_key, base_url=self._base_url)

            # Xay dung messages cho LLM
            messages = build_improve_instructions_messages(
                user_query=self._user_query,
                file_tree=self._file_tree,
                git_diff=self._git_diff,
            )

            if not self._model_id:
                raise ValueError(
                    "Invalid AI model configuration. Please check your settings."
                )

            if self._cancelled:
                return

            self.signals.progress.emit("Waiting for AI response...")

            # Goi LLM voi JSON structured output
            response: LLMResponse = provider.generate_structured(
                messages=messages,
                model_id=self._model_id,
                json_schema=IMPROVE_INSTRUCTIONS_SCHEMA,
                temperature=0.3,  # Hoi creative ti de improve instruction
            )

            if self._cancelled:
                return

            self.signals.progress.emit("Parsing response...")

            # Parse JSON response
            improved_instructions, explanation = self._parse_response(response.content)

            usage: Dict[str, Any] = response.usage or {}

            if self._cancelled:
                return

            self.signals.finished.emit(improved_instructions, explanation, usage)

        except (ConnectionError, PermissionError) as e:
            logger.warning("Improve Instructions Worker error: %s", e)
            self.signals.error.emit(str(e))
        except Exception as e:
            logger.exception("Unexpected error in ImproveInstructionsWorker")
            self.signals.error.emit(f"Unexpected error: {e}")

    def _parse_response(self, content: str) -> tuple[str, str]:
        import re

        cleaned = content.strip()
        md_match = re.match(r"^```(?:json)?\s*\n?(.*?)\n?\s*```$", cleaned, re.DOTALL)
        if md_match:
            cleaned = md_match.group(1).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"LLM tra ve response khong phai JSON hop le: {e}\n"
                f"Raw content (first 300 chars): {content[:300]}"
            ) from e

        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object, got {type(data).__name__}")

        improved_instructions = data.get("improved_instructions")
        explanation = data.get("explanation", "")

        if not isinstance(improved_instructions, str):
            raise ValueError("improved_instructions phai la string trong JSON response")

        return improved_instructions, explanation
