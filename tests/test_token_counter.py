"""
Unit tests cho TokenizationService.

REFACTORED: Tests da duoc cap nhat tu core.token_counter (da xoa)
sang services.tokenization_service.TokenizationService.

Test cac case:
- count_tokens(): Dem tokens trong text
- count_tokens_for_file(): Dem tokens trong file, skip binary
- count_tokens_batch_parallel(): Parallel batch counting
- get_worker_count(): Tinh so workers toi uu
- Binary detection: Magic numbers, byte analysis
- Cache: clear_cache(), clear_file_from_cache()
"""

import pytest
from pathlib import Path
from unittest.mock import patch
import os

from services.tokenization_service import TokenizationService
from core.tokenization.batch import get_worker_count
from core.encoders import _estimate_tokens
from core.binary_detection import _looks_binary, _check_magic_numbers


class TestCountTokens:
    """Test TokenizationService.count_tokens()."""

    def setup_method(self):
        """Tao TokenizationService instance moi cho moi test."""
        self.service = TokenizationService()

    def test_empty_string(self):
        """Empty string returns 0 tokens."""
        assert self.service.count_tokens("") == 0

    def test_simple_text(self):
        """Simple text returns positive token count."""
        result = self.service.count_tokens("Hello, world!")
        assert result > 0
        assert isinstance(result, int)

    def test_code_snippet(self):
        """Code snippet returns reasonable token count."""
        code = """
def hello():
    print("Hello, World!")
    return 42
"""
        result = self.service.count_tokens(code)
        # Code thuong co ~1 token per 4 chars, nhung tiktoken khac
        assert result > 5
        assert result < 100

    def test_unicode_text(self):
        """Unicode text (Vietnamese) is handled correctly."""
        text = "Xin chao the gioi!"
        result = self.service.count_tokens(text)
        assert result > 0

    def test_very_long_text(self):
        """Very long text returns proportional token count."""
        short_text = "Hello " * 10
        long_text = "Hello " * 1000

        short_count = self.service.count_tokens(short_text)
        long_count = self.service.count_tokens(long_text)

        # Long text should have roughly 100x more tokens
        assert long_count > short_count * 50


class TestEstimateTokens:
    """Test _estimate_tokens() fallback function."""

    def test_empty_string(self):
        """Empty string estimates 0 tokens."""
        assert _estimate_tokens("") == 0

    def test_short_text(self):
        """Short text estimates at least 1 token."""
        assert _estimate_tokens("Hi") >= 1

    def test_known_length(self):
        """Text with known length estimates correctly (~4 chars = 1 token)."""
        text = "a" * 100
        estimate = _estimate_tokens(text)
        assert estimate == 25  # 100 / 4


class TestCountTokensForFile:
    """Test TokenizationService.count_tokens_for_file()."""

    def setup_method(self):
        """Tao TokenizationService instance moi cho moi test."""
        self.service = TokenizationService()

    def test_nonexistent_file(self):
        """Nonexistent file returns 0."""
        result = self.service.count_tokens_for_file(Path("/nonexistent/file.py"))
        assert result == 0

    def test_text_file(self, tmp_path):
        """Text file returns positive token count."""
        file_path = tmp_path / "test.py"
        file_path.write_text("def hello():\n    return 42")

        self.service.clear_cache()
        result = self.service.count_tokens_for_file(file_path)
        assert result > 0

    def test_empty_file(self, tmp_path):
        """Empty file returns 0 tokens."""
        file_path = tmp_path / "empty.txt"
        file_path.write_text("")

        self.service.clear_cache()
        result = self.service.count_tokens_for_file(file_path)
        assert result == 0

    def test_binary_file_skipped(self, tmp_path):
        """Binary file (JPEG magic number) returns 0."""
        file_path = tmp_path / "image.jpg"
        # Write JPEG magic number
        file_path.write_bytes(bytes([0xFF, 0xD8, 0xFF, 0xE0]))

        self.service.clear_cache()
        result = self.service.count_tokens_for_file(file_path)
        assert result == 0

    def test_large_file_skipped(self, tmp_path):
        """File > 5MB is skipped."""
        file_path = tmp_path / "large.txt"
        # Create file > 5MB
        file_path.write_text("x" * (6 * 1024 * 1024))

        self.service.clear_cache()
        result = self.service.count_tokens_for_file(file_path)
        assert result == 0

    def test_directory_returns_zero(self, tmp_path):
        """Directory path returns 0."""
        dir_path = tmp_path / "subdir"
        dir_path.mkdir()

        result = self.service.count_tokens_for_file(dir_path)
        assert result == 0

    def test_caching(self, tmp_path):
        """Results are cached based on mtime."""
        file_path = tmp_path / "cached.py"
        file_path.write_text("print('hello')")

        self.service.clear_cache()

        # First call
        result1 = self.service.count_tokens_for_file(file_path)

        # Second call should use cache
        result2 = self.service.count_tokens_for_file(file_path)

        assert result1 == result2


class TestGetWorkerCount:
    """Test get_worker_count() function."""

    def test_small_task_count(self):
        """Small task count returns 1 worker."""
        assert get_worker_count(5) == 1
        assert get_worker_count(50) == 1
        assert get_worker_count(99) == 1

    def test_medium_task_count(self):
        """Medium task count returns proportional workers."""
        # 100 tasks = 1 worker (TASKS_PER_WORKER = 100)
        assert get_worker_count(100) == 1
        # 200 tasks = 2 workers
        assert get_worker_count(200) == 2
        # 500 tasks = 5 workers
        assert get_worker_count(500) == 5

    def test_large_task_count_capped_by_cpu(self):
        """Large task count is capped by CPU cores."""
        cpu_count = os.cpu_count() or 4

        # 10000 tasks would need 100 workers, but capped by CPU
        result = get_worker_count(10000)
        assert result <= cpu_count
        assert result >= 1

    def test_zero_tasks(self):
        """Zero tasks returns 1 worker (minimum)."""
        assert get_worker_count(0) == 1


class TestBinaryDetection:
    """Test binary file detection functions."""

    def test_jpeg_magic_number(self):
        """JPEG magic number detected as binary."""
        chunk = bytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10])
        assert _check_magic_numbers(chunk) is True
        assert _looks_binary(chunk) is True

    def test_png_magic_number(self):
        """PNG magic number detected as binary."""
        chunk = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A])
        assert _check_magic_numbers(chunk) is True

    def test_pdf_magic_number(self):
        """PDF magic number detected as binary."""
        chunk = b"%PDF-1.4"
        assert _check_magic_numbers(chunk) is True

    def test_zip_magic_number(self):
        """ZIP magic number detected as binary."""
        chunk = bytes([0x50, 0x4B, 0x03, 0x04])
        assert _check_magic_numbers(chunk) is True

    def test_text_file_not_binary(self):
        """Plain text is not detected as binary."""
        chunk = b"def hello():\n    print('world')\n"
        assert _looks_binary(chunk) is False

    def test_null_bytes_binary(self):
        """File with many null bytes detected as binary."""
        # > 1% null bytes = binary
        chunk = b"text" + (b"\x00" * 10) + b"more"
        assert _looks_binary(chunk) is True

    def test_empty_chunk(self):
        """Empty chunk is not binary."""
        assert _looks_binary(b"") is False


class TestClearTokenCache:
    """Test TokenizationService cache operations."""

    def setup_method(self):
        """Tao TokenizationService instance moi cho moi test."""
        self.service = TokenizationService()

    def test_cache_cleared(self, tmp_path):
        """Cache is cleared successfully."""
        file_path = tmp_path / "test.py"
        file_path.write_text("print('x')")

        # Populate cache
        self.service.count_tokens_for_file(file_path)

        # Clear cache
        self.service.clear_cache()

        # Modify file
        file_path.write_text("print('y')" * 100)

        # Should get new count (not cached)
        new_count = self.service.count_tokens_for_file(file_path)
        assert new_count > 10  # Longer content


class TestModelConfig:
    """Test TokenizationService.set_model_config()."""

    def test_set_model_config_resets_encoder(self):
        """set_model_config() resets internal encoder state."""
        service = TokenizationService()

        # Count tokens to init encoder
        service.count_tokens("test")

        # Switch model
        service.set_model_config(tokenizer_repo="Xenova/claude-tokenizer")

        # Should work with new config
        result = service.count_tokens("test")
        assert result > 0

    def test_reset_encoder(self):
        """reset_encoder() forces encoder reload."""
        service = TokenizationService()

        # Count tokens to init encoder
        service.count_tokens("test")

        # Reset
        service.reset_encoder()

        # Should still work (lazy re-init)
        result = service.count_tokens("test")
        assert result > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
