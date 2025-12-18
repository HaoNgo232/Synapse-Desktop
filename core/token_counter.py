"""
Token Counter - Dem token su dung tiktoken

Port tu: /home/hao/Desktop/labs/overwrite/src/services/token-counter.ts
Don gian hoa dang ke vi tiktoken la Python native library (OpenAI official).
"""

from pathlib import Path
from typing import Optional
import tiktoken

# Lazy-loaded encoder singleton
_encoder: Optional[tiktoken.Encoding] = None

# Guardrail: skip files > 5MB
MAX_BYTES = 5 * 1024 * 1024


def _get_encoder() -> tiktoken.Encoding:
    """
    Lay encoder singleton (o200k_base cho GPT-4o/GPT-4o-mini).
    Tao mot lan, dung lai de tiet kiem thoi gian.
    """
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("o200k_base")
    return _encoder


def count_tokens(text: str) -> int:
    """
    Dem so token trong mot doan text.
    
    Args:
        text: Text can dem token
        
    Returns:
        So luong tokens
    """
    encoder = _get_encoder()
    return len(encoder.encode(text))


def count_tokens_for_file(file_path: Path) -> int:
    """
    Dem so token trong mot file.
    
    - Skip files qua lon (> 5MB)
    - Skip binary files
    - Return 0 neu khong doc duoc
    
    Args:
        file_path: Duong dan den file
        
    Returns:
        So luong tokens, hoac 0 neu skip/error
    """
    try:
        # Check file size
        stat = file_path.stat()
        if stat.st_size > MAX_BYTES:
            return 0
        
        # Check if binary (read first 8KB)
        with open(file_path, 'rb') as f:
            chunk = f.read(8000)
        
        if _looks_binary(chunk):
            return 0
        
        # Read and count
        content = file_path.read_text(encoding='utf-8', errors='replace')
        return count_tokens(content)
        
    except (OSError, IOError):
        return 0


def _looks_binary(chunk: bytes) -> bool:
    """
    Kiem tra xem data co phai la binary khong.
    
    Logic port tu TypeScript:
    - Check magic numbers (PDF, ZIP, EXE, etc.)
    - Check ti le null bytes va non-printable characters
    """
    if len(chunk) == 0:
        return False
    
    # Check magic numbers
    if _check_magic_numbers(chunk):
        return True
    
    # Analyze byte content
    return _analyze_byte_content(chunk)


# Magic number signatures cho cac format binary pho bien
MAGIC_NUMBERS = [
    (bytes([0xFF, 0xD8, 0xFF]), "JPEG"),
    (bytes([0x89, 0x50, 0x4E, 0x47]), "PNG"),
    (bytes([0x47, 0x49, 0x46, 0x38]), "GIF"),
    (bytes([0x25, 0x50, 0x44, 0x46]), "PDF"),
    (bytes([0x50, 0x4B, 0x03, 0x04]), "ZIP"),
    (bytes([0x50, 0x4B, 0x05, 0x06]), "ZIP (empty)"),
    (bytes([0x7F, 0x45, 0x4C, 0x46]), "ELF"),
    (bytes([0x4D, 0x5A]), "PE/EXE"),
    (bytes([0xCA, 0xFE, 0xBA, 0xBE]), "Mach-O"),
]


def _check_magic_numbers(chunk: bytes) -> bool:
    """Check if chunk starts with known binary magic numbers"""
    for signature, _ in MAGIC_NUMBERS:
        if len(chunk) >= len(signature) and chunk[:len(signature)] == signature:
            return True
    return False


def _analyze_byte_content(chunk: bytes) -> bool:
    """
    Analyze byte content de detect binary.
    
    - > 1% null bytes -> binary
    - > 30% non-printable -> binary
    """
    if len(chunk) == 0:
        return False
    
    non_printable_count = 0
    null_byte_count = 0
    
    for byte in chunk:
        if byte == 0:
            null_byte_count += 1
        elif byte < 32 and byte not in (9, 10, 13):  # Exclude tab, LF, CR
            non_printable_count += 1
        elif byte > 126:
            non_printable_count += 1
    
    # > 1% null bytes -> binary
    if null_byte_count > len(chunk) * 0.01:
        return True
    
    # > 30% non-printable -> binary
    if non_printable_count > len(chunk) * 0.3:
        return True
    
    return False
