"""
Binary Detection - Phat hien file binary dua tren magic numbers va byte analysis.

Module chua cac ham phat hien binary file:
- _looks_binary_fast(): Kiem tra nhanh (optimized) dua tren signatures va sampling
- _looks_binary(): Kiem tra day du (magic numbers + byte analysis)
- _check_magic_numbers(): Kiem tra magic number header
- _analyze_byte_content(): Phan tich ty le null bytes va non-printable chars

Note: Production code chinh su dung `is_binary_file()` tu `core/utils/file_utils.py`.
Cac ham o day la low-level utilities duoc test rieng va co the tai su dung.
"""

# Pre-compiled patterns cho binary detection
_BINARY_SIGNATURES = [
    (b"\xff\xd8\xff", "JPEG"),
    (b"\x89PNG", "PNG"),
    (b"GIF8", "GIF"),
    (b"%PDF", "PDF"),
    (b"PK\x03\x04", "ZIP"),
    (b"\x7fELF", "ELF"),
    (b"MZ", "PE/EXE"),
]


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


def _looks_binary_fast(chunk: bytes) -> bool:
    """
    Optimized binary detection su dung pre-compiled signatures.

    Nhanh hon _looks_binary() vi dung _BINARY_SIGNATURES (bytes literal)
    thay vi MAGIC_NUMBERS (bytes constructor). Ket hop sampling de kiem tra
    null bytes va non-printable characters.

    Args:
        chunk: Du lieu bytes can kiem tra

    Returns:
        True neu co ve la binary
    """
    if len(chunk) == 0:
        return False

    # Kiem tra magic signatures truoc (fast path)
    for sig, _ in _BINARY_SIGNATURES:
        if chunk.startswith(sig):
            return True

    # Sampling-based analysis cho chunks lon
    sample_size = min(len(chunk), 1000)
    sample = chunk[:sample_size]

    # Dem null bytes
    null_count = sample.count(b"\x00")
    if null_count > sample_size * 0.01:
        return True

    # Kiem tra nhanh non-printable bang bytes translation
    non_printable = sum(1 for b in sample if b < 32 and b not in (9, 10, 13) or b > 126)
    if non_printable > sample_size * 0.3:
        return True

    return False


def _check_magic_numbers(chunk: bytes) -> bool:
    """
    Kiem tra chunk bat dau bang known binary magic numbers.

    Args:
        chunk: Du lieu bytes can kiem tra

    Returns:
        True neu chunk bat dau bang magic number nhan biet
    """
    for signature, _ in MAGIC_NUMBERS:
        if len(chunk) >= len(signature) and chunk[: len(signature)] == signature:
            return True
    return False


def _analyze_byte_content(chunk: bytes) -> bool:
    """
    Phan tich noi dung bytes de phat hien binary.

    Tieu chi:
    - > 1% null bytes -> binary
    - > 30% non-printable characters -> binary

    Args:
        chunk: Du lieu bytes can phan tich

    Returns:
        True neu noi dung co dac diem binary
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


def _looks_binary(chunk: bytes) -> bool:
    """
    Kiem tra xem data co phai la binary khong (comprehensive check).

    Logic:
    1. Kiem tra magic numbers (PDF, ZIP, EXE, etc.)
    2. Kiem tra ti le null bytes va non-printable characters

    Args:
        chunk: Du lieu bytes can kiem tra

    Returns:
        True neu data la binary
    """
    if len(chunk) == 0:
        return False

    # Kiem tra magic numbers
    if _check_magic_numbers(chunk):
        return True

    # Phan tich byte content
    return _analyze_byte_content(chunk)
