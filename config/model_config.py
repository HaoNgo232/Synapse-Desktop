"""
Model Configuration - Định nghĩa các LLM models và context limits

Lưu trữ thông tin các model phổ biến để hiển thị warning
khi số token vượt quá giới hạn context window.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ModelConfig:
    """
    Cấu hình cho một LLM model.

    Attributes:
        id: ID duy nhất của model (VD: "gpt-5.1")
        name: Tên hiển thị (VD: "GPT-5.1")
        context_length: Kích thước context window (số tokens tối đa)
        tokenizer_repo: Hugging Face repo cho tokenizer (None = dùng tiktoken)
    """

    id: str
    name: str
    context_length: int
    tokenizer_repo: Optional[str] = None


# Danh sách các model phổ biến với context limits
# Cập nhật theo yêu cầu user
MODEL_CONFIGS: List[ModelConfig] = [
    # OpenAI (dùng tiktoken/rs-bpe)
    ModelConfig(id="gpt-5.1", name="GPT-5.1", context_length=200000),
    ModelConfig(id="gpt-5.1-thinking", name="GPT-5.1 Thinking", context_length=200000),
    
    # Anthropic (dùng Xenova/claude-tokenizer)
    ModelConfig(
        id="claude-opus-4.5", 
        name="Claude Opus 4.5", 
        context_length=200000,
        tokenizer_repo="Xenova/claude-tokenizer"
    ),
    ModelConfig(
        id="claude-sonnet-4.5", 
        name="Claude Sonnet 4.5", 
        context_length=200000,
        tokenizer_repo="Xenova/claude-tokenizer"
    ),
    ModelConfig(
        id="claude-haiku-4.5", 
        name="Claude Haiku 4.5", 
        context_length=200000,
        tokenizer_repo="Xenova/claude-tokenizer"
    ),
    
    # Google (dùng Xenova/gemma-tokenizer - không gated)
    ModelConfig(
        id="gemini-3-pro", 
        name="Gemini 3 Pro", 
        context_length=1000000,
        tokenizer_repo="Xenova/gemma-tokenizer"
    ),
    ModelConfig(
        id="gemini-3-flash", 
        name="Gemini 3 Flash", 
        context_length=1000000,
        tokenizer_repo="Xenova/gemma-tokenizer"
    ),
    
    # DeepSeek (dùng deepseek-ai/DeepSeek-V2 - public, MIT license)
    ModelConfig(
        id="deepseek-v3.1", 
        name="DeepSeek V3.1", 
        context_length=128000,
        tokenizer_repo="deepseek-ai/DeepSeek-V2"
    ),
    ModelConfig(
        id="deepseek-r1", 
        name="DeepSeek R1", 
        context_length=128000,
        tokenizer_repo="deepseek-ai/DeepSeek-V2"
    ),
    
    # xAI (dùng Xenova/grok-1-tokenizer - không gated)
    ModelConfig(
        id="grok-4", 
        name="Grok 4", 
        context_length=256000,
        tokenizer_repo="Xenova/grok-1-tokenizer"
    ),
    
    # Alibaba (dùng Qwen/Qwen2.5-7B - public, không gated)
    ModelConfig(
        id="qwen3-235b", 
        name="Qwen3 235B", 
        context_length=256000,
        tokenizer_repo="Qwen/Qwen2.5-7B"
    ),
    
    # Meta (dùng Xenova/llama-3-tokenizer - không gated)
    ModelConfig(
        id="llama-4-scout", 
        name="Llama 4 Scout", 
        context_length=10000000,
        tokenizer_repo="Xenova/llama-3-tokenizer"
    ),
]

# Default model ID khi chưa chọn
DEFAULT_MODEL_ID = "claude-sonnet-4.5"


def get_model_by_id(model_id: str) -> Optional[ModelConfig]:
    """
    Lấy model config theo ID.

    Args:
        model_id: ID của model cần tìm

    Returns:
        ModelConfig nếu tìm thấy, None nếu không
    """
    for model in MODEL_CONFIGS:
        if model.id == model_id:
            return model
    return None


def get_model_options() -> List[tuple]:
    """
    Lấy danh sách options cho dropdown.

    Returns:
        List of (display_text, model_id) tuples
    """
    return [
        (f"{m.name} ({_format_context_length(m.context_length)})", m.id)
        for m in MODEL_CONFIGS
    ]


def _format_context_length(length: int) -> str:
    """Format context length cho hiển thị (VD: 200k, 1M)"""
    if length >= 1000000:
        return f"{length // 1000000}M"
    elif length >= 1000:
        return f"{length // 1000}k"
    return str(length)
