"""
AI Context Worker - Background worker cho viec goi LLM API.

Su dung QRunnable + QThreadPool de goi LLM API tren secondary thread,
khong block Main UI thread.

Workflow:
1. Main thread tao AIContextWorker voi prompt data
2. Quang worker vao QThreadPool.globalInstance().start(worker)
3. Worker chay tren background thread, goi LLM API
4. Khi xong, emit signal finished/error ve Main thread
5. Main thread nhan signal va update UI (tick file tree)

Thread Safety: Worker tu khoi tao provider rieng, KHONG chia se state
voi Main thread. Chi giao tiep qua Qt Signals (thread-safe).
"""

import json
import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from core.ai.base_provider import LLMMessage, LLMResponse
from core.ai.openai_provider import OpenAICompatibleProvider
from core.prompting.context_builder_prompts import (
    CONTEXT_SELECTION_SCHEMA,
    build_context_builder_messages,
)

logger = logging.getLogger(__name__)


class AIContextWorkerSignals(QObject):
    """
    Signals de giao tiep giua background worker va Main UI thread.

    Qt Signals tu dong marshal data qua thread boundary,
    dam bao thread-safe ma khong can lock thu cong.
    """

    # Emit khi LLM tra ve thanh cong: (list_paths, reasoning, usage_dict)
    finished = Signal(list, str, dict)
    # Emit khi co loi: (error_message)
    error = Signal(str)
    # Emit de thong bao tien do (optional): (status_text)
    progress = Signal(str)


class AIContextWorker(QRunnable):
    """
    Background worker goi LLM API de lay danh sach file paths.

    Ke thua QRunnable de chay tren QThreadPool.
    Moi worker tu khoi tao OpenAICompatibleProvider rieng,
    khong chia se state voi bất kỳ thread nào khác.

    Attributes:
        signals: AIContextWorkerSignals de emit ket qua
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_id: str,
        file_tree: str,
        user_query: str,
        git_diff: Optional[str] = None,
        chat_history: Optional[List[LLMMessage]] = None,
    ) -> None:
        """
        Khoi tao worker voi du lieu can thiet de goi LLM.

        Args:
            api_key: API key cho LLM provider
            base_url: Base URL cua API endpoint
            model_id: Model ID can su dung
            file_tree: Cay thu muc project (ASCII tree)
            user_query: Mo ta cong viec tu nguoi dung
            git_diff: Optional git diff string
            chat_history: Optional lich su chat truoc do
        """
        super().__init__()
        self.signals = AIContextWorkerSignals()
        self.setAutoDelete(True)

        # Luu tham so de dung trong run()
        self._api_key = api_key
        self._base_url = base_url
        self._model_id = model_id
        self._file_tree = file_tree
        self._user_query = user_query
        self._git_diff = git_diff
        self._chat_history = chat_history

    @Slot()
    def run(self) -> None:
        """
        Chay tren background thread. Goi LLM API va parse ket qua.

        Method nay duoc QThreadPool goi tu mot thread trong pool.
        MOI logic o day deu chay NGOAI Main thread.
        Giao tiep voi Main thread CHI qua self.signals.
        """
        try:
            self.signals.progress.emit("Connecting to LLM...")

            # Khoi tao provider rieng cho worker nay (khong chia se state)
            provider = OpenAICompatibleProvider()
            provider.configure(api_key=self._api_key, base_url=self._base_url)

            # Xay dung messages cho LLM
            messages = build_context_builder_messages(
                file_tree=self._file_tree,
                user_query=self._user_query,
                git_diff=self._git_diff,
                chat_history=self._chat_history,
            )

            self.signals.progress.emit("Waiting for AI response...")

            # Goi LLM voi JSON structured output
            response: LLMResponse = provider.generate_structured(
                messages=messages,
                model_id=self._model_id,
                json_schema=CONTEXT_SELECTION_SCHEMA,
                temperature=0.0,  # Deterministic cho selection task
            )

            self.signals.progress.emit("Parsing response...")

            # Parse JSON response
            selected_paths, reasoning = self._parse_response(response.content)

            # Extract usage info
            usage: Dict[str, Any] = response.usage or {}

            self.signals.finished.emit(selected_paths, reasoning, usage)

        except (ConnectionError, PermissionError) as e:
            logger.warning("AI Context Builder error: %s", e)
            self.signals.error.emit(str(e))
        except Exception as e:
            logger.exception("Unexpected error in AIContextWorker")
            self.signals.error.emit(f"Unexpected error: {e}")

    def _parse_response(self, content: str) -> tuple[List[str], str]:
        """
        Parse JSON response tu LLM thanh danh sach paths va reasoning.

        Args:
            content: JSON string tu LLM response

        Returns:
            Tuple (list_of_paths, reasoning_string)

        Raises:
            ValueError: Khi response khong phai JSON hop le
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM tra ve response khong phai JSON hop le: {e}") from e

        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object, got {type(data).__name__}")

        selected_paths = data.get("selected_paths", [])
        reasoning = data.get("reasoning", "")

        # Validate: phai la list of strings
        if not isinstance(selected_paths, list):
            raise ValueError(
                f"selected_paths phai la array, got {type(selected_paths).__name__}"
            )

        # Loc chi giu cac paths la strings, loai bo gia tri rong
        valid_paths = [
            str(p).strip()
            for p in selected_paths
            if isinstance(p, str) and str(p).strip()
        ]

        return valid_paths, str(reasoning)
