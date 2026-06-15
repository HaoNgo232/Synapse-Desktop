from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from shared.types.llm_types import LLMMessage


@dataclass
class LLMResponse:
    content: str
    model: str = ""
    usage: Optional[Dict[str, int]] = None
    raw: Optional[Dict[str, Any]] = None


@runtime_checkable
class IAIProvider(Protocol):
    def configure(self, api_key: str, base_url: str = "") -> None: ...

    def generate_structured(
        self,
        messages: List[LLMMessage],
        model_id: str,
        json_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.0,
    ) -> LLMResponse: ...
