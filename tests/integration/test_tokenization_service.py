"""
Integration tests cho TokenizationService.

Test cac tuong tac THUC giua cac component:
- TokenizationService <-> core.encoders (encoder lifecycle)
- TokenizationService <-> TokenCache (cache invalidation)
- encoder_registry <-> TokenizationService (singleton, DI)
- Thread safety voi concurrent access
- Model switching + encoder reload
- Batch processing voi mixed file types
- Fallback warning (Option 2b)
"""

import time
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from services.tokenization_service import TokenizationService
from services.interfaces.tokenization_service import ITokenizationService


# ================================================================
# A. Interface Compliance
# ================================================================


class TestInterfaceCompliance:
    """Verify TokenizationService implements ITokenizationService dung contract."""

    def test_is_subclass(self):
        """TokenizationService la subclass cua ITokenizationService."""
        assert issubclass(TokenizationService, ITokenizationService)

    def test_instance_of_interface(self):
        """Instance la instance cua ITokenizationService."""
        service = TokenizationService()
        assert isinstance(service, ITokenizationService)

    def test_all_abstract_methods_implemented(self):
        """Tat ca abstract methods deu duoc implement."""
        # Neu thieu bat ky method nao, Python se raise TypeError khi instantiate
        service = TokenizationService()
        assert hasattr(service, "count_tokens")
        assert hasattr(service, "count_tokens_for_file")
        assert hasattr(service, "count_tokens_batch_parallel")
        assert hasattr(service, "set_model_config")
        assert hasattr(service, "reset_encoder")
        assert hasattr(service, "clear_cache")
        assert hasattr(service, "clear_file_from_cache")
        assert all(
            callable(getattr(service, m))
            for m in [
                "count_tokens",
                "count_tokens_for_file",
                "count_tokens_batch_parallel",
                "set_model_config",
                "reset_encoder",
                "clear_cache",
                "clear_file_from_cache",
            ]
        )


# ================================================================
# B. Singleton via encoder_registry
# ================================================================


class TestEncoderRegistrySingleton:
    """Test encoder_registry.get_tokenization_service() singleton behavior."""

    def test_returns_same_instance(self):
        """get_tokenization_service() luon tra ve cung 1 instance."""
        import services.encoder_registry as reg

        svc1 = reg.get_tokenization_service()
        svc2 = reg.get_tokenization_service()
        assert svc1 is svc2

    def test_returns_interface_type(self):
        """get_tokenization_service() tra ve ITokenizationService."""
        import services.encoder_registry as reg

        svc = reg.get_tokenization_service()
        assert isinstance(svc, ITokenizationService)

    def test_thread_safe_init(self):
        """Concurrent calls to get_tokenization_service() tra ve cung 1 instance."""
        import services.encoder_registry as reg

        results = []

        def get_service():
            svc = reg.get_tokenization_service()
            results.append(id(svc))

        threads = [threading.Thread(target=get_service) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Tat ca threads phai nhan duoc cung 1 instance
        assert len(set(results)) == 1, "Singleton bi tao nhieu instance!"


# ================================================================
# C. Thread Safety
# ================================================================


class TestThreadSafety:
    """Test concurrent count_tokens() calls khong bi race condition."""

    def test_concurrent_count_tokens(self):
        """Nhieu threads goi count_tokens() dong thoi phai cho ket qua nhat quan."""
        service = TokenizationService()
        text = "Hello, world! This is a test."
        expected = service.count_tokens(text)

        errors = []

        def count_in_thread():
            for _ in range(20):
                result = service.count_tokens(text)
                if result != expected:
                    errors.append(f"Expected {expected}, got {result}")

        threads = [threading.Thread(target=count_in_thread) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race conditions detected: {errors[:5]}"

    def test_concurrent_file_counting(self, tmp_path):
        """Multiple threads dem token cung 1 file cho ket qua nhat quan."""
        test_file = tmp_path / "thread_test.py"
        test_file.write_text("def hello():\n    print('world')\n" * 10)

        service = TokenizationService()
        expected = service.count_tokens_for_file(test_file)

        results = []

        def count_file():
            result = service.count_tokens_for_file(test_file)
            results.append(result)

        threads = [threading.Thread(target=count_file) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r == expected for r in results), (
            f"Inconsistent results: {set(results)}"
        )

    def test_concurrent_count_and_reset(self):
        """count_tokens() va reset_encoder() dong thoi khong crash."""
        service = TokenizationService()
        errors = []

        def count_loop():
            for _ in range(50):
                try:
                    service.count_tokens("test string for counting")
                except Exception as e:
                    errors.append(str(e))

        def reset_loop():
            for _ in range(10):
                try:
                    service.reset_encoder()
                    time.sleep(0.01)
                except Exception as e:
                    errors.append(str(e))

        t1 = threading.Thread(target=count_loop)
        t2 = threading.Thread(target=reset_loop)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0, f"Errors during concurrent access: {errors[:5]}"


# ================================================================
# D. Cache Invalidation
# ================================================================


class TestCacheInvalidation:
    """Test cache lifecycle: put, get, invalidate, mtime-based refresh."""

    def test_cache_returns_same_value_for_unchanged_file(self, tmp_path):
        """File khong thay doi -> cache hit."""
        service = TokenizationService()
        test_file = tmp_path / "cached.py"
        test_file.write_text("x = 1")

        count1 = service.count_tokens_for_file(test_file)
        count2 = service.count_tokens_for_file(test_file)
        assert count1 == count2

    def test_cache_invalidated_when_file_modified(self, tmp_path):
        """File thay doi (mtime thay doi) -> cache miss -> dem lai."""
        service = TokenizationService()
        test_file = tmp_path / "modified.py"
        test_file.write_text("x = 1")

        count1 = service.count_tokens_for_file(test_file)

        # Dam bao mtime thay doi bang cach sleep va ghi lai
        time.sleep(0.05)
        test_file.write_text("x = 1\n" * 100)

        count2 = service.count_tokens_for_file(test_file)
        assert count2 > count1, "Cache phai bi invalidate khi file thay doi"

    def test_clear_file_from_cache(self, tmp_path):
        """clear_file_from_cache() xoa dung file khoi cache."""
        service = TokenizationService()
        file_a = tmp_path / "a.py"
        file_b = tmp_path / "b.py"
        file_a.write_text("a = 1")
        file_b.write_text("b = 2")

        # Populate cache
        service.count_tokens_for_file(file_a)
        service.count_tokens_for_file(file_b)

        # Clear chi file a
        service.clear_file_from_cache(str(file_a))

        # File b van con trong cache (khong bi anh huong)
        assert service._cache.get(str(file_b), file_b.stat().st_mtime) is not None

    def test_clear_cache_empties_all(self, tmp_path):
        """clear_cache() xoa toan bo entries."""
        service = TokenizationService()
        for i in range(5):
            f = tmp_path / f"file{i}.py"
            f.write_text(f"x = {i}")
            service.count_tokens_for_file(f)

        service.clear_cache()

        # Sau khi clear, khong co cache hit nao
        for i in range(5):
            f = tmp_path / f"file{i}.py"
            cached = service._cache.get(str(f), f.stat().st_mtime)
            assert cached is None, f"Cache van con entry cho file{i}.py"


# ================================================================
# E. Model Switching
# ================================================================


class TestModelSwitching:
    """Test set_model_config() va reset_encoder() lifecycle."""

    def test_set_model_config_resets_internal_state(self):
        """set_model_config() reset encoder va encoder_type."""
        service = TokenizationService()

        # Init encoder
        service.count_tokens("test")

        # Switch model
        service.set_model_config(tokenizer_repo="Xenova/claude-tokenizer")

        # Internal state phai duoc reset
        assert service._encoder is None
        assert service._encoder_type == ""
        assert service._using_estimation is False
        assert service._tokenizer_repo == "Xenova/claude-tokenizer"

    def test_reset_encoder_allows_lazy_reinit(self):
        """Sau reset_encoder(), count_tokens() van hoat dong (lazy re-init)."""
        service = TokenizationService()

        count1 = service.count_tokens("Hello world")
        service.reset_encoder()
        count2 = service.count_tokens("Hello world")

        # Ca hai phai tra ve ket qua hop le
        assert count1 > 0
        assert count2 > 0

    def test_set_model_config_clears_estimation_flag(self):
        """set_model_config() reset _using_estimation flag."""
        service = TokenizationService()
        service._using_estimation = True

        service.set_model_config(tokenizer_repo=None)
        assert not service._using_estimation


# ================================================================
# F. Fallback Warning (Option 2b)
# ================================================================


class TestFallbackWarning:
    """Test Option 2b: warning log + estimation khi encoder khong kha dung."""

    def test_fallback_returns_estimation(self):
        """Khi encoder = None, count_tokens fallback ve _estimate_tokens."""
        service = TokenizationService()
        service._encoder = None

        # Force _get_or_create_encoder to return None
        with patch.object(service, "_get_or_create_encoder", return_value=None):
            result = service.count_tokens("a" * 100)
            assert result == 25  # 100 / 4

    def test_warning_emitted_once(self):
        """Warning chi duoc emit 1 lan (khong spam log)."""
        service = TokenizationService()

        with patch.object(service, "_get_or_create_encoder", return_value=None):
            with patch("services.tokenization_service.log_warning") as mock_warn:
                service.count_tokens("test1")
                service.count_tokens("test2")
                service.count_tokens("test3")

                # Chi 1 lan warning
                assert mock_warn.call_count == 1

    def test_warning_reset_after_set_model_config(self):
        """Sau set_model_config, warning flag duoc reset."""
        service = TokenizationService()
        service._using_estimation = True

        service.set_model_config(tokenizer_repo=None)

        # Flag phai duoc reset
        assert not service._using_estimation


# ================================================================
# G. File Handling Edge Cases
# ================================================================


class TestFileHandlingEdgeCases:
    """Test cac edge cases khi dem token cho file."""

    def test_nonexistent_file(self):
        """File khong ton tai -> return 0."""
        service = TokenizationService()
        assert service.count_tokens_for_file(Path("/nonexistent/path.py")) == 0

    def test_directory_path(self, tmp_path):
        """Directory path -> return 0."""
        service = TokenizationService()
        assert service.count_tokens_for_file(tmp_path) == 0

    def test_empty_file(self, tmp_path):
        """Empty file -> return 0."""
        service = TokenizationService()
        f = tmp_path / "empty.py"
        f.write_text("")
        assert service.count_tokens_for_file(f) == 0

    def test_binary_file(self, tmp_path):
        """Binary file (JPEG) -> return 0."""
        service = TokenizationService()
        f = tmp_path / "image.jpg"
        f.write_bytes(bytes([0xFF, 0xD8, 0xFF, 0xE0] + [0] * 100))
        assert service.count_tokens_for_file(f) == 0

    def test_large_file_skipped(self, tmp_path):
        """File > 5MB -> return 0, khong doc."""
        service = TokenizationService()
        f = tmp_path / "large.txt"
        f.write_text("x" * (6 * 1024 * 1024))
        assert service.count_tokens_for_file(f) == 0

    def test_utf8_file(self, tmp_path):
        """File voi Vietnamese text -> dem dung."""
        service = TokenizationService()
        f = tmp_path / "viet.py"
        f.write_text("# Xin chao the gioi\nprint('Hello')")
        result = service.count_tokens_for_file(f)
        assert result > 0

    def test_symlink_to_file(self, tmp_path):
        """Symlink tro den file thuc -> dem duoc."""
        service = TokenizationService()
        real_file = tmp_path / "real.py"
        real_file.write_text("x = 42")
        link_file = tmp_path / "link.py"
        link_file.symlink_to(real_file)

        result = service.count_tokens_for_file(link_file)
        assert result > 0


# ================================================================
# H. Batch Processing
# ================================================================


class TestBatchProcessing:
    """Test count_tokens_batch_parallel() voi nhieu scenarios."""

    def test_empty_list(self):
        """Empty list -> empty dict."""
        service = TokenizationService()
        with patch(
            "services.tokenization_service.is_counting_tokens", return_value=True
        ):
            result = service.count_tokens_batch_parallel([])
            assert result == {}

    def test_batch_with_mixed_files(self, tmp_path):
        """Batch voi text + binary + nonexistent files."""
        service = TokenizationService()

        # Text file
        text_file = tmp_path / "code.py"
        text_file.write_text("def hello():\n    return 42\n" * 5)

        # Binary file
        binary_file = tmp_path / "img.jpg"
        binary_file.write_bytes(bytes([0xFF, 0xD8, 0xFF, 0xE0] + [0] * 100))

        # Nonexistent file
        missing = tmp_path / "missing.py"

        with patch(
            "services.tokenization_service.is_counting_tokens", return_value=True
        ):
            results = service.count_tokens_batch_parallel(
                [text_file, binary_file, missing], max_workers=2
            )

        assert str(text_file) in results
        assert results[str(text_file)] > 0
        assert results.get(str(binary_file), 0) == 0
        assert results.get(str(missing), 0) == 0

    def test_batch_updates_cache(self, tmp_path):
        """Batch processing phai update cache cho files da dem."""
        service = TokenizationService()

        files = []
        for i in range(5):
            f = tmp_path / f"file{i}.py"
            f.write_text(f"x = {i}\n" * 10)
            files.append(f)

        with patch(
            "services.tokenization_service.is_counting_tokens", return_value=True
        ):
            results = service.count_tokens_batch_parallel(files, max_workers=2)

        # Verify cache duoc populate
        for f in files:
            cached = service._cache.get(str(f), f.stat().st_mtime)
            assert cached is not None, f"Cache miss cho {f.name}"
            assert cached == results[str(f)]

    def test_batch_cancelled_returns_partial(self, tmp_path):
        """Khi is_counting_tokens() = False giua chung, tra ve {} (empty)."""
        service = TokenizationService()

        files = []
        for i in range(5):
            f = tmp_path / f"cancel{i}.py"
            f.write_text(f"y = {i}")
            files.append(f)

        # Cancellation flag = False -> return empty
        with patch(
            "services.tokenization_service.is_counting_tokens", return_value=False
        ):
            result = service.count_tokens_batch_parallel(files)
            assert result == {}


# ================================================================
# I. mmap File Reading
# ================================================================


class TestMmapReading:
    """Test _read_file_mmap() doc file hieu qua."""

    def test_read_normal_file(self, tmp_path):
        """Doc file binh thuong qua mmap."""
        service = TokenizationService()
        f = tmp_path / "normal.txt"
        content = "Hello, world!\nLine 2"
        f.write_text(content)

        result = service._read_file_mmap(f)
        assert result == content

    def test_read_empty_file(self, tmp_path):
        """Doc empty file -> return empty string."""
        service = TokenizationService()
        f = tmp_path / "empty.txt"
        f.write_text("")

        result = service._read_file_mmap(f)
        assert result == ""

    def test_read_large_file(self, tmp_path):
        """Doc file lon qua mmap van dung."""
        service = TokenizationService()
        f = tmp_path / "large.txt"
        content = "A" * 100_000
        f.write_text(content)

        result = service._read_file_mmap(f)
        assert result is not None
        assert len(result) == 100_000


# ================================================================
# J. Isolation Between Instances
# ================================================================


class TestInstanceIsolation:
    """Verify 2 TokenizationService instances khong chia se state."""

    def test_separate_caches(self, tmp_path):
        """Moi instance co cache rieng."""
        svc1 = TokenizationService()
        svc2 = TokenizationService()

        f = tmp_path / "isolated.py"
        f.write_text("x = 1")

        svc1.count_tokens_for_file(f)

        # svc2 chua dem file nay -> cache miss
        cached_in_svc2 = svc2._cache.get(str(f), f.stat().st_mtime)
        assert cached_in_svc2 is None

    def test_separate_encoder_state(self):
        """Reset encoder cua svc1 khong anh huong svc2."""
        svc1 = TokenizationService()
        svc2 = TokenizationService()

        # Init encoder cho ca hai
        svc1.count_tokens("test")
        svc2.count_tokens("test")

        # Reset svc1
        svc1._encoder = None
        svc1._encoder_type = ""

        # svc2 van con encoder
        assert svc2._encoder is not None or svc2._using_estimation

    def test_different_model_configs(self):
        """2 instances co the dung model khac nhau."""
        svc1 = TokenizationService(tokenizer_repo=None)
        svc2 = TokenizationService(tokenizer_repo="Xenova/claude-tokenizer")

        assert svc1._tokenizer_repo != svc2._tokenizer_repo

        # Ca hai van dem duoc
        assert svc1.count_tokens("test") > 0
        assert svc2.count_tokens("test") > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
