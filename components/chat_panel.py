"""
Chat Panel - Main chat UI widget.

Panel cho phep user tro chuyen voi LLM trong context cua workspace.

Layout:
+-----------------------------------------+
| [Chat] [New] [Clear]    [model] [files] |  <- header
+-----------------------------------------+
|                                         |
|  [message bubbles scroll area]          |
|                                         |
+-----------------------------------------+
| [text input area]          [Send Ctrl+Enter] |
+-----------------------------------------+

Features:
- Multi-line text input (Ctrl+Enter to send)
- Streaming response (real-time chunk display)
- OPX Apply button inline khi response chua OPX
- Session history list
- Context indicator (so files dang trong context)
"""

import logging
from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.chat.message_types import ChatMessage
from core.chat.response_handler import ParsedResponse
from core.theme import ThemeColors, ThemeFonts
from components.chat_message_widget import ChatMessageWidget

logger = logging.getLogger(__name__)


class _StreamingMessageWidget(ChatMessageWidget):
    """
    Message widget dac biet cho response dang streaming.

    Giu trang thai partial content de append chunks real-time.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        msg = ChatMessage(role="assistant", content="")
        super().__init__(msg, parent=parent)
        self._accumulated = ""

    def append_chunk(self, chunk: str) -> None:
        """Append mot chunk text moi."""
        self._accumulated += chunk
        self.update_content(self._accumulated)

    def get_final_content(self) -> str:
        """Lay noi dung hoan chinh sau khi stream xong."""
        return self._accumulated


class ChatInputField(QTextEdit):
    """
    Text input field cho chat - ho tro Ctrl+Enter de send.

    Override keyPressEvent de bat Ctrl+Enter.
    Callback duoc inject qua constructor thay vi mutable class attribute.
    """

    def __init__(
        self,
        on_send: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._on_send = on_send

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Bat Ctrl+Enter de gui tin nhan."""
        if (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            if self._on_send:
                self._on_send()
        else:
            super().keyPressEvent(event)


class ChatPanel(QWidget):
    """
    Main chat UI widget.

    Integrate voi ChatService de stream LLM responses va hien thi
    message bubbles trong scrollable area.
    """

    def __init__(
        self,
        get_workspace: Callable[[], Optional[Path]],
        get_selected_paths: Callable[[], List[str]],
        chat_service: Optional[object] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Khoi tao ChatPanel.

        Args:
            get_workspace: Callable tra ve workspace path hien tai
            get_selected_paths: Callable tra ve danh sach paths duoc chon
            chat_service: ChatService instance (inject tu ServiceContainer)
            parent: Qt parent widget
        """
        super().__init__(parent)
        self._get_workspace = get_workspace
        self._get_selected_paths = get_selected_paths
        self._chat_service = chat_service
        self._streaming_widget: Optional[_StreamingMessageWidget] = None

        self._build_ui()
        self._connect_service()

    def _build_ui(self) -> None:
        """Build UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = self._build_header()
        layout.addWidget(header)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {ThemeColors.BORDER};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        # Messages area
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll_area.setStyleSheet(
            f"QScrollArea {{ background: {ThemeColors.BG_PAGE}; border: none; }}"
        )

        self._messages_container = QWidget()
        self._messages_container.setStyleSheet(f"background: {ThemeColors.BG_PAGE};")
        self._messages_layout = QVBoxLayout(self._messages_container)
        self._messages_layout.setContentsMargins(8, 8, 8, 8)
        self._messages_layout.setSpacing(4)
        self._messages_layout.addStretch()  # Push messages xuong cuoi

        self._scroll_area.setWidget(self._messages_container)
        layout.addWidget(self._scroll_area, stretch=1)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"background-color: {ThemeColors.BORDER};")
        sep2.setFixedHeight(1)
        layout.addWidget(sep2)

        # Input area
        input_area = self._build_input_area()
        layout.addWidget(input_area)

    def _build_header(self) -> QFrame:
        """Build header bar."""
        header = QFrame()
        header.setFixedHeight(44)
        header.setStyleSheet(f"background: {ThemeColors.BG_SURFACE};")
        hlayout = QHBoxLayout(header)
        hlayout.setContentsMargins(12, 0, 12, 0)
        hlayout.setSpacing(8)

        # Title
        title = QLabel("💬  Chat")
        title.setStyleSheet(
            f"color: {ThemeColors.TEXT_PRIMARY}; "
            f"font-size: {ThemeFonts.SIZE_SUBTITLE}px; font-weight: 700;"
        )
        hlayout.addWidget(title)
        hlayout.addStretch()

        # Context indicator
        self._context_label = QLabel("No files selected")
        self._context_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED}; font-size: {ThemeFonts.SIZE_CAPTION}px;"
        )
        hlayout.addWidget(self._context_label)

        # New Chat button
        new_btn = QPushButton("+ New Chat")
        new_btn.setFixedHeight(28)
        new_btn.setStyleSheet(
            f"background: {ThemeColors.BG_ELEVATED}; "
            f"color: {ThemeColors.TEXT_SECONDARY}; "
            f"border: 1px solid {ThemeColors.BORDER}; "
            f"border-radius: 4px; padding: 0 10px; "
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
        )
        new_btn.clicked.connect(self._on_new_chat)
        hlayout.addWidget(new_btn)

        return header

    def _build_input_area(self) -> QFrame:
        """Build input area (text field + send button)."""
        area = QFrame()
        area.setStyleSheet(f"background: {ThemeColors.BG_SURFACE};")
        alayout = QVBoxLayout(area)
        alayout.setContentsMargins(12, 8, 12, 8)
        alayout.setSpacing(6)

        # Status label (hien thi trang thai: "Thinking...", loi, v.v.)
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED}; font-size: {ThemeFonts.SIZE_CAPTION}px;"
        )
        self._status_label.setVisible(False)
        alayout.addWidget(self._status_label)

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        # Text input - inject on_send callback via constructor
        self._input_field = ChatInputField(on_send=self._on_send)
        self._input_field.setMinimumHeight(60)
        self._input_field.setMaximumHeight(120)
        self._input_field.setPlaceholderText(
            "Ask anything about your code... (Ctrl+Enter to send)"
        )
        self._input_field.setStyleSheet(
            f"background: {ThemeColors.BG_ELEVATED}; "
            f"color: {ThemeColors.TEXT_PRIMARY}; "
            f"border: 1px solid {ThemeColors.BORDER}; "
            f"border-radius: 6px; "
            f"padding: 8px; "
            f"font-size: {ThemeFonts.SIZE_BODY}px;"
        )
        input_row.addWidget(self._input_field, stretch=1)

        # Send button
        self._send_btn = QPushButton("Send")
        self._send_btn.setFixedSize(80, 60)
        self._send_btn.setStyleSheet(
            f"background: {ThemeColors.PRIMARY}; "
            f"color: white; border: none; border-radius: 6px; "
            f"font-size: {ThemeFonts.SIZE_BODY}px; font-weight: 600;"
        )
        self._send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self._send_btn)

        alayout.addLayout(input_row)

        # Hint
        hint = QLabel("Ctrl+Enter to send")
        hint.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED}; font-size: {ThemeFonts.SIZE_CAPTION}px;"
        )
        alayout.addWidget(hint)

        return area

    def _connect_service(self) -> None:
        """Connect ChatService signals toi UI slots."""
        if self._chat_service is None:
            return

        svc = self._chat_service
        if hasattr(svc, "signals"):
            svc.signals.chunk_received.connect(self._on_chunk_received)
            svc.signals.response_finished.connect(self._on_response_finished)
            svc.signals.error_occurred.connect(self._on_error)
            svc.signals.opx_detected.connect(self._on_opx_detected)
            svc.signals.processing_started.connect(self._on_processing_started)
            svc.signals.processing_finished.connect(self._on_processing_finished)
            svc.signals.session_updated.connect(self._on_session_updated)

    def update_context_indicator(self, paths: List[str]) -> None:
        """
        Cap nhat context indicator (so files dang trong context).

        Args:
            paths: Danh sach paths duoc chon
        """
        if paths:
            self._context_label.setText(f"📎 {len(paths)} file(s) in context")
        else:
            self._context_label.setText("No files selected")

    # === Slots ===

    @Slot()
    def _on_send(self) -> None:
        """Xu ly khi user click Send hoac Ctrl+Enter."""
        text = self._input_field.toPlainText().strip()
        if not text:
            return

        if self._chat_service is None:
            self._show_error("Chat service chua duoc khoi tao. Kiem tra Settings.")
            return

        # Cap nhat workspace va selection cho service
        workspace = self._get_workspace()
        selected = self._get_selected_paths()
        self._chat_service.set_workspace(workspace)
        self._chat_service.set_selected_paths(selected)

        # Clear input TRUOC khi gui (tranh user gui lai)
        self._input_field.clear()

        # Gui qua service - service se add message vao session va emit session_updated
        # UI se nhan session_updated va re-render message
        self._chat_service.send_message(text)

    @Slot()
    def _on_new_chat(self) -> None:
        """Bat dau session moi."""
        if self._chat_service:
            self._chat_service.clear_session()
        self._clear_messages_ui()

    @Slot()
    def _on_session_updated(self) -> None:
        """
        Re-render messages khi session thay doi.

        Duoc goi khi ChatService add message vao session (user message)
        hoac sau khi response hoan tat (assistant message).
        Chi re-render tin nhan moi nhat de tranh double-rendering.
        """
        if self._chat_service is None:
            return

        session = self._chat_service.get_session()
        if not session.messages:
            return

        # Lay tin nhan cuoi cung chua duoc render
        last_msg = session.messages[-1]

        # Chi them user messages qua duong session_updated
        # Assistant messages duoc xu ly qua streaming widget
        if last_msg.role == "user":
            self._add_message_widget(last_msg)

    @Slot(str)
    def _on_chunk_received(self, chunk: str) -> None:
        """Xu ly chunk text tu LLM - append vao streaming widget."""
        if self._streaming_widget is None:
            # Tao streaming widget moi
            self._streaming_widget = _StreamingMessageWidget(parent=None)
            self._add_widget_to_messages(self._streaming_widget)

        self._streaming_widget.append_chunk(chunk)
        self._scroll_to_bottom()

    @Slot(str)
    def _on_response_finished(self, full_text: str) -> None:
        """Xu ly khi response hoan tat."""
        self._streaming_widget = None

    @Slot(object)
    def _on_opx_detected(self, parsed: ParsedResponse) -> None:
        """Xu ly khi OPX duoc phat hien trong response."""
        # OPX apply buttons se duoc hien thi trong assistant message bubbles
        # khi message duoc re-render sau khi stream xong
        pass

    @Slot(str)
    def _on_error(self, error_msg: str) -> None:
        """Hien thi loi tu LLM."""
        self._streaming_widget = None
        self._show_error(error_msg)

    @Slot()
    def _on_processing_started(self) -> None:
        """Hien thi trang thai dang xu ly."""
        self._send_btn.setEnabled(False)
        self._send_btn.setText("...")
        self._show_status("Thinking...")

    @Slot()
    def _on_processing_finished(self) -> None:
        """Hien thi trang thai da xong xu ly."""
        self._send_btn.setEnabled(True)
        self._send_btn.setText("Send")
        self._hide_status()

    # === Private Helpers ===

    def _add_message_widget(
        self,
        message: ChatMessage,
        parsed: Optional[ParsedResponse] = None,
    ) -> ChatMessageWidget:
        """
        Them mot message widget vao UI.

        Args:
            message: ChatMessage can hien thi
            parsed: ParsedResponse neu co OPX

        Returns:
            ChatMessageWidget da them vao
        """
        widget = ChatMessageWidget(message, parsed_response=parsed)
        widget.copy_requested.connect(self._on_copy_message)
        if parsed and parsed.has_actionable_opx:
            widget.apply_opx_requested.connect(self._on_apply_opx)

        self._add_widget_to_messages(widget)
        self._scroll_to_bottom()
        return widget

    def _add_widget_to_messages(self, widget: QWidget) -> None:
        """Them widget vao messages container (truoc stretch)."""
        # Insert truoc stretch (stretch la item cuoi cung)
        count = self._messages_layout.count()
        self._messages_layout.insertWidget(count - 1, widget)

    def _clear_messages_ui(self) -> None:
        """Xoa tat ca message widgets khoi UI."""
        self._streaming_widget = None
        # Xoa tat ca widgets tru stretch cuoi cung
        while self._messages_layout.count() > 1:
            item = self._messages_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def _scroll_to_bottom(self) -> None:
        """Scroll xuong cuoi messages area."""
        scrollbar = self._scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _show_error(self, error_msg: str) -> None:
        """Hien thi error message."""
        error_label = QLabel(f"⚠️ {error_msg}")
        error_label.setWordWrap(True)
        error_label.setStyleSheet(
            f"color: {ThemeColors.ERROR}; "
            f"background: transparent; "
            f"padding: 8px; "
            f"font-size: {ThemeFonts.SIZE_BODY}px;"
        )
        self._add_widget_to_messages(error_label)
        self._scroll_to_bottom()

    def _show_status(self, text: str) -> None:
        """Hien thi status message."""
        self._status_label.setText(text)
        self._status_label.setVisible(True)

    def _hide_status(self) -> None:
        """An status message."""
        self._status_label.setVisible(False)

    @Slot(str)
    def _on_copy_message(self, content: str) -> None:
        """Copy message content vao clipboard."""
        QApplication.clipboard().setText(content)
        try:
            from components.toast_qt import toast_success

            toast_success(self, "Copied to clipboard")
        except Exception:
            pass

    @Slot(object)
    def _on_apply_opx(self, parsed: ParsedResponse) -> None:
        """Apply OPX blocks tu response."""
        if not parsed.has_actionable_opx or not parsed.opx_result:
            return

        workspace = self._get_workspace()
        if not workspace:
            self._show_error("No workspace open.")
            return

        try:
            from core.file_actions import apply_file_actions
            from services.apply_service import convert_to_row_results

            results = apply_file_actions(parsed.opx_result.file_actions, workspace)
            row_results = convert_to_row_results(
                results, parsed.opx_result.file_actions
            )

            success_count = sum(1 for r in row_results if r.success)
            fail_count = len(row_results) - success_count

            try:
                from components.toast_qt import toast_success, toast_error

                if fail_count == 0:
                    toast_success(
                        self, f"Applied {success_count} change(s) successfully"
                    )
                else:
                    toast_error(
                        self,
                        f"Applied {success_count}, failed {fail_count} change(s)",
                    )
            except Exception:
                pass

            # Save memory block neu co
            if parsed.memory_block and parsed.has_memory:
                try:
                    from services.apply_service import save_memory_block

                    save_memory_block(workspace, parsed.memory_block)
                except Exception as e:
                    logger.warning("Could not save memory block: %s", e)

        except Exception as e:
            logger.exception("Error applying OPX from chat")
            self._show_error(f"Failed to apply changes: {e}")
