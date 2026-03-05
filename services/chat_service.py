"""
Chat Service - Orchestrator cho chatbot feature.

Quan ly conversation history, context injection, va worker lifecycle.
Provides API don gian de send messages va nhan streaming response.

Luong hoat dong:
1. User goi send_message(user_text)
2. ChatService build context tu workspace + selection hien tai
3. Assemble messages: [system_with_context] + chat_history + [user_msg]
4. Token budget check -> trim neu can
5. Start ChatWorker (QRunnable)
6. Worker stream -> emit signals -> UI update real-time

Thread Safety:
- send_message() duoc goi tu Main thread
- ChatWorker chay tren background thread
- Giao tiep qua Qt Signals
"""

import logging
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from PySide6.QtCore import QObject, QThreadPool, Signal

from core.ai.base_provider import LLMMessage
from core.chat.context_injector import ContextInjector
from core.chat.message_types import ChatMessage, ChatSession
from core.chat.response_handler import ParsedResponse
from services.chat_worker import ChatWorker

if TYPE_CHECKING:
    from services.prompt_build_service import PromptBuildService

logger = logging.getLogger(__name__)

# Token budget mac dinh cho context (de lai room cho conversation history)
_DEFAULT_MAX_CONTEXT_TOKENS = 50000
# So messages cu toi da giu trong conversation history
_MAX_HISTORY_MESSAGES = 40


class ChatServiceSignals(QObject):
    """
    Qt Signals cho ChatService.

    Cho phep UI connect vao de nhan updates real-time.
    """

    # Emit moi chunk text tu LLM
    chunk_received = Signal(str)
    # Emit khi LLM hoan tat response (chua full text)
    response_finished = Signal(str)
    # Emit khi co loi
    error_occurred = Signal(str)
    # Emit khi phat hien OPX blocks trong response
    opx_detected = Signal(object)  # ParsedResponse
    # Emit khi session thay doi (them message, v.v.)
    session_updated = Signal()
    # Emit khi bat dau xu ly (de hien thi loading indicator)
    processing_started = Signal()
    # Emit khi ket thuc xu ly
    processing_finished = Signal()


class ChatService(QObject):
    """
    Main orchestrator cho chatbot feature.

    Quan ly:
    - Current chat session (messages history)
    - Context injection (workspace context)
    - Worker lifecycle (start/cancel/generation counter)
    - History persistence (qua ChatHistoryStore)

    Attributes:
        signals: ChatServiceSignals de giao tiep voi UI
    """

    def __init__(
        self,
        prompt_builder: Optional["PromptBuildService"] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        """
        Khoi tao ChatService.

        Args:
            prompt_builder: PromptBuildService de generate context.
                            Neu None, se khoi tao instance moi.
            parent: Qt parent object
        """
        super().__init__(parent)
        self.signals = ChatServiceSignals()

        # Context injector de build workspace context
        self._context_injector = ContextInjector(prompt_builder=prompt_builder)

        # Current session
        self._session: ChatSession = ChatSession()

        # Worker management: generation counter de cancel stale workers
        self._current_worker: Optional[ChatWorker] = None
        self._generation: int = 0

        # Workspace va selection state
        self._workspace: Optional[Path] = None
        self._selected_paths: List[str] = []

        # Settings cache
        self._api_key: str = ""
        self._base_url: str = "https://api.openai.com/v1"
        self._model_id: str = ""
        self._max_context_tokens: int = _DEFAULT_MAX_CONTEXT_TOKENS
        self._history_enabled: bool = True
        self._include_git_changes: bool = True

        # Load settings
        self._reload_settings()

    # === Public API ===

    def set_workspace(self, workspace: Optional[Path]) -> None:
        """
        Cap nhat workspace hien tai.

        Args:
            workspace: Path den workspace root
        """
        self._workspace = workspace

    def set_selected_paths(self, paths: List[str]) -> None:
        """
        Cap nhat danh sach files duoc chon.

        Args:
            paths: Danh sach file paths (relative hoac absolute)
        """
        self._selected_paths = list(paths)

    def send_message(self, user_text: str) -> None:
        """
        Gui tin nhan va bat dau stream response.

        Method nay:
        1. Them user message vao session
        2. Build context tu workspace
        3. Cancel worker cu neu dang chay
        4. Start ChatWorker moi

        Args:
            user_text: Noi dung tin nhan cua user
        """
        if not user_text.strip():
            return

        # Reload settings truoc moi request de lay gia tri moi nhat
        self._reload_settings()

        # Them user message vao session
        user_msg = ChatMessage(role="user", content=user_text.strip())
        self._session.add_message(user_msg)
        self.signals.session_updated.emit()

        # Cancel worker cu (neu co)
        self._cancel_current_worker()

        # Tang generation counter de invalid ket qua cu
        self._generation += 1
        current_gen = self._generation

        # Build messages cho LLM
        messages = self._build_llm_messages()

        if not self._model_id:
            self.signals.error_occurred.emit(
                "Chua cau hinh AI model. Vui long kiem tra Settings."
            )
            return

        self.signals.processing_started.emit()

        # Tao va start worker
        worker = ChatWorker(
            api_key=self._api_key,
            base_url=self._base_url,
            model_id=self._model_id,
            messages=messages,
            generation=current_gen,
            temperature=0.7,
        )

        # Connect signals
        worker.signals.chunk_received.connect(self._on_chunk_received)
        worker.signals.finished.connect(
            lambda text: self._on_worker_finished(text, current_gen)
        )
        worker.signals.error.connect(self._on_worker_error)
        worker.signals.opx_detected.connect(self._on_opx_detected)

        self._current_worker = worker
        QThreadPool.globalInstance().start(worker)

    def cancel_current_request(self) -> None:
        """Cancel request dang chay (neu co)."""
        self._cancel_current_worker()
        self.signals.processing_finished.emit()

    def get_session(self) -> ChatSession:
        """Lay current chat session."""
        return self._session

    def clear_session(self) -> None:
        """Reset conversation - tao session moi."""
        self._cancel_current_worker()
        self._session = ChatSession(
            workspace_path=str(self._workspace) if self._workspace else None
        )
        self.signals.session_updated.emit()

    def load_session(self, session: ChatSession) -> None:
        """
        Load mot session cu de resume.

        Args:
            session: ChatSession can load
        """
        self._cancel_current_worker()
        self._session = session
        self.signals.session_updated.emit()

    def save_current_session(self) -> None:
        """Luu current session ra disk."""
        if not self._workspace or not self._session.messages:
            return

        try:
            from services.chat_history_store import save_session

            save_session(
                workspace=self._workspace,
                session=self._session,
                history_enabled=self._history_enabled,
            )
        except Exception as e:
            logger.warning("Could not save chat session: %s", e)

    # === Private Methods ===

    def _reload_settings(self) -> None:
        """Load settings tu settings_manager."""
        try:
            from services.settings_manager import load_app_settings

            settings = load_app_settings()
            self._api_key = settings.ai_api_key
            self._base_url = settings.ai_base_url
            # Dung chat_model_id neu co, fallback ve ai_model_id
            self._model_id = (
                getattr(settings, "chat_model_id", "") or settings.ai_model_id
            )
            self._max_context_tokens = getattr(
                settings, "chat_max_context_tokens", _DEFAULT_MAX_CONTEXT_TOKENS
            )
            self._history_enabled = getattr(settings, "chat_history_enabled", True)
            self._include_git_changes = settings.include_git_changes
        except Exception as e:
            logger.warning("Could not reload chat settings: %s", e)

    def _build_llm_messages(self) -> List[LLMMessage]:
        """
        Tao danh sach messages cho LLM API.

        Format: [system_with_context, ...history..., last_user_msg]
        """
        # Build workspace context
        context = self._context_injector.build_context(
            workspace=self._workspace,
            selected_paths=self._selected_paths,
            include_git_changes=self._include_git_changes,
            max_tokens=self._max_context_tokens,
        )

        # System message voi context
        system_content = context.build_system_prompt()
        messages: List[LLMMessage] = [LLMMessage(role="system", content=system_content)]

        # Add conversation history (trim neu can)
        history = self._get_trimmed_history()
        messages.extend(history)

        return messages

    def _get_trimmed_history(self) -> List[LLMMessage]:
        """
        Lay history da trim de fit trong token budget.

        Sliding window: giu lai MAX_HISTORY_MESSAGES messages moi nhat.
        """
        all_messages = self._session.messages
        if not all_messages:
            return []

        # Lay toi da _MAX_HISTORY_MESSAGES messages moi nhat
        recent = all_messages[-_MAX_HISTORY_MESSAGES:]

        return [
            LLMMessage(role=msg.role, content=msg.content)
            for msg in recent
            if msg.role in ("user", "assistant")
        ]

    def _cancel_current_worker(self) -> None:
        """Cancel worker dang chay neu co."""
        if self._current_worker:
            self._current_worker.cancel()
            self._current_worker = None

    def _on_chunk_received(self, chunk: str) -> None:
        """Xu ly chunk text tu worker -> forward toi UI."""
        self.signals.chunk_received.emit(chunk)

    def _on_worker_finished(self, full_text: str, generation: int) -> None:
        """
        Xu ly khi worker hoan tat.

        Kiem tra generation counter de tranh xu ly ket qua cu
        (neu user da gui message moi trong luc stream).
        """
        # Check xem result nay co phai la stale khong
        if generation != self._generation:
            logger.debug(
                "Ignoring stale worker result (gen %d != %d)",
                generation,
                self._generation,
            )
            return

        # Them assistant message vao session
        if full_text:
            assistant_msg = ChatMessage(role="assistant", content=full_text)
            self._session.add_message(assistant_msg)
            self.signals.session_updated.emit()

        self.signals.response_finished.emit(full_text)
        self.signals.processing_finished.emit()

        # Luu session sau moi turn hoan tat
        self.save_current_session()

    def _on_worker_error(self, error_msg: str) -> None:
        """Xu ly loi tu worker."""
        self.signals.error_occurred.emit(error_msg)
        self.signals.processing_finished.emit()

    def _on_opx_detected(self, parsed: ParsedResponse) -> None:
        """Forward OPX detection toi UI."""
        self.signals.opx_detected.emit(parsed)
