"""
Unit tests cho core/tokenization/ package.

Test cac module:
- cancellation: Global cancellation flag (thread-safe)
- cache: TokenCache LRU voi mtime invalidation
- counter: Core counting logic (text + file)
- batch: Parallel/batch processing

Tong cong: ~55 tests.
"""

import os
import threading
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.tokenization.cancellation import (
    is_counting_tokens,
    start_token_counting,
    stop_token_counting,
)
from core.tokenization.cache import TokenCache, token_cache
from core.tokenization.counter import (
    count_tokens,
    count_tokens_for_file,
    _count_tokens_for_file_no_cache,
    _read_file_mmap,
    MAX_BYTES,
)
from core.tokenization.batch import (
    get_worker_count,
    count_tokens_batch,
    count_tokens_batch_parallel,
    TASKS_PER_WORKER,
    MIN_FILES_FOR_PARALLEL,
)


# ============================================================================
# CANCELLATION MODULE TESTS
# ============================================================================


class TestCancellationFlag:
    """Test thread-safe global cancellation flag."""

    def setup_method(self):
        """Reset flag truoc moi test."""
        stop_token_counting()

    def teardown_method(self):
        """Cleanup sau moi test."""
        stop_token_counting()

    def test_initial_state_is_false(self):
        """Flag ban dau la False."""
        assert is_counting_tokens() is False

    def test_start_sets_true(self):
        """start_token_counting() set flag = True."""
        start_token_counting()
        assert is_counting_tokens() is True

    def test_stop_sets_false(self):
        """stop_token_counting() set flag = False."""
        start_token_counting()
        stop_token_counting()
        assert is_counting_tokens() is False

    def test_start_stop_sequence(self):
        """Start -> check -> stop -> check."""
        assert is_counting_tokens() is False
        start_token_counting()
        assert is_counting_tokens() is True
        stop_token_counting()
        assert is_counting_tokens() is False

    def test_multiple_starts(self):
        """Nhieu lan start khong loi."""
        start_token_counting()
        start_token_counting()
        start_token_counting()
        assert is_counting_tokens() is True

    def test_multiple_stops(self):
        """Nhieu lan stop khong loi."""
        stop_token_counting()
        stop_token_counting()
        stop_token_counting()
        assert is_counting_tokens() is False

    def test_thread_safety_no_crash(self):
        """Concurrent reads/writes khong crash."""
        errors = []

        def toggle_flag():
            try:
                for _ in range(100):
                    start_token_counting()
                    is_counting_tokens()
                    stop_token_counting()
            except Exception as e:
                errors.append(e)

        # Chay 10 threads dong thoi
        threads = [threading.Thread(target=toggle_flag) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"Thread errors: {errors}"


# ============================================================================
# CACHE MODULE TESTS
# ============================================================================


class TestTokenCache:
    """Test TokenCache class (LRU with mtime invalidation)."""

    def setup_method(self):
        """Tao cache moi cho moi test."""
        self.cache = TokenCache(max_size=5)

    def test_get_returns_none_on_miss(self):
        """Cache miss tra ve None."""
        assert self.cache.get("/file.py", 1.0) is None

    def test_get_returns_count_on_hit(self):
        """Cache hit tra ve token count."""
        self.cache.put("/file.py", 1.0, 42)
        assert self.cache.get("/file.py", 1.0) == 42

    def test_get_returns_none_on_stale_mtime(self):
        """mtime thay doi -> cache miss (invalidation)."""
        self.cache.put("/file.py", 1.0, 42)
        # File da thay doi (mtime khac)
        assert self.cache.get("/file.py", 2.0) is None

    def test_get_moves_to_end_lru(self):
        """get() move entry to end (LRU behavior)."""
        self.cache.put("/a.py", 1.0, 10)
        self.cache.put("/b.py", 1.0, 20)
        self.cache.put("/c.py", 1.0, 30)

        # Access /a.py -> moves to end
        self.cache.get("/a.py", 1.0)

        # Fill to capacity (max_size=5) + evict
        self.cache.put("/d.py", 1.0, 40)
        self.cache.put("/e.py", 1.0, 50)
        self.cache.put("/f.py", 1.0, 60)  # Should evict /b.py (oldest)

        # /b.py evicted, /a.py still exists (was moved to end)
        assert self.cache.get("/b.py", 1.0) is None
        assert self.cache.get("/a.py", 1.0) == 10

    def test_get_no_move_does_not_reorder(self):
        """get_no_move() khong thay doi thu tu LRU."""
        self.cache.put("/a.py", 1.0, 10)
        self.cache.put("/b.py", 1.0, 20)

        # Access /a.py without moving
        result = self.cache.get_no_move("/a.py", 1.0)
        assert result == 10

    def test_get_no_move_returns_none_on_miss(self):
        """get_no_move() tra ve None khi miss."""
        assert self.cache.get_no_move("/file.py", 1.0) is None

    def test_get_no_move_returns_none_on_stale(self):
        """get_no_move() tra ve None khi mtime stale."""
        self.cache.put("/file.py", 1.0, 42)
        assert self.cache.get_no_move("/file.py", 2.0) is None

    def test_put_stores_entry(self):
        """put() luu entry thanh cong."""
        self.cache.put("/file.py", 1.0, 100)
        assert len(self.cache) == 1
        assert self.cache.get("/file.py", 1.0) == 100

    def test_put_evicts_oldest_at_capacity(self):
        """put() evict entry cu nhat khi dat max_size."""
        for i in range(5):
            self.cache.put(f"/file{i}.py", 1.0, i * 10)

        # Cache day (5 entries)
        assert len(self.cache) == 5

        # Them entry moi -> evict /file0.py
        self.cache.put("/new.py", 1.0, 999)
        assert len(self.cache) == 5
        assert self.cache.get("/file0.py", 1.0) is None
        assert self.cache.get("/new.py", 1.0) == 999

    def test_put_updates_existing_entry(self):
        """put() cho phep cap nhat entry da ton tai."""
        self.cache.put("/file.py", 1.0, 42)
        self.cache.put("/file.py", 2.0, 84)  # Update voi mtime moi
        assert self.cache.get("/file.py", 2.0) == 84
        assert self.cache.get("/file.py", 1.0) is None  # mtime cu khong con valid

    def test_put_batch_stores_multiple(self):
        """put_batch() luu nhieu entries cung luc."""
        entries = {
            "/a.py": (1.0, 10),
            "/b.py": (1.0, 20),
            "/c.py": (1.0, 30),
        }
        self.cache.put_batch(entries)
        assert len(self.cache) == 3
        assert self.cache.get("/a.py", 1.0) == 10
        assert self.cache.get("/b.py", 1.0) == 20
        assert self.cache.get("/c.py", 1.0) == 30

    def test_put_batch_evicts_when_full(self):
        """put_batch() evict khi vuot max_size."""
        # Fill 3 entries
        self.cache.put("/x.py", 1.0, 1)
        self.cache.put("/y.py", 1.0, 2)
        self.cache.put("/z.py", 1.0, 3)

        # Batch add 4 entries -> max_size 5, must evict 2
        entries = {
            "/a.py": (1.0, 10),
            "/b.py": (1.0, 20),
            "/c.py": (1.0, 30),
            "/d.py": (1.0, 40),
        }
        self.cache.put_batch(entries)

        # /x.py va /y.py bi evict
        assert self.cache.get("/x.py", 1.0) is None
        assert self.cache.get("/y.py", 1.0) is None
        assert len(self.cache) == 5

    def test_clear_empties_cache(self):
        """clear() xoa toan bo."""
        self.cache.put("/a.py", 1.0, 10)
        self.cache.put("/b.py", 1.0, 20)
        self.cache.clear()
        assert len(self.cache) == 0
        assert self.cache.get("/a.py", 1.0) is None

    def test_clear_file_removes_single(self):
        """clear_file() xoa mot entry cu the."""
        self.cache.put("/a.py", 1.0, 10)
        self.cache.put("/b.py", 1.0, 20)
        self.cache.clear_file("/a.py")
        assert self.cache.get("/a.py", 1.0) is None
        assert self.cache.get("/b.py", 1.0) == 20
        assert len(self.cache) == 1

    def test_clear_file_nonexistent(self):
        """clear_file() voi path khong ton tai khong loi."""
        self.cache.clear_file("/nonexistent.py")  # Should not raise

    def test_len_returns_count(self):
        """__len__() tra ve so entries chinh xac."""
        assert len(self.cache) == 0
        self.cache.put("/a.py", 1.0, 10)
        assert len(self.cache) == 1
        self.cache.put("/b.py", 1.0, 20)
        assert len(self.cache) == 2

    def test_thread_safety_concurrent_access(self):
        """Concurrent put/get khong crash."""
        cache = TokenCache(max_size=100)
        errors = []

        def writer(start_idx):
            try:
                for i in range(50):
                    cache.put(f"/file_{start_idx}_{i}.py", 1.0, i)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(50):
                    cache.get(f"/file_0_{i}.py", 1.0)
            except Exception as e:
                errors.append(e)

        threads = []
        for idx in range(5):
            threads.append(threading.Thread(target=writer, args=(idx,)))
        threads.append(threading.Thread(target=reader))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"Thread errors: {errors}"


class TestTokenCacheSingleton:
    """Test module-level token_cache singleton."""

    def setup_method(self):
        """Clear singleton cache truoc moi test."""
        token_cache.clear()

    def test_singleton_is_token_cache(self):
        """Singleton la instance cua TokenCache."""
        assert isinstance(token_cache, TokenCache)

    def test_singleton_persistent(self):
        """Singleton giu state giua cac lan truy cap."""
        token_cache.put("/test.py", 1.0, 42)
        # Import lai va kiem tra
        from core.tokenization.cache import token_cache as same_cache

        assert same_cache.get("/test.py", 1.0) == 42


# ============================================================================
# COUNTER MODULE TESTS
# ============================================================================


class TestCountTokens:
    """Test count_tokens() function."""

    def test_empty_string(self):
        """Empty text tra ve 0."""
        assert count_tokens("") == 0

    def test_simple_text(self):
        """Text don gian tra ve positive count."""
        result = count_tokens("Hello, world!")
        assert result > 0
        assert isinstance(result, int)

    def test_code_snippet(self):
        """Code snippet tra ve reasonable count."""
        code = "def hello():\n    return 42\n"
        result = count_tokens(code)
        assert 3 < result < 20

    def test_unicode_text(self):
        """Unicode (tieng Viet) duoc xu ly dung."""
        text = "Xin chao the gioi!"
        result = count_tokens(text)
        assert result > 0

    def test_fallback_when_encoder_none(self):
        """Fallback uoc luong khi encoder = None."""
        with patch("core.tokenization.counter.get_encoder", return_value=None):
            text = "Hello world test"
            result = count_tokens(text)
            # Estimation: ~len/4
            assert result > 0

    def test_fallback_when_encode_raises(self):
        """Fallback khi encode() raise exception."""
        mock_encoder = MagicMock()
        mock_encoder.encode.side_effect = RuntimeError("encoding failed")

        with patch("core.tokenization.counter.get_encoder", return_value=mock_encoder):
            with patch("core.encoders._encoder_type", "tiktoken"):
                result = count_tokens("Hello world")
                # Fallback to estimation
                assert result > 0


class TestReadFileMmap:
    """Test _read_file_mmap() optimized file reading."""

    def test_read_text_file(self, tmp_path):
        """Doc file text thanh cong."""
        f = tmp_path / "test.txt"
        f.write_text("Hello, world!")
        assert _read_file_mmap(f) == "Hello, world!"

    def test_read_empty_file(self, tmp_path):
        """Doc empty file tra ve empty string."""
        f = tmp_path / "empty.txt"
        f.write_text("")
        assert _read_file_mmap(f) == ""

    def test_read_unicode_file(self, tmp_path):
        """Doc file unicode (tieng Viet)."""
        f = tmp_path / "vn.txt"
        f.write_text("Xin chao the gioi!")
        content = _read_file_mmap(f)
        assert "Xin chao" in content

    def test_read_binary_content(self, tmp_path):
        """Doc file binary voi errors='replace'."""
        f = tmp_path / "binary.dat"
        f.write_bytes(b"\xff\xfe\x00\x01\x02")
        content = _read_file_mmap(f)
        assert content is not None

    def test_nonexistent_file_returns_none(self):
        """File khong ton tai tra ve None."""
        result = _read_file_mmap(Path("/nonexistent/file.txt"))
        assert result is None

    def test_multiline_file(self, tmp_path):
        """Doc file nhieu dong."""
        f = tmp_path / "multi.py"
        content = "line1\nline2\nline3\n"
        f.write_text(content)
        assert _read_file_mmap(f) == content


class TestCountTokensForFileNoCache:
    """Test _count_tokens_for_file_no_cache() parallel-safe counting."""

    def setup_method(self):
        """Clear cache truoc moi test."""
        token_cache.clear()

    def test_nonexistent_file(self):
        """File khong ton tai tra ve 0."""
        assert _count_tokens_for_file_no_cache(Path("/nonexistent.py")) == 0

    def test_empty_file(self, tmp_path):
        """Empty file tra ve 0."""
        f = tmp_path / "empty.py"
        f.write_text("")
        assert _count_tokens_for_file_no_cache(f) == 0

    def test_text_file(self, tmp_path):
        """Text file tra ve positive count."""
        f = tmp_path / "test.py"
        f.write_text("def hello():\n    return 42\n")
        result = _count_tokens_for_file_no_cache(f)
        assert result > 0

    def test_binary_file_skipped(self, tmp_path):
        """Binary file tra ve 0."""
        f = tmp_path / "image.jpg"
        f.write_bytes(bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"\x00" * 100)
        assert _count_tokens_for_file_no_cache(f) == 0

    def test_large_file_skipped(self, tmp_path):
        """File > MAX_BYTES tra ve 0."""
        f = tmp_path / "large.txt"
        f.write_text("x" * (MAX_BYTES + 1))
        assert _count_tokens_for_file_no_cache(f) == 0

    def test_directory_returns_zero(self, tmp_path):
        """Directory path tra ve 0."""
        d = tmp_path / "subdir"
        d.mkdir()
        assert _count_tokens_for_file_no_cache(d) == 0


class TestCountTokensForFile:
    """Test count_tokens_for_file() voi cache."""

    def setup_method(self):
        """Clear cache truoc moi test."""
        token_cache.clear()

    def test_nonexistent_file(self):
        """File khong ton tai tra ve 0."""
        assert count_tokens_for_file(Path("/nonexistent.py")) == 0

    def test_text_file(self, tmp_path):
        """Text file tra ve positive count."""
        f = tmp_path / "test.py"
        f.write_text("print('hello world')")
        result = count_tokens_for_file(f)
        assert result > 0

    def test_caching_mtime_hit(self, tmp_path):
        """Ket qua duoc cache dua tren mtime."""
        f = tmp_path / "cached.py"
        f.write_text("x = 1")

        result1 = count_tokens_for_file(f)
        result2 = count_tokens_for_file(f)

        assert result1 == result2
        assert result1 > 0

    def test_cache_invalidation_on_mtime_change(self, tmp_path):
        """Cache bi invalidate khi file thay doi (mtime khac)."""
        f = tmp_path / "changing.py"
        f.write_text("x = 1")

        count_tokens_for_file(f)

        # Thay doi file noi dung (mtime thay doi)
        import time

        time.sleep(0.01)  # Dam bao mtime khac
        f.write_text("x = 1\n" * 100)

        # Ket qua moi phai khac
        new_result = count_tokens_for_file(f)
        assert new_result > 5  # Noi dung dai hon

    def test_empty_file_returns_zero(self, tmp_path):
        """Empty file tra ve 0."""
        f = tmp_path / "empty.py"
        f.write_text("")
        assert count_tokens_for_file(f) == 0

    def test_binary_file_returns_zero(self, tmp_path):
        """Binary file (JPEG magic) tra ve 0."""
        f = tmp_path / "img.jpg"
        f.write_bytes(bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"\x00" * 100)
        assert count_tokens_for_file(f) == 0

    def test_large_file_returns_zero(self, tmp_path):
        """File > 5MB tra ve 0."""
        f = tmp_path / "huge.txt"
        f.write_text("a" * (MAX_BYTES + 1))
        assert count_tokens_for_file(f) == 0


# ============================================================================
# BATCH MODULE TESTS
# ============================================================================


class TestGetWorkerCount:
    """Test get_worker_count() calculation."""

    def test_small_tasks(self):
        """It tasks -> 1 worker."""
        assert get_worker_count(1) == 1
        assert get_worker_count(50) == 1
        assert get_worker_count(99) == 1

    def test_medium_tasks(self):
        """100 tasks = 1 worker, 200 = 2."""
        assert get_worker_count(100) == 1
        assert get_worker_count(200) == 2

    def test_capped_by_cpu(self):
        """Bi gioi han boi so CPU cores."""
        cpu = os.cpu_count() or 4
        result = get_worker_count(100000)
        assert result <= cpu
        assert result >= 1

    def test_zero_tasks(self):
        """0 tasks -> 1 worker (minimum)."""
        assert get_worker_count(0) == 1


class TestCountTokensBatch:
    """Test count_tokens_batch() sequential processing."""

    def setup_method(self):
        """Clear cache va set counting flag."""
        token_cache.clear()

    def teardown_method(self):
        """Reset counting flag."""
        stop_token_counting()

    def test_empty_list(self):
        """Empty list tra ve empty dict."""
        start_token_counting()
        result = count_tokens_batch([])
        assert result == {}

    def test_returns_empty_when_cancelled(self, tmp_path):
        """Tra ve empty khi is_counting_tokens = False."""
        f = tmp_path / "test.py"
        f.write_text("hello world")

        stop_token_counting()
        result = count_tokens_batch([f])
        assert result == {}

    def test_counts_files(self, tmp_path):
        """Dem token cho nhieu files."""
        files = []
        for i in range(3):
            f = tmp_path / f"file{i}.py"
            f.write_text(f"# File {i}\nprint({i})")
            files.append(f)

        start_token_counting()
        result = count_tokens_batch(files)

        assert len(result) == 3
        assert all(isinstance(v, int) for v in result.values())
        assert all(v > 0 for v in result.values())

    def test_handles_mixed_files(self, tmp_path):
        """Xu ly mix: text, binary, nonexistent."""
        text_f = tmp_path / "text.py"
        text_f.write_text("print('hello')")

        bin_f = tmp_path / "img.jpg"
        bin_f.write_bytes(bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"\x00" * 100)

        none_f = tmp_path / "gone.py"

        start_token_counting()
        result = count_tokens_batch([text_f, bin_f, none_f])

        assert result[str(text_f)] > 0
        assert result[str(bin_f)] == 0
        assert result[str(none_f)] == 0


class TestCountTokensBatchParallel:
    """Test count_tokens_batch_parallel() ThreadPoolExecutor."""

    def setup_method(self):
        """Clear cache."""
        token_cache.clear()

    def teardown_method(self):
        """Reset flag."""
        stop_token_counting()

    def test_empty_list(self):
        """Empty list tra ve empty dict."""
        start_token_counting()
        result = count_tokens_batch_parallel([])
        assert result == {}

    def test_returns_empty_when_cancelled(self, tmp_path):
        """Tra ve empty khi cancelled."""
        f = tmp_path / "test.py"
        f.write_text("hello")

        stop_token_counting()
        result = count_tokens_batch_parallel([f])
        assert result == {}

    def test_parallel_counting(self, tmp_path):
        """Dem song song nhieu files."""
        files = []
        for i in range(10):
            f = tmp_path / f"file{i}.py"
            f.write_text(f"# File {i}\nx = {i}\nprint(x)\n")
            files.append(f)

        start_token_counting()
        result = count_tokens_batch_parallel(files, max_workers=2)

        assert len(result) == 10
        assert all(v >= 0 for v in result.values())
        # It nhat text files phai co tokens
        text_counts = [v for v in result.values() if v > 0]
        assert len(text_counts) == 10

    def test_updates_cache(self, tmp_path):
        """Ket qua duoc luu vao token_cache."""
        f = tmp_path / "cached.py"
        f.write_text("x = 42")
        mtime = f.stat().st_mtime

        start_token_counting()
        count_tokens_batch_parallel([f], update_cache=True)

        # Kiem tra cache
        cached = token_cache.get(str(f), mtime)
        assert cached is not None
        assert cached > 0

    def test_auto_detects_hf(self, tmp_path):
        """Auto-detect HF tokenizer khi co tokenizer_repo."""
        f = tmp_path / "test.py"
        f.write_text("hello")

        start_token_counting()

        with patch(
            "core.tokenization.batch.get_tokenizer_repo", return_value="test/repo"
        ):
            with patch("core.tokenization.batch.HAS_TOKENIZERS", True):
                with patch("core.tokenization.batch.count_tokens_batch_hf") as mock_hf:
                    mock_hf.return_value = {str(f): 1}
                    count_tokens_batch_parallel([f])
                    mock_hf.assert_called_once()


class TestConstants:
    """Test cac constants duoc export dung."""

    def test_max_bytes(self):
        """MAX_BYTES = 5MB."""
        assert MAX_BYTES == 5 * 1024 * 1024

    def test_tasks_per_worker(self):
        """TASKS_PER_WORKER = 100."""
        assert TASKS_PER_WORKER == 100

    def test_min_files_for_parallel(self):
        """MIN_FILES_FOR_PARALLEL = 10."""
        assert MIN_FILES_FOR_PARALLEL == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
