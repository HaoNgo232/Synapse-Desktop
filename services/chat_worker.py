"""
Chat Worker - Background QRunnable cho LLM streaming.

Tuong tu AIContextWorker nhung ho tro streaming (SSE/chunked) cho chatbot.
Moi worker tu khoi tao provider rieng, KHONG chia se state voi Main thread.
Chi giao tiep qua Qt Signals (thread-safe).

Workflow:
1. Main thread tao ChatWorker voi messages va settings
2. Quang worker vao QThreadPool.globalInstance().start(worker)
3. Worker chay tren background thread, stream LLM response
4. Moi chunk: emit chunk_received signal
5. Khi xong: emit finished signal voi full response
6. Khi co loi: emit error signal
7. Neu phat hien OPX: emit opx_detected signal

Generation counter: Tang counter truoc khi start worker moi,
neu worker nhan counter khong khop khi emit -> boi vi da bi cancel.
"""

import logging
from typing import List

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from core.ai.base_provider import LLMMessage
from core.ai.openai_provider import OpenAICompatibleProvider
from core.chat.response_handler import parse_chat_response

logger = logging.getLogger(__name__)


class ChatWorkerSignals(QObject):
    """
    Signals de giao tiep giua background worker va Main UI thread.

    Qt Signals tu dong marshal data qua thread boundary.
    """

    # Emit moi khi nhan duoc chunk text moi tu LLM
    chunk_received = Signal(str)
    # Emit khi stream hoan tat voi full response
    finished = Signal(str)
    # Emit khi co loi xay ra
    error = Signal(str)
    # Emit khi phat hien OPX blocks trong response (sau khi stream xong)
    opx_detected = Signal(object)  # ParsedResponse


class ChatWorker(QRunnable):
    """
    Background worker stream response tu LLM API.

    Ke thua QRunnable de chay tren QThreadPool.
    Support streaming (SSE) va cancel via generation counter.

    Attributes:
        signals: ChatWorkerSignals de emit ket qua
        _generation: So thu tu cua worker nay (de detect cancel)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_id: str,
        messages: List[LLMMessage],
        generation: int = 0,
        temperature: float = 0.7,
    ) -> None:
        """
        Khoi tao worker voi cau hinh LLM va messages.

        Args:
            api_key: API key cho LLM provider
            base_url: Base URL cua API endpoint
            model_id: Model ID can su dung
            messages: Danh sach messages (system + history + user)
            generation: So thu tu de detect cancel (neu user gui message moi)
            temperature: Do sang tao cua model
        """
        super().__init__()
        self.signals = ChatWorkerSignals()
        self.setAutoDelete(True)
        self._cancelled = False

        self._api_key = api_key
        self._base_url = base_url
        self._model_id = model_id
        self._messages = messages
        self._generation = generation
        self._temperature = temperature

    def cancel(self) -> None:
        """Yeu cau worker dung som."""
        self._cancelled = True

    @Slot()
    def run(self) -> None:
        """
        Chay tren background thread. Stream LLM response va emit chunks.

        Method nay duoc QThreadPool goi tu mot thread trong pool.
        MOI logic o day deu chay NGOAI Main thread.
        Giao tiep voi Main thread CHI qua self.signals.
        """
        try:
            if self._cancelled:
                return

            if not self._model_id:
                raise ValueError(
                    "Invalid AI model configuration. Please check your settings."
                )

            # Khoi tao provider rieng cho worker nay (khong chia se state)
            provider = OpenAICompatibleProvider()
            provider.configure(api_key=self._api_key, base_url=self._base_url)

            # Stream response
            full_content = ""
            stream = provider.generate_stream(
                messages=self._messages,
                model_id=self._model_id,
                temperature=self._temperature,
            )

            for chunk in stream:
                if self._cancelled:
                    return

                if chunk.delta:
                    full_content += chunk.delta
                    self.signals.chunk_received.emit(chunk.delta)

                if chunk.done:
                    break

            if self._cancelled:
                return

            # Emit full response
            self.signals.finished.emit(full_content)

            # Parse response sau khi stream hoan tat
            if full_content:
                parsed = parse_chat_response(full_content)
                if parsed.has_opx or parsed.has_memory:
                    self.signals.opx_detected.emit(parsed)

        except (ConnectionError, PermissionError) as e:
            logger.warning("Chat Worker error: %s", e)
            self.signals.error.emit(str(e))
        except Exception as e:
            logger.exception("Unexpected error in ChatWorker")
            self.signals.error.emit(f"Unexpected error: {e}")
