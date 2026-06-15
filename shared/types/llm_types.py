from dataclasses import dataclass


@dataclass
class LLMMessage:
    """
    Mot message trong chuoi hoi thoai (conversation history).

    Attributes:
        role: Vai tro cua nguoi gui ("system", "user", "assistant")
        content: Noi dung tin nhan
    """

    role: str  # "system" | "user" | "assistant"
    content: str
