"""
Chat Message Types - Dataclasses cho chat messages va session state.

Cac type nay la pure Python dataclasses, khong phu thuoc Qt.
Duoc dung boi ChatService, ChatWorker, va ChatHistoryStore.

Types:
    ChatMessage: Mot tin nhan trong cuoc tro chuyen
    ChatSession: Toan bo session tro chuyen (chua list messages)
    ChatContext: Context snapshot duoc inject vao system message
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional


# Role cua nguoi gui tin nhan
ChatRole = Literal["user", "assistant", "system"]

# Do dai toi da cua session title (se them "..." neu dai hon)
_MAX_TITLE_LENGTH = 60


@dataclass
class ChatMessage:
    """
    Mot tin nhan trong cuoc tro chuyen.

    Attributes:
        role: Vai tro nguoi gui ("user" | "assistant" | "system")
        content: Noi dung tin nhan
        timestamp: Thoi diem gui tin nhan (ISO format)
        message_id: ID duy nhat cho tin nhan
        metadata: Du lieu phu them (VD: token counts, model info)
    """

    role: ChatRole
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Chuyen doi thanh dict de serialize JSON."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "message_id": self.message_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        """Tao ChatMessage tu dict (de deserialize tu JSON)."""
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            message_id=data.get("message_id", str(uuid.uuid4())),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ChatSession:
    """
    Toan bo session tro chuyen.

    Chua danh sach messages va metadata cua session.
    Moi workspace co the co nhieu sessions.

    Attributes:
        session_id: ID duy nhat cua session
        messages: Danh sach cac tin nhan trong session
        workspace_path: Duong dan workspace hien tai
        created_at: Thoi diem tao session
        updated_at: Thoi diem cap nhat cuoi cung
        title: Tieu de session (tu dong tao tu tin nhan dau tien)
    """

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    messages: List[ChatMessage] = field(default_factory=list)
    workspace_path: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    title: str = "New Chat"

    def add_message(self, message: ChatMessage) -> None:
        """Them message vao session va cap nhat updated_at."""
        self.messages.append(message)
        self.updated_at = datetime.now().isoformat()
        # Tu dong dat title tu tin nhan user dau tien
        if len(self.messages) == 1 and message.role == "user":
            self.title = message.content[:_MAX_TITLE_LENGTH].strip()
            if len(message.content) > _MAX_TITLE_LENGTH:
                self.title += "..."

    def get_history_for_llm(self) -> List[Dict[str, str]]:
        """
        Lay lich su chat theo format cho LLM API.

        Loai bo system messages (se duoc inject rieng),
        chi giu user va assistant messages.

        Returns:
            List dict {"role": ..., "content": ...} cho LLM
        """
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.messages
            if msg.role in ("user", "assistant")
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Chuyen doi thanh dict de serialize JSON."""
        return {
            "session_id": self.session_id,
            "messages": [m.to_dict() for m in self.messages],
            "workspace_path": self.workspace_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatSession":
        """Tao ChatSession tu dict (de deserialize tu JSON)."""
        messages = [ChatMessage.from_dict(m) for m in data.get("messages", [])]
        return cls(
            session_id=data.get("session_id", str(uuid.uuid4())),
            messages=messages,
            workspace_path=data.get("workspace_path"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            title=data.get("title", "New Chat"),
        )


@dataclass
class ChatContext:
    """
    Context snapshot duoc inject vao system message moi lan chat.

    Chua cac thong tin ve workspace, files duoc chon, va trang thai hien tai.
    Duoc tao boi ContextInjector moi khi user gui tin nhan.

    Attributes:
        file_map: ASCII tree cua thu muc workspace
        selected_files_content: Noi dung cac files duoc chon
        git_diffs: Git diff hien tai (neu co)
        project_rules: Noi dung cac rule files (AGENTS.md, .cursorrules, v.v.)
        memory: Continuous memory tu cac phien truoc (neu co)
        workspace_path: Duong dan workspace
        selected_file_paths: Danh sach paths cac files duoc chon
        token_count: Tong so tokens cua context (uoc tinh)
    """

    file_map: str = ""
    selected_files_content: str = ""
    git_diffs: str = ""
    project_rules: str = ""
    memory: str = ""
    workspace_path: Optional[str] = None
    selected_file_paths: List[str] = field(default_factory=list)
    token_count: int = 0

    def is_empty(self) -> bool:
        """Kiem tra context co rong hay khong."""
        return not (
            self.file_map
            or self.selected_files_content
            or self.git_diffs
            or self.project_rules
        )

    def build_system_prompt(self) -> str:
        """
        Tao system message tu context hien tai.

        System message se duoc inject vao dau moi conversation,
        chua toan bo thong tin workspace de LLM co the tro loi chinh xac.

        Returns:
            System prompt string da duoc format
        """
        parts: List[str] = [
            "You are an expert software developer assistant with deep knowledge of "
            "the codebase. You help the user understand, modify, and improve their code.\n"
            "When suggesting code changes, use OPX format:\n"
            "<edit file='path/to/file' op='new|patch|replace|remove|move'>\n"
            "  <put><<<\n  new content\n>>></put>\n"
            "</edit>\n"
        ]

        if self.workspace_path:
            parts.append(f"\n## Workspace\n`{self.workspace_path}`\n")

        if self.memory:
            parts.append(f"\n## Previous Session Memory\n{self.memory}\n")

        if self.project_rules:
            parts.append(f"\n## Project Rules\n{self.project_rules}\n")

        if self.file_map:
            parts.append(f"\n## Project Structure\n```\n{self.file_map}\n```\n")

        if self.selected_files_content:
            parts.append(
                f"\n## Selected Files Content\n{self.selected_files_content}\n"
            )

        if self.git_diffs:
            parts.append(f"\n## Recent Git Changes\n{self.git_diffs}\n")

        return "".join(parts)
