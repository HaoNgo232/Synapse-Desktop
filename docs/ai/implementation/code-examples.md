---
phase: implementation
title: Implementation Guide - Large Codebase Features
description: Detailed implementation guide with code examples and patterns
---

# Implementation Guide: Large Codebase Features

## Overview

This guide provides detailed implementation instructions, code examples, and best practices for each feature. Follow these guidelines to ensure consistency and quality.

## Token Cache Implementation

### File: `services/token_cache.py`

```python
"""
Token Cache Service - Persistent caching for token counts

Features:
- SQLite storage for fast lookups
- Content hash-based invalidation
- Automatic size management
- JSON fallback when SQLite unavailable
"""

import sqlite3
import json
import hashlib
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

from core.logging_config import log_info, log_error, log_debug


@dataclass
class CacheEntry:
    """Token cache entry"""
    file_path: str
    content_hash: str
    token_count: int
    last_updated: float
    encoding_model: str
    file_size: int
    mtime: float


class TokenCacheManager:
    """Manage persistent token count cache"""
    
    def __init__(self, cache_dir: Path, max_size_mb: int = 100):
        """
        Initialize cache manager.
        
        Args:
            cache_dir: Directory to store cache
            max_size_mb: Maximum cache size in megabytes
        """
        self._cache_dir = cache_dir
        self._max_size = max_size_mb
        self._db_path = cache_dir / "token_cache.db"
        self._use_sqlite = True
        self._json_path = cache_dir / "token_cache.json"
        
        # Statistics
        self._hits = 0
        self._misses = 0
        
        # Initialize storage
        self._init_storage()
    
    def _init_storage(self):
        """Initialize storage backend (SQLite or JSON fallback)"""
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._init_sqlite()
            log_info("Token cache initialized with SQLite")
        except Exception as e:
            log_error(f"Failed to initialize SQLite cache: {e}")
            self._use_sqlite = False
            self._init_json()
            log_info("Token cache fallback to JSON")
    
    def _init_sqlite(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        # Create table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_cache (
                file_path TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                token_count INTEGER NOT NULL,
                last_updated REAL NOT NULL,
                encoding_model TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                mtime REAL NOT NULL
            )
        """)
        
        # Create indices
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_last_updated 
            ON token_cache(last_updated)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_content_hash 
            ON token_cache(content_hash)
        """)
        
        conn.commit()
        conn.close()
    
    def _init_json(self):
        """Initialize JSON fallback storage"""
        if not self._json_path.exists():
            self._json_path.write_text("{}", encoding="utf-8")
    
    def get(self, file_path: Path, encoding_model: str = "cl100k_base") -> Optional[int]:
        """
        Get cached token count if valid.
        
        Args:
            file_path: Path to file
            encoding_model: Token encoding model
            
        Returns:
            Cached token count or None if invalid/missing
        """
        try:
            # Check file exists and get metadata
            if not file_path.exists():
                return None
            
            stat = file_path.stat()
            current_mtime = stat.st_mtime
            current_size = stat.st_size
            
            # Get from storage
            entry = self._get_entry(str(file_path))
            
            if entry is None:
                self._misses += 1
                return None
            
            # Validate entry
            if (entry.mtime != current_mtime or 
                entry.file_size != current_size or
                entry.encoding_model != encoding_model):
                # File changed, invalidate
                self.invalidate(file_path)
                self._misses += 1
                return None
            
            self._hits += 1
            log_debug(f"Cache hit: {file_path.name}")
            return entry.token_count
            
        except Exception as e:
            log_error(f"Error reading cache: {e}")
            return None
    
    def set(
        self, 
        file_path: Path, 
        token_count: int, 
        encoding_model: str = "cl100k_base"
    ):
        """
        Store token count in cache.
        
        Args:
            file_path: Path to file
            token_count: Number of tokens
            encoding_model: Token encoding model
        """
        try:
            if not file_path.exists():
                return
            
            stat = file_path.stat()
            
            # Calculate content hash for additional validation
            content_hash = self._calculate_hash(file_path)
            
            entry = CacheEntry(
                file_path=str(file_path),
                content_hash=content_hash,
                token_count=token_count,
                last_updated=datetime.now().timestamp(),
                encoding_model=encoding_model,
                file_size=stat.st_size,
                mtime=stat.st_mtime
            )
            
            self._set_entry(entry)
            
            # Check size and cleanup if needed
            self._maybe_cleanup()
            
        except Exception as e:
            log_error(f"Error writing cache: {e}")
    
    def invalidate(self, file_path: Path):
        """Remove entry from cache"""
        try:
            self._delete_entry(str(file_path))
        except Exception as e:
            log_error(f"Error invalidating cache: {e}")
    
    def clear(self):
        """Clear all cache entries"""
        try:
            if self._use_sqlite:
                conn = sqlite3.connect(str(self._db_path))
                cursor = conn.cursor()
                cursor.execute("DELETE FROM token_cache")
                conn.commit()
                conn.close()
            else:
                self._json_path.write_text("{}", encoding="utf-8")
            
            self._hits = 0
            self._misses = 0
            log_info("Token cache cleared")
            
        except Exception as e:
            log_error(f"Error clearing cache: {e}")
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
        
        entry_count = self._get_entry_count()
        size_mb = self._get_cache_size_mb()
        
        return {
            "entry_count": entry_count,
            "size_mb": round(size_mb, 2),
            "hit_rate": round(hit_rate, 1),
            "hits": self._hits,
            "misses": self._misses,
        }
    
    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file content"""
        sha256 = hashlib.sha256()
        
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception:
            # Fallback to file size + mtime
            stat = file_path.stat()
            return f"{stat.st_size}:{stat.st_mtime}"
    
    # Storage backend implementations
    
    def _get_entry(self, file_path: str) -> Optional[CacheEntry]:
        """Get entry from storage"""
        if self._use_sqlite:
            return self._get_entry_sqlite(file_path)
        else:
            return self._get_entry_json(file_path)
    
    def _set_entry(self, entry: CacheEntry):
        """Set entry in storage"""
        if self._use_sqlite:
            self._set_entry_sqlite(entry)
        else:
            self._set_entry_json(entry)
    
    def _delete_entry(self, file_path: str):
        """Delete entry from storage"""
        if self._use_sqlite:
            self._delete_entry_sqlite(file_path)
        else:
            self._delete_entry_json(file_path)
    
    def _get_entry_sqlite(self, file_path: str) -> Optional[CacheEntry]:
        """Get entry from SQLite"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM token_cache WHERE file_path = ?",
            (file_path,)
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if row is None:
            return None
        
        return CacheEntry(
            file_path=row[0],
            content_hash=row[1],
            token_count=row[2],
            last_updated=row[3],
            encoding_model=row[4],
            file_size=row[5],
            mtime=row[6]
        )
    
    def _set_entry_sqlite(self, entry: CacheEntry):
        """Set entry in SQLite"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO token_cache 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.file_path,
            entry.content_hash,
            entry.token_count,
            entry.last_updated,
            entry.encoding_model,
            entry.file_size,
            entry.mtime
        ))
        
        conn.commit()
        conn.close()
    
    def _delete_entry_sqlite(self, file_path: str):
        """Delete entry from SQLite"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM token_cache WHERE file_path = ?", (file_path,))
        conn.commit()
        conn.close()
    
    def _get_entry_json(self, file_path: str) -> Optional[CacheEntry]:
        """Get entry from JSON"""
        try:
            data = json.loads(self._json_path.read_text(encoding="utf-8"))
            entry_dict = data.get(file_path)
            
            if entry_dict is None:
                return None
            
            return CacheEntry(**entry_dict)
        except Exception:
            return None
    
    def _set_entry_json(self, entry: CacheEntry):
        """Set entry in JSON"""
        try:
            data = json.loads(self._json_path.read_text(encoding="utf-8"))
            data[entry.file_path] = {
                "file_path": entry.file_path,
                "content_hash": entry.content_hash,
                "token_count": entry.token_count,
                "last_updated": entry.last_updated,
                "encoding_model": entry.encoding_model,
                "file_size": entry.file_size,
                "mtime": entry.mtime
            }
            self._json_path.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            log_error(f"Error writing JSON cache: {e}")
    
    def _delete_entry_json(self, file_path: str):
        """Delete entry from JSON"""
        try:
            data = json.loads(self._json_path.read_text(encoding="utf-8"))
            data.pop(file_path, None)
            self._json_path.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass
    
    def _get_entry_count(self) -> int:
        """Get total number of cache entries"""
        if self._use_sqlite:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM token_cache")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        else:
            try:
                data = json.loads(self._json_path.read_text(encoding="utf-8"))
                return len(data)
            except Exception:
                return 0
    
    def _get_cache_size_mb(self) -> float:
        """Get cache size in megabytes"""
        try:
            if self._use_sqlite:
                size_bytes = self._db_path.stat().st_size
            else:
                size_bytes = self._json_path.stat().st_size
            
            return size_bytes / (1024 * 1024)
        except Exception:
            return 0.0
    
    def _maybe_cleanup(self):
        """Cleanup old entries if cache too large"""
        size_mb = self._get_cache_size_mb()
        
        if size_mb > self._max_size:
            log_info(f"Cache size {size_mb}MB exceeds limit {self._max_size}MB, cleaning up")
            self._cleanup_old_entries()
    
    def _cleanup_old_entries(self):
        """Remove oldest entries to reduce cache size"""
        if self._use_sqlite:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            
            # Keep only 50% of entries (oldest removed)
            cursor.execute("""
                DELETE FROM token_cache 
                WHERE file_path IN (
                    SELECT file_path FROM token_cache 
                    ORDER BY last_updated ASC 
                    LIMIT (SELECT COUNT(*) / 2 FROM token_cache)
                )
            """)
            
            conn.commit()
            conn.close()
        else:
            # JSON fallback: keep newest 50%
            try:
                data = json.loads(self._json_path.read_text(encoding="utf-8"))
                
                # Sort by last_updated
                sorted_entries = sorted(
                    data.items(),
                    key=lambda x: x[1].get("last_updated", 0),
                    reverse=True
                )
                
                # Keep top 50%
                keep_count = len(sorted_entries) // 2
                new_data = dict(sorted_entries[:keep_count])
                
                self._json_path.write_text(
                    json.dumps(new_data, indent=2),
                    encoding="utf-8"
                )
            except Exception as e:
                log_error(f"Error cleaning up JSON cache: {e}")


# Singleton instance
_cache_manager: Optional[TokenCacheManager] = None


def get_token_cache() -> TokenCacheManager:
    """Get singleton token cache instance"""
    global _cache_manager
    
    if _cache_manager is None:
        cache_dir = Path.home() / ".overwrite-desktop" / "cache"
        _cache_manager = TokenCacheManager(cache_dir)
    
    return _cache_manager
```

### Integration with Token Counter

Update `core/token_counter.py`:

```python
from services.token_cache import get_token_cache

def count_tokens(file_path: Path, encoding_name: str = "cl100k_base") -> int:
    """
    Count tokens in file with caching.
    
    Args:
        file_path: Path to file
        encoding_name: Token encoding model
        
    Returns:
        Number of tokens
    """
    # Try cache first
    cache = get_token_cache()
    cached_count = cache.get(file_path, encoding_name)
    
    if cached_count is not None:
        return cached_count
    
    # Cache miss - count tokens
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        
        # Use tiktoken
        import tiktoken
        encoding = tiktoken.get_encoding(encoding_name)
        count = len(encoding.encode(content))
        
        # Store in cache
        cache.set(file_path, count, encoding_name)
        
        return count
        
    except Exception as e:
        log_error(f"Error counting tokens for {file_path}: {e}")
        # Fallback: estimate tokens as words
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            return len(content.split())
        except Exception:
            return 0
```

## Partial Operations Executor

### File: `services/operations_executor.py`

```python
"""
Partial Operations Executor - Execute file operations independently

Features:
- Independent execution (no all-or-nothing)
- Automatic backup before changes
- Retry logic with exponential backoff
- Detailed per-operation reporting
"""

import time
from pathlib import Path
from typing import Callable, Optional
from dataclasses import dataclass
from datetime import datetime

from core.file_actions import (
    apply_file_action,
    create_backup,
    restore_backup,
)
from core.opx_parser import FileAction
from core.logging_config import log_info, log_error, log_warning


@dataclass
class OperationResult:
    """Result of single file operation"""
    file_path: str
    action: str
    success: bool
    message: str
    duration_ms: float
    backup_path: Optional[str] = None
    attempt_count: int = 1


class PartialOperationsExecutor:
    """Execute file operations independently with retry logic"""
    
    def __init__(
        self,
        workspace_path: Path,
        backup_dir: Path,
        max_retries: int = 3
    ):
        """
        Initialize executor.
        
        Args:
            workspace_path: Workspace root path
            backup_dir: Directory for backups
            max_retries: Maximum retry attempts for transient errors
        """
        self._workspace = workspace_path
        self._backup_dir = backup_dir
        self._max_retries = max_retries
        
        # Ensure backup directory exists
        self._backup_dir.mkdir(parents=True, exist_ok=True)
    
    def execute_operations(
        self,
        file_actions: list[FileAction],
        on_progress: Optional[Callable[[int, int, OperationResult], None]] = None
    ) -> list[OperationResult]:
        """
        Execute file operations independently.
        
        Args:
            file_actions: List of parsed file operations
            on_progress: Callback(completed, total, latest_result)
            
        Returns:
            List of operation results (both success and failures)
        """
        results = []
        total = len(file_actions)
        
        log_info(f"Executing {total} file operations")
        
        for idx, action in enumerate(file_actions, start=1):
            result = self._execute_single(action)
            results.append(result)
            
            if on_progress:
                on_progress(idx, total, result)
            
            # Log result
            if result.success:
                log_info(f"✓ {result.action} {result.file_path} ({result.duration_ms:.0f}ms)")
            else:
                log_error(f"✗ {result.action} {result.file_path}: {result.message}")
        
        # Summary
        success_count = sum(1 for r in results if r.success)
        fail_count = total - success_count
        log_info(f"Operations complete: {success_count} success, {fail_count} failed")
        
        return results
    
    def _execute_single(self, action: FileAction) -> OperationResult:
        """
        Execute single file operation with retry logic.
        
        Args:
            action: File action to execute
            
        Returns:
            Operation result
        """
        start_time = time.time()
        file_path = self._workspace / action.path
        backup_path = None
        
        # Create backup for destructive operations
        if action.action in ("modify", "delete", "rename", "rewrite"):
            if file_path.exists():
                try:
                    backup_path = str(create_backup(file_path, self._backup_dir))
                except Exception as e:
                    # Backup failure is critical - abort operation
                    duration = (time.time() - start_time) * 1000
                    return OperationResult(
                        file_path=action.path,
                        action=action.action,
                        success=False,
                        message=f"Backup failed: {e}",
                        duration_ms=duration,
                        backup_path=None,
                        attempt_count=0
                    )
        
        # Try operation with retries
        last_error = None
        
        for attempt in range(1, self._max_retries + 1):
            try:
                # Execute the operation
                apply_file_action(self._workspace, action)
                
                duration = (time.time() - start_time) * 1000
                
                return OperationResult(
                    file_path=action.path,
                    action=action.action,
                    success=True,
                    message="Success",
                    duration_ms=duration,
                    backup_path=backup_path,
                    attempt_count=attempt
                )
                
            except PermissionError as e:
                last_error = e
                
                if attempt < self._max_retries:
                    # Wait with exponential backoff
                    wait_time = 0.1 * (2 ** (attempt - 1))
                    log_warning(f"Permission error, retry {attempt}/{self._max_retries} after {wait_time}s")
                    time.sleep(wait_time)
                else:
                    # Final attempt failed - restore backup
                    if backup_path:
                        try:
                            restore_backup(Path(backup_path), file_path)
                        except Exception as restore_error:
                            log_error(f"Failed to restore backup: {restore_error}")
                    
                    duration = (time.time() - start_time) * 1000
                    return OperationResult(
                        file_path=action.path,
                        action=action.action,
                        success=False,
                        message=f"Permission denied after {attempt} attempts: {e}",
                        duration_ms=duration,
                        backup_path=backup_path,
                        attempt_count=attempt
                    )
                    
            except FileNotFoundError as e:
                # Don't retry for not found errors
                last_error = e
                
                if backup_path:
                    try:
                        restore_backup(Path(backup_path), file_path)
                    except Exception:
                        pass
                
                duration = (time.time() - start_time) * 1000
                return OperationResult(
                    file_path=action.path,
                    action=action.action,
                    success=False,
                    message=f"File not found: {e}",
                    duration_ms=duration,
                    backup_path=backup_path,
                    attempt_count=attempt
                )
                
            except Exception as e:
                # Other errors - restore backup and fail
                last_error = e
                
                if backup_path:
                    try:
                        restore_backup(Path(backup_path), file_path)
                    except Exception as restore_error:
                        log_error(f"Failed to restore backup: {restore_error}")
                
                duration = (time.time() - start_time) * 1000
                return OperationResult(
                    file_path=action.path,
                    action=action.action,
                    success=False,
                    message=f"Operation failed: {e}",
                    duration_ms=duration,
                    backup_path=backup_path,
                    attempt_count=attempt
                )
        
        # Should not reach here, but handle gracefully
        duration = (time.time() - start_time) * 1000
        return OperationResult(
            file_path=action.path,
            action=action.action,
            success=False,
            message=f"Unexpected error: {last_error}",
            duration_ms=duration,
            backup_path=backup_path,
            attempt_count=self._max_retries
        )
```

## Best Practices

### Error Handling Pattern

Always use fallback chains:

```python
def robust_operation():
    """Example of robust error handling with fallbacks"""
    try:
        # Try primary method
        return primary_method()
    except SpecificError as e:
        log_warning(f"Primary method failed: {e}, trying fallback")
        try:
            # Try fallback method
            return fallback_method()
        except Exception as e2:
            log_error(f"Fallback also failed: {e2}")
            # Return safe default
            return safe_default_value()
```

### Performance Monitoring

Wrap performance-critical code:

```python
import time

def measure_performance(operation_name: str):
    """Decorator to measure operation performance"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                log_info(f"{operation_name} completed in {duration:.0f}ms")
                return result
            except Exception as e:
                duration = (time.time() - start) * 1000
                log_error(f"{operation_name} failed after {duration:.0f}ms: {e}")
                raise
        return wrapper
    return decorator

@measure_performance("token_count")
def count_tokens_with_monitoring(file_path: Path) -> int:
    return count_tokens(file_path)
```

### Resource Cleanup

Always use context managers:

```python
class ManagedResource:
    """Example of proper resource management"""
    
    def __enter__(self):
        self._acquire_resource()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._release_resource()
        return False  # Don't suppress exceptions
    
    def cleanup(self):
        """Explicit cleanup method for manual management"""
        try:
            self._release_resource()
        except Exception as e:
            log_error(f"Cleanup failed: {e}")
```

### Testing Guidelines

Write tests for all new features:

```python
def test_token_cache_hit():
    """Test cache returns stored value"""
    cache = TokenCacheManager(Path("/tmp/test_cache"))
    file_path = Path("test.py")
    
    # Store value
    cache.set(file_path, 100)
    
    # Retrieve value
    cached = cache.get(file_path)
    
    assert cached == 100

def test_token_cache_invalidation():
    """Test cache invalidates on file change"""
    cache = TokenCacheManager(Path("/tmp/test_cache"))
    file_path = Path("test.py")
    
    # Store value
    cache.set(file_path, 100)
    
    # Modify file
    file_path.write_text("new content")
    
    # Should be cache miss
    cached = cache.get(file_path)
    
    assert cached is None
```

## Next Steps

1. Implement token cache (`services/token_cache.py`)
2. Add unit tests (`tests/test_token_cache.py`)
3. Integrate with token counter
4. Add UI controls in settings
5. Test with large projects
6. Measure performance improvements
7. Document usage in README

## References

- [SQLite Python Documentation](https://docs.python.org/3/library/sqlite3.html)
- [Flet Threading Model](https://flet.dev/docs/guides/python/async-apps)
- [Pathlib Documentation](https://docs.python.org/3/library/pathlib.html)
