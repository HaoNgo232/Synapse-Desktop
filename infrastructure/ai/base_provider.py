"""
BaseLLMProvider - Abstract Base Class dinh nghia contract cho moi LLM provider.

Tuan thu Open/Closed Principle (SOLID):
- Dong voi viec sua doi: Logic cua Context Builder UI KHONG can thay doi
  khi them provider moi.
- Mo voi viec mo rong: Chi can tao class ke thua BaseLLMProvider va override
  cac methods la co the ho tro provider moi (Anthropic, Gemini, etc.).

Moi provider PHAI implement:
1. fetch_available_models() - Lay danh sach model tu server
2. generate_structured() - Goi API va ep tra ve JSON structured output
3. generate_stream() - Goi API va stream tung chunk (phong ho chatbot/agent)

Thread Safety: Cac method trong class nay co the duoc goi tu background thread
(QRunnable). Implementation can dam bao thread-safe cho cac shared resources.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional


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


@dataclass
class LLMResponse:
    """
    Ket qua tra ve tu LLM provider sau khi goi API.

    Attributes:
        content: Noi dung text tra ve tu model
        model: ID cua model da su dung
        usage: Thong tin su dung token (prompt_tokens, completion_tokens, total_tokens)
        raw: Response goc tu provider (de debug neu can)
    """

    content: str
    model: str = ""
    usage: Optional[Dict[str, int]] = None
    raw: Optional[Dict[str, Any]] = None


@dataclass
class StreamChunk:
    """
    Mot phan nho cua response khi stream (Server-Sent Events).

    Attributes:
        delta: Noi dung text moi trong chunk nay
        done: True neu day la chunk cuoi cung (ket thuc stream)
    """

    delta: str
    done: bool = False


class BaseLLMProvider(ABC):
    """
    Abstract Base Class dinh nghia contract cho tat ca LLM providers.

    Bat ky provider nao (OpenAI, Anthropic, Gemini, Local LLM) deu PHAI
    implement tat ca cac abstract methods de dam bao tuong thich voi
    Context Builder va cac tinh nang AI khac trong tuong lai.

    Liskov Substitution Principle: Moi subclass co the thay the BaseLLMProvider
    ma khong lam thay doi hanh vi cua code su dung no.
    """

    @abstractmethod
    def configure(self, api_key: str, base_url: str = "") -> None:
        """
        Cau hinh credentials va endpoint cho provider.

        Args:
            api_key: API key de xac thuc voi provider
            base_url: URL goc cua API (de trong neu dung mac dinh cua provider)
        """
        ...

    @abstractmethod
    def fetch_available_models(self) -> List[str]:
        """
        Lay danh sach cac model IDs ma server dang ho tro.

        Su dung de populate dropdown tren UI Settings.
        Voi OpenAI-compatible APIs, goi endpoint GET /v1/models.
        Voi cac provider khac, co the hardcode hoac goi API tuong ung.

        Returns:
            List cac model ID strings (VD: ["gpt-4o", "gpt-4o-mini"])

        Raises:
            ConnectionError: Khi khong ket noi duoc toi server
            AuthenticationError: Khi API key khong hop le
        """
        ...

    @abstractmethod
    def generate_structured(
        self,
        messages: List[LLMMessage],
        model_id: str,
        json_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """
        Goi API va ep LLM tra ve JSON structured output.

        Day la method CHINH cho tinh nang Context Builder:
        - Gui System prompt + User prompt
        - Nhan ve JSON chua danh sach file paths

        Args:
            messages: Danh sach messages trong conversation
            model_id: ID cua model can su dung
            json_schema: JSON Schema de ep buoc response format (optional)
            temperature: Do "sang tao" cua model (0.0 = deterministic)

        Returns:
            LLMResponse chua content la JSON string

        Raises:
            ConnectionError: Khi khong ket noi duoc toi server
            ValueError: Khi response khong dung dinh dang mong doi
        """
        ...

    @abstractmethod
    def generate_stream(
        self,
        messages: List[LLMMessage],
        model_id: str,
        temperature: float = 0.7,
    ) -> Generator[StreamChunk, None, None]:
        """
        Goi API va stream response tung chunk (Server-Sent Events).

        Phong ho cho tinh nang chatbot/agent tuong lai.
        Cho phep hien thi response theo thoi gian thuc tren UI.

        Args:
            messages: Danh sach messages trong conversation
            model_id: ID cua model can su dung
            temperature: Do "sang tao" cua model

        Yields:
            StreamChunk voi delta text va trang thai done

        Raises:
            ConnectionError: Khi khong ket noi duoc toi server
        """
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """
        Kiem tra provider da duoc cau hinh (co api_key) chua.

        Returns:
            True neu da co api_key va base_url hop le
        """
        ...

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Tra ve ten hien thi cua provider (de dung tren UI).

        Returns:
            Ten provider (VD: "OpenAI Compatible", "Anthropic Claude")
        """
        ...
