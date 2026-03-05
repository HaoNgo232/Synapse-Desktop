"""
Chat Message Widget - Individual message bubble trong chat panel.

Hien thi mot tin nhan (user hoac assistant) trong chat.

Features:
- User messages: plain text, aligned phai, mau khac biet
- Assistant messages: scrollable text + OPX action buttons neu co
- Copy button moi message
- "Apply OPX" button khi response chua OPX blocks hop le
"""

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.chat.message_types import ChatMessage
from core.chat.response_handler import ParsedResponse
from core.theme import ThemeColors, ThemeFonts

logger = logging.getLogger(__name__)

# Height constants cho content text area
_CONTENT_HEIGHT_PADDING = 24  # Padding them vao doc_height de tranh scroll
_MIN_CONTENT_HEIGHT = 60  # Chieu cao toi thieu de doc content
_MAX_CONTENT_HEIGHT = 400  # Chieu cao toi da de tranh widget qua lon


class ChatMessageWidget(QFrame):
    """
    Widget hien thi mot tin nhan trong chat.

    User messages: compact, aligned phai, mau accent
    Assistant messages: full width, mau surface, co action buttons

    Signals:
        apply_opx_requested: Emit khi user click "Apply OPX"
            chua ParsedResponse cua response nay
        copy_requested: Emit khi user click "Copy"
    """

    apply_opx_requested = Signal(object)  # ParsedResponse
    copy_requested = Signal(str)  # message content

    def __init__(
        self,
        message: ChatMessage,
        parsed_response: Optional[ParsedResponse] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Khoi tao widget cho mot message.

        Args:
            message: ChatMessage can hien thi
            parsed_response: ParsedResponse neu day la assistant message (co OPX)
            parent: Qt parent widget
        """
        super().__init__(parent)
        self._message = message
        self._parsed_response = parsed_response
        self._is_user = message.role == "user"

        self._build_ui()

    def _build_ui(self) -> None:
        """Build UI cho message bubble."""
        self.setObjectName("chatMessageFrame")

        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(8, 4, 8, 4)
        outer_layout.setSpacing(0)

        # Tao bubble container
        bubble = QFrame()
        bubble.setObjectName(
            "chatUserBubble" if self._is_user else "chatAssistantBubble"
        )
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(12, 10, 12, 10)
        bubble_layout.setSpacing(6)

        # Role label
        role_label = QLabel("You" if self._is_user else "Assistant")
        role_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED}; font-size: {ThemeFonts.SIZE_CAPTION}px;"
        )
        bubble_layout.addWidget(role_label)

        # Content text
        if self._is_user:
            # User message: simple label
            content_label = QLabel(self._message.content)
            content_label.setWordWrap(True)
            content_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            content_label.setStyleSheet(
                f"color: {ThemeColors.TEXT_PRIMARY}; "
                f"font-size: {ThemeFonts.SIZE_BODY}px;"
            )
            bubble_layout.addWidget(content_label)
        else:
            # Assistant message: scrollable text edit (read-only)
            content_text = QTextEdit()
            content_text.setObjectName("chatAssistantText")
            content_text.setReadOnly(True)
            content_text.setPlainText(self._message.content)
            content_text.setMinimumHeight(40)
            # Auto-resize theo content
            doc_height = (
                int(content_text.document().size().height()) + _CONTENT_HEIGHT_PADDING
            )
            content_text.setFixedHeight(
                min(max(doc_height, _MIN_CONTENT_HEIGHT), _MAX_CONTENT_HEIGHT)
            )
            content_text.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            content_text.setStyleSheet(
                f"background: transparent; border: none; "
                f"color: {ThemeColors.TEXT_PRIMARY}; "
                f"font-size: {ThemeFonts.SIZE_BODY}px;"
            )
            bubble_layout.addWidget(content_text)

        # Action buttons (cho assistant messages)
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(6)
        actions_layout.setContentsMargins(0, 0, 0, 0)

        # Copy button (luon co)
        copy_btn = QPushButton("Copy")
        copy_btn.setObjectName("chatCopyBtn")
        copy_btn.setFixedHeight(26)
        copy_btn.setStyleSheet(self._action_btn_style())
        copy_btn.clicked.connect(
            lambda: self.copy_requested.emit(self._message.content)
        )
        actions_layout.addWidget(copy_btn)

        # Apply OPX button (chi cho assistant messages co OPX hop le)
        if (
            not self._is_user
            and self._parsed_response is not None
            and self._parsed_response.has_actionable_opx
        ):
            opx_btn = QPushButton("⚡ Apply OPX")
            opx_btn.setObjectName("chatApplyOPXBtn")
            opx_btn.setFixedHeight(26)
            opx_btn.setToolTip(
                f"Apply {len(self._parsed_response.opx_result.file_actions)} "  # type: ignore[union-attr]
                f"file action(s)"
            )
            opx_btn.setStyleSheet(
                f"background-color: {ThemeColors.SUCCESS_BG}; "
                f"color: white; "
                f"border: none; border-radius: 4px; "
                f"padding: 2px 10px; font-size: {ThemeFonts.SIZE_CAPTION}px;"
                f"font-weight: 600;"
            )
            opx_btn.clicked.connect(
                lambda: self.apply_opx_requested.emit(self._parsed_response)
            )
            actions_layout.addWidget(opx_btn)

        actions_layout.addStretch()
        bubble_layout.addLayout(actions_layout)

        # Align user messages sang phai
        if self._is_user:
            outer_layout.addStretch()
            outer_layout.addWidget(bubble)
            bubble.setMaximumWidth(500)
        else:
            outer_layout.addWidget(bubble)
            outer_layout.addStretch()

        # Style bubble
        if self._is_user:
            bubble.setStyleSheet(
                f"background-color: {ThemeColors.PRIMARY}; "
                f"border-radius: 12px 12px 2px 12px;"
            )
        else:
            bubble.setStyleSheet(
                f"background-color: {ThemeColors.BG_ELEVATED}; "
                f"border-radius: 2px 12px 12px 12px; "
                f"border: 1px solid {ThemeColors.BORDER};"
            )

    def _action_btn_style(self) -> str:
        """Style cho action buttons."""
        return (
            f"background-color: {ThemeColors.BG_SURFACE}; "
            f"color: {ThemeColors.TEXT_SECONDARY}; "
            f"border: 1px solid {ThemeColors.BORDER}; "
            f"border-radius: 4px; "
            f"padding: 2px 10px; "
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
        )

    def update_content(self, new_content: str) -> None:
        """
        Cap nhat noi dung message (dung khi streaming).

        Args:
            new_content: Noi dung moi cua message
        """
        self._message = ChatMessage(
            role=self._message.role,
            content=new_content,
            timestamp=self._message.timestamp,
            message_id=self._message.message_id,
        )
        # Find va update text widget
        content_text = self.findChild(QTextEdit, "chatAssistantText")
        if content_text:
            content_text.setPlainText(new_content)
            # Resize
            doc_height = (
                int(content_text.document().size().height()) + _CONTENT_HEIGHT_PADDING
            )
            content_text.setFixedHeight(
                min(max(doc_height, _MIN_CONTENT_HEIGHT), _MAX_CONTENT_HEIGHT)
            )
