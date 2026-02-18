"""
Encoders - Quan ly encoder/tokenizer singleton cho token counting.

Module nay quan ly viec chon va khoi tao encoder phu hop:
- rs-bpe (Rust implementation, nhanh hon ~5x)
- tiktoken (Python, fallback)
- Hugging Face tokenizers (cho models co custom tokenizer_repo)

DIP: Module nay KHONG import tu services layer.
Config (tokenizer_repo) duoc inject tu encoder_registry.

Functions:
- _get_encoder(tokenizer_repo): Lay encoder singleton (thread-safe)
- _get_hf_tokenizer(tokenizer_repo): Lay HF tokenizer singleton
- reset_encoder(): Reset khi user doi model
- _estimate_tokens(): Uoc luong tokens khi encoder khong kha dung
"""

import threading
from typing import Optional, Any, TYPE_CHECKING


# ============================================================
# Import tokenizer backends
# ============================================================

# Thu import rs-bpe truoc (nhanh hon, Rust-based)
try:
    from rs_bpe import openai as rs_bpe_openai

    HAS_RS_BPE = True
except ImportError:

    class _RsBpeStub:
        """Stub module khi rs-bpe khong duoc cai dat."""

        @staticmethod
        def o200k_base():
            return None

        @staticmethod
        def cl100k_base():
            return None

    rs_bpe_openai = _RsBpeStub()
    HAS_RS_BPE = False

# Fallback sang tiktoken
import tiktoken

# Thu import tokenizers cho models co custom tokenizer (vd: Claude)
if TYPE_CHECKING:
    from tokenizers import Tokenizer

    HAS_TOKENIZERS = True
else:
    try:
        from tokenizers import Tokenizer

        HAS_TOKENIZERS = True
    except ImportError:
        Tokenizer = None  # Se kiem tra HAS_TOKENIZERS truoc khi su dung
        HAS_TOKENIZERS = False


# ============================================================
# Encoder singleton state (thread-safe)
# ============================================================

# Lazy-loaded encoder singleton
_encoder: Optional[Any] = None
_encoder_type: str = ""  # "rs_bpe", "tiktoken", hoac "hf"
_claude_tokenizer: Optional[Any] = None
_encoder_lock = threading.Lock()


def _get_hf_tokenizer(tokenizer_repo: Optional[str] = None) -> Optional[Any]:
    """
    Lay Hugging Face tokenizer singleton.

    DIP: Nhan tokenizer_repo tu caller (inject tu encoder_registry),
    khong tu doc settings.

    Args:
        tokenizer_repo: HF repo ID (vd: "Xenova/claude-tokenizer").
                        None = khong dung HF tokenizer.

    Returns:
        HF Tokenizer instance hoac None
    """
    global _claude_tokenizer

    if _claude_tokenizer is not None:
        return _claude_tokenizer

    if not HAS_TOKENIZERS:
        return None

    if not tokenizer_repo:
        return None

    try:
        _claude_tokenizer = Tokenizer.from_pretrained(tokenizer_repo)
        from core.logging_config import log_info

        log_info(f"[Encoders] Using {tokenizer_repo} tokenizer")
        return _claude_tokenizer
    except Exception as e:
        from core.logging_config import log_error

        log_error(f"[Encoders] Failed to load tokenizer from {tokenizer_repo}: {e}")
        return None


def _get_encoder(tokenizer_repo: Optional[str] = None) -> Optional[Any]:
    """
    Lay encoder singleton (thread-safe).

    DIP: Nhan tokenizer_repo tu caller (inject tu encoder_registry),
    khong tu doc settings.

    Selection order:
    1. Model co tokenizer_repo -> Dung Hugging Face tokenizers
    2. rs-bpe (Rust, 5x nhanh hon tiktoken)
    3. tiktoken (Python fallback)

    Args:
        tokenizer_repo: HF repo ID hoac None (dung tiktoken/rs-bpe).

    Returns:
        Encoder instance hoac None
    """
    global _encoder, _encoder_type

    # Fast path: encoder da khoi tao (khong can lock)
    if _encoder is not None:
        return _encoder

    with _encoder_lock:
        # Double-check sau khi lay lock
        if _encoder is not None:
            return _encoder

    # Kiem tra model co custom tokenizer repo khong
    if tokenizer_repo:
        if _encoder_type == "hf" and _encoder is not None:
            return _encoder

        _encoder = _get_hf_tokenizer(tokenizer_repo)
        if _encoder is not None:
            _encoder_type = "hf"
            return _encoder
        # Fallback sang OpenAI tokenizer neu HF tokenizer that bai

    # Cho models khong co custom tokenizer hoac fallback
    if _encoder is not None and _encoder_type != "hf":
        return _encoder

    # Thu rs-bpe truoc (nhanh hon ~5x)
    if HAS_RS_BPE:
        try:
            _encoder = rs_bpe_openai.o200k_base()
            _encoder_type = "rs_bpe"
            from core.logging_config import log_info

            log_info("[Encoders] Using rs-bpe (Rust) - 5x faster than tiktoken")
            return _encoder
        except Exception:
            pass

        try:
            _encoder = rs_bpe_openai.cl100k_base()
            _encoder_type = "rs_bpe"
            from core.logging_config import log_info

            log_info("[Encoders] Using rs-bpe cl100k_base (Rust)")
            return _encoder
        except Exception:
            pass

    # Fallback ve tiktoken
    encodings_to_try = ["o200k_base", "cl100k_base", "p50k_base", "gpt2"]

    for encoding_name in encodings_to_try:
        try:
            _encoder = tiktoken.get_encoding(encoding_name)
            _encoder_type = "tiktoken"
            from core.logging_config import log_info

            log_info(f"[Encoders] Using tiktoken {encoding_name}")
            return _encoder
        except Exception:
            continue

    return None


def _estimate_tokens(text: str) -> int:
    """
    Uoc luong so token khi encoder khong kha dung.

    Quy tac: ~4 ky tu = 1 token (heuristic pho bien).
    Day la uoc luong, khong chinh xac 100%.

    Args:
        text: Text can uoc luong

    Returns:
        So token uoc luong
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def reset_encoder() -> None:
    """
    Reset encoder singleton khi user doi model.

    Goi function nay sau khi save settings voi model_id moi.
    """
    global _encoder, _encoder_type, _claude_tokenizer
    _encoder = None
    _encoder_type = ""
    _claude_tokenizer = None

    from core.logging_config import log_info

    log_info("[Encoders] Encoder reset - will reload on next count_tokens() call")
