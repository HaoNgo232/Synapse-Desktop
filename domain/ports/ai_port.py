from dataclasses import dataclass
from typing import List, Protocol, runtime_checkable

@dataclass
class LLMMessage:
    role: str
    content: str

@dataclass
class LLMResponse:
    content: str
    token_count: int

@runtime_checkable
class IAIProvider(Protocol):
    def generate(self, messages: List[LLMMessage]) -> LLMResponse:
        ...
