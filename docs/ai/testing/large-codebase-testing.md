---
phase: testing
title: Testing Strategy for Large Codebase Features
description: Comprehensive testing approach for new features and improvements
---

# Testing Strategy: Large Codebase Features

## Overview

This document outlines the testing strategy for all proposed features, including unit tests, integration tests, performance tests, and error scenario tests.

## Testing Priorities

### P0 (Critical) - Must Pass
- Data integrity (no file corruption/loss)
- Backup and restore operations
- OPX parsing correctness
- Memory leak prevention

### P1 (High) - Should Pass
- Performance targets met
- Cache invalidation works
- Error recovery mechanisms
- UI responsiveness

### P2 (Medium) - Nice to Have
- Edge case handling
- Cross-platform compatibility
- Accessibility features

## Test Coverage Goals

| Component | Target Coverage | Current | Gap |
|-----------|----------------|---------|-----|
| Token Cache | 90% | 0% | New feature |
| Operations Executor | 95% | 0% | New feature |
| Tree Loader | 85% | ~60% | Enhancement |
| Selection Groups | 90% | 0% | New feature |
| Smart Selection | 85% | 0% | New feature |
| OPX Parser | 95% | ~80% | Improvements |

**Overall Target: 90% coverage for new code**

## Unit Tests

### Token Cache Tests (`tests/test_token_cache.py`)

```python
"""Unit tests for TokenCacheManager"""

import pytest
from pathlib import Path
import tempfile
import time

from services.token_cache import TokenCacheManager, CacheEntry


class TestTokenCache:
    """Test suite for token cache functionality"""
    
    @pytest.fixture
    def cache_dir(self):
        """Create temporary cache directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def cache(self, cache_dir):
        """Create cache manager instance"""
        return TokenCacheManager(cache_dir, max_size_mb=1)
    
    @pytest.fixture
    def test_file(self):
        """Create temporary test file"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            path = Path(f.name)
        yield path
        path.unlink()
    
    def test_cache_miss_returns_none(self, cache, test_file):
        """Test that cache miss returns None"""
        result = cache.get(test_file)
        assert result is None
    
    def test_cache_hit_returns_stored_value(self, cache, test_file):
        """Test that cached value is returned"""
        # Store value
        cache.set(test_file, 100)
        
        # Retrieve value
        result = cache.get(test_file)
        
        assert result == 100
    
    def test_cache_invalidates_on_file_change(self, cache, test_file):
        """Test that cache invalidates when file changes"""
        # Store value
        cache.set(test_file, 100)
        
        # Modify file
        time.sleep(0.1)  # Ensure mtime changes
        test_file.write_text("new content")
        
        # Should be cache miss
        result = cache.get(test_file)
        
        assert result is None
    
    def test_cache_invalidate_removes_entry(self, cache, test_file):
        """Test manual cache invalidation"""
        # Store value
        cache.set(test_file, 100)
        
        # Invalidate
        cache.invalidate(test_file)
        
        # Should be cache miss
        result = cache.get(test_file)
        
        assert result is None
    
    def test_cache_clear_removes_all(self, cache, test_file):
        """Test that clear removes all entries"""
        # Store multiple values
        cache.set(test_file, 100)
        
        # Clear cache
        cache.clear()
        
        # Check all cleared
        result = cache.get(test_file)
        assert result is None
        
        stats = cache.get_stats()
        assert stats['entry_count'] == 0
    
    def test_cache_stats_accuracy(self, cache, test_file):
        """Test that cache statistics are accurate"""
        # Initial stats
        stats = cache.get_stats()
        assert stats['entry_count'] == 0
        assert stats['hits'] == 0
        assert stats['misses'] == 0
        
        # Add entry and check
        cache.set(test_file, 100)
        cache.get(test_file)  # Hit
        cache.get(Path("nonexistent"))  # Miss
        
        stats = cache.get_stats()
        assert stats['entry_count'] == 1
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate'] == 50.0
    
    def test_cache_size_management(self, cache, test_file):
        """Test that cache respects size limits"""
        # Fill cache beyond limit
        for i in range(100):
            cache.set(test_file, i)
        
        # Check size stayed under limit
        stats = cache.get_stats()
        assert stats['size_mb'] <= 1.0
    
    def test_json_fallback_works(self, cache_dir):
        """Test JSON fallback when SQLite unavailable"""
        # Force JSON mode
        cache = TokenCacheManager(cache_dir)
        cache._use_sqlite = False
        
        # Test basic operations
        test_file = Path("test.txt")
        cache.set(test_file, 100)
        result = cache.get(test_file)
        
        assert result == 100


class TestTokenCacheIntegration:
    """Integration tests with token counter"""
    
    def test_cache_integration_with_counter(self, cache_dir, test_file):
        """Test cache integrates with token counter"""
        from core.token_counter import count_tokens
        from services.token_cache import get_token_cache
        
        # First count (cache miss)
        count1 = count_tokens(test_file)
        
        # Second count (should be cache hit)
        count2 = count_tokens(test_file)
        
        assert count1 == count2
        
        # Check cache was used
        cache = get_token_cache()
        stats = cache.get_stats()
        assert stats['hits'] >= 1
```

### Partial Operations Tests (`tests/test_operations_executor.py`)

```python
"""Unit tests for PartialOperationsExecutor"""

import pytest
from pathlib import Path
import tempfile

from services.operations_executor import PartialOperationsExecutor, OperationResult
from core.opx_parser import FileAction, ChangeBlock


class TestPartialOperationsExecutor:
    """Test suite for operations executor"""
    
    @pytest.fixture
    def workspace(self):
        """Create temporary workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def backup_dir(self):
        """Create temporary backup directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def executor(self, workspace, backup_dir):
        """Create executor instance"""
        return PartialOperationsExecutor(workspace, backup_dir)
    
    def test_successful_create_operation(self, executor, workspace):
        """Test successful file creation"""
        action = FileAction(
            path="test.txt",
            action="create",
            changes=[ChangeBlock(
                description="Create test file",
                content="Hello, World!"
            )]
        )
        
        results = executor.execute_operations([action])
        
        assert len(results) == 1
        assert results[0].success is True
        assert (workspace / "test.txt").exists()
        assert (workspace / "test.txt").read_text() == "Hello, World!"
    
    def test_failed_operation_does_not_stop_others(self, executor, workspace):
        """Test that one failure doesn't stop other operations"""
        actions = [
            FileAction(path="test1.txt", action="create", changes=[
                ChangeBlock(description="Create", content="Content 1")
            ]),
            FileAction(path="/invalid/path/test2.txt", action="create", changes=[
                ChangeBlock(description="Create", content="Content 2")
            ]),
            FileAction(path="test3.txt", action="create", changes=[
                ChangeBlock(description="Create", content="Content 3")
            ]),
        ]
        
        results = executor.execute_operations(actions)
        
        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is True
        
        # Check files created
        assert (workspace / "test1.txt").exists()
        assert not (workspace / "test2.txt").exists()
        assert (workspace / "test3.txt").exists()
    
    def test_backup_created_before_modify(self, executor, workspace, backup_dir):
        """Test that backup is created before modification"""
        # Create initial file
        test_file = workspace / "test.txt"
        test_file.write_text("Original content")
        
        action = FileAction(
            path="test.txt",
            action="modify",
            changes=[ChangeBlock(
                description="Modify",
                search="Original",
                content="Modified"
            )]
        )
        
        results = executor.execute_operations([action])
        
        assert results[0].success is True
        assert results[0].backup_path is not None
        
        # Check backup exists
        backup_path = Path(results[0].backup_path)
        assert backup_path.exists()
        assert backup_path.read_text() == "Original content"
    
    def test_rollback_on_failure(self, executor, workspace):
        """Test that file is restored on operation failure"""
        # Create initial file
        test_file = workspace / "test.txt"
        test_file.write_text("Original content")
        
        # Create action that will fail
        action = FileAction(
            path="test.txt",
            action="modify",
            changes=[ChangeBlock(
                description="Modify",
                search="NonexistentText",  # Won't match
                content="Modified"
            )]
        )
        
        results = executor.execute_operations([action])
        
        assert results[0].success is False
        
        # File should still have original content
        assert test_file.read_text() == "Original content"
    
    def test_progress_callback(self, executor, workspace):
        """Test that progress callback is called"""
        actions = [
            FileAction(path=f"test{i}.txt", action="create", changes=[
                ChangeBlock(description="Create", content=f"Content {i}")
            ])
            for i in range(3)
        ]
        
        progress_calls = []
        
        def on_progress(completed, total, result):
            progress_calls.append((completed, total, result.success))
        
        results = executor.execute_operations(actions, on_progress)
        
        assert len(progress_calls) == 3
        assert progress_calls[0] == (1, 3, True)
        assert progress_calls[1] == (2, 3, True)
        assert progress_calls[2] == (3, 3, True)
    
    def test_retry_on_permission_error(self, executor, workspace, monkeypatch):
        """Test retry logic for permission errors"""
        # This is a simplified test - real test would need OS-level permissions
        attempt_count = 0
        
        def mock_operation(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise PermissionError("Access denied")
            # Succeed on second attempt
        
        # Would need proper mocking here
        pass  # Placeholder for complex retry test
```

## Integration Tests

### End-to-End Workflow Tests (`tests/test_e2e_workflows.py`)

```python
"""End-to-end workflow tests"""

import pytest
from pathlib import Path
import tempfile

from core.file_utils import scan_directory
from core.token_counter import count_tokens
from core.opx_parser import parse_opx_response
from services.operations_executor import PartialOperationsExecutor


class TestEndToEndWorkflows:
    """Test complete user workflows"""
    
    @pytest.fixture
    def project_dir(self):
        """Create test project structure"""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            
            # Create project structure
            (base / "src").mkdir()
            (base / "src" / "main.py").write_text("print('Hello')")
            (base / "src" / "utils.py").write_text("def helper(): pass")
            (base / "tests").mkdir()
            (base / "tests" / "test_main.py").write_text("def test(): pass")
            (base / ".gitignore").write_text("__pycache__\n*.pyc\n")
            
            yield base
    
    def test_full_context_generation_workflow(self, project_dir):
        """Test complete context generation workflow"""
        # 1. Scan directory
        tree = scan_directory(project_dir)
        assert tree is not None
        
        # 2. Count tokens for files
        files = [
            project_dir / "src" / "main.py",
            project_dir / "src" / "utils.py",
        ]
        
        total_tokens = 0
        for file_path in files:
            count = count_tokens(file_path)
            assert count > 0
            total_tokens += count
        
        assert total_tokens > 0
    
    def test_full_opx_application_workflow(self, project_dir):
        """Test complete OPX application workflow"""
        # 1. Parse OPX
        opx_content = """
        <opx>
            <edit file="src/new_file.py" op="new">
                <why>Create new module</why>
                <put>
<<<
def new_function():
    return "Hello"
>>>
                </put>
            </edit>
        </opx>
        """
        
        result = parse_opx_response(opx_content)
        assert len(result.file_actions) == 1
        assert len(result.errors) == 0
        
        # 2. Execute operations
        backup_dir = project_dir / ".backups"
        executor = PartialOperationsExecutor(project_dir, backup_dir)
        
        results = executor.execute_operations(result.file_actions)
        
        assert len(results) == 1
        assert results[0].success is True
        
        # 3. Verify file created
        new_file = project_dir / "src" / "new_file.py"
        assert new_file.exists()
        assert "new_function" in new_file.read_text()
```

## Performance Tests

### Large Project Tests (`tests/test_performance.py`)

```python
"""Performance tests for large codebases"""

import pytest
import time
from pathlib import Path
import tempfile

from core.file_utils import scan_directory
from services.token_cache import TokenCacheManager


class TestPerformance:
    """Performance benchmark tests"""
    
    @pytest.fixture
    def large_project(self):
        """Create large test project (1000 files)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            
            # Create 1000 files
            for i in range(1000):
                folder = base / f"folder_{i // 100}"
                folder.mkdir(exist_ok=True)
                
                file_path = folder / f"file_{i}.py"
                file_path.write_text(f"# File {i}\nprint('test')")
            
            yield base
    
    def test_tree_scan_performance(self, large_project):
        """Test tree scanning performance"""
        start = time.time()
        tree = scan_directory(large_project)
        duration = time.time() - start
        
        assert tree is not None
        assert duration < 5.0, f"Tree scan took {duration}s (limit: 5s)"
    
    def test_token_cache_performance(self):
        """Test cache lookup performance"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = TokenCacheManager(cache_dir)
            
            # Add 1000 entries
            files = [Path(f"test_{i}.py") for i in range(1000)]
            
            for file_path in files:
                cache.set(file_path, 100)
            
            # Measure lookup time
            start = time.time()
            for file_path in files:
                cache.get(file_path)
            duration = time.time() - start
            
            avg_lookup = duration / len(files) * 1000  # ms
            assert avg_lookup < 1.0, f"Avg lookup: {avg_lookup}ms (limit: 1ms)"
    
    def test_memory_usage_stays_bounded(self, large_project):
        """Test that memory usage doesn't grow unbounded"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Baseline memory
        baseline_mb = process.memory_info().rss / (1024 * 1024)
        
        # Perform operations
        for _ in range(10):
            tree = scan_directory(large_project)
        
        # Check memory
        current_mb = process.memory_info().rss / (1024 * 1024)
        increase = current_mb - baseline_mb
        
        assert increase < 100, f"Memory increased by {increase}MB (limit: 100MB)"
```

## Error Scenario Tests

### Failure Mode Tests (`tests/test_error_scenarios.py`)

```python
"""Tests for error scenarios and fallback mechanisms"""

import pytest
from pathlib import Path
import tempfile

from core.opx_parser import parse_opx_response
from services.token_cache import TokenCacheManager


class TestErrorScenarios:
    """Test error handling and fallbacks"""
    
    def test_malformed_opx_returns_partial_results(self):
        """Test that parser returns partial results on errors"""
        opx_content = """
        <opx>
            <edit file="test1.py" op="new">
                <put><<<content1>>></put>
            </edit>
            
            <edit file="test2.py">
                <!-- Missing op attribute -->
                <put><<<content2>>></put>
            </edit>
            
            <edit file="test3.py" op="new">
                <put><<<content3>>></put>
            </edit>
        </opx>
        """
        
        result = parse_opx_response(opx_content)
        
        # Should get 2 valid actions + 1 error
        assert len(result.file_actions) == 2
        assert len(result.errors) == 1
        
        # Valid actions should be parseable
        assert result.file_actions[0].path == "test1.py"
        assert result.file_actions[1].path == "test3.py"
    
    def test_cache_handles_corrupted_database(self):
        """Test cache fallback when database is corrupted"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            
            # Create corrupted database
            db_path = cache_dir / "token_cache.db"
            db_path.write_text("corrupted data")
            
            # Cache should initialize with fallback
            cache = TokenCacheManager(cache_dir)
            
            # Should still work (JSON fallback)
            test_file = Path("test.py")
            cache.set(test_file, 100)
            result = cache.get(test_file)
            
            # JSON fallback should work
            assert cache._use_sqlite is False
    
    def test_permission_error_on_backup_aborts_operation(self):
        """Test that backup failure aborts operation safely"""
        # Would need OS-level permission manipulation
        # Placeholder for complex permission test
        pass
    
    def test_disk_full_scenario(self):
        """Test behavior when disk is full"""
        # Difficult to test without actual disk manipulation
        # Would use mock/patch in real implementation
        pass
```

## Test Execution

### Run All Tests
```bash
# Run all tests with coverage
pytest tests/ -v --cov=services --cov=core --cov-report=html

# Run specific test suites
pytest tests/test_token_cache.py -v
pytest tests/test_operations_executor.py -v
pytest tests/test_performance.py -v

# Run with markers
pytest -m "unit" tests/
pytest -m "integration" tests/
pytest -m "performance" tests/
```

### Continuous Integration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
      - name: Run tests
        run: pytest tests/ -v --cov=services --cov=core
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Test Data

### Sample Projects for Testing

Create test data in `tests/fixtures/`:

```
fixtures/
├── small_project/      # 10 files
├── medium_project/     # 100 files
├── large_project/      # 1000 files
└── malformed_opx/      # Various OPX test cases
```

## Success Criteria

### Phase 1: Foundation
- ✅ Token cache: 90% coverage, < 1ms lookups
- ✅ Partial operations: 95% coverage, independent execution verified
- ✅ OPX parser: Handles all malformed cases gracefully

### Phase 2: Performance
- ✅ Tree loading: < 1s for 10,000 files
- ✅ Memory: Stays under 300MB for large projects
- ✅ No memory leaks in 1000 operations

### Phase 3: Usability
- ✅ Selection groups: CRUD operations work
- ✅ Smart selection: Pattern matching accurate
- ✅ UI: No freezes during operations

## Coverage Reports

Generate and review coverage reports:

```bash
# Generate HTML report
pytest --cov=services --cov=core --cov-report=html

# Open report
open htmlcov/index.html

# Check for uncovered lines
pytest --cov=services --cov=core --cov-report=term-missing
```

## Performance Benchmarking

Track performance metrics over time:

```python
# tests/benchmarks.py
import pytest

@pytest.mark.benchmark
def test_token_cache_lookup_benchmark(benchmark):
    """Benchmark cache lookup performance"""
    cache = TokenCacheManager(...)
    result = benchmark(cache.get, test_file)
    
    # Assert benchmark results
    assert result is not None
```

## Next Steps

1. Implement unit tests for TokenCacheManager
2. Implement integration tests for full workflows
3. Run performance benchmarks on large projects
4. Set up CI/CD pipeline
5. Track coverage metrics
6. Document test results
