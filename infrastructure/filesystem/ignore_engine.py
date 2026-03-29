"""
Ignore Engine - Single source of truth cho tat ca logic ignore/gitignore.

Thay the cac doan code bi trung lap o:
- core/utils/file_utils.py (scan_directory, scan_directory_shallow, load_folder_children)
- core/utils/file_scanner.py (FileScanner._build_ignore_patterns)
- components/file_tree_model.py (_collect_files_from_disk, _build_search_index_async)

Cung cap:
- build_ignore_patterns(): Tap hop patterns tu VCS + default + user + gitignore
- build_pathspec(): Tao pathspec.PathSpec tu patterns (co cache)
- read_gitignore(): Doc .gitignore, .git/info/exclude, global gitignore (co cache)
- find_git_root(): Tim git root directory tu mot path bat ky
- clear_cache(): Xoa tat ca cache

SOLID: Single Responsibility - chi lo viec quyet dinh "file/folder nay co bi ignore khong"
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import threading

import pathspec

from shared.constants import EXTENDED_IGNORE_PATTERNS


class IgnoreEngine:
    """
    Ignore Engine - Single source of truth cho tat ca logic ignore/gitignore.

    Cung cap:
    - build_ignore_patterns(): Tap hop patterns tu VCS + default + user + gitignore
    - build_pathspec(): Tao pathspec.PathSpec tu patterns (co cache)
    - read_gitignore(): Doc .gitignore, .git/info/exclude, global gitignore (co cache)
    - find_git_root(): Tim git root directory tu mot path bat ky
    - clear_cache(): Xoa tat ca cache
    """

    # Cac VCS directories luon bi exclude
    VCS_DIRS = [".git", ".hg", ".svn"]

    def __init__(self):
        # Cache cho gitignore patterns: root_path -> (mtime, patterns)
        self._gitignore_cache: Dict[str, Tuple[float, list]] = {}
        # Cache cho PathSpec objects: cache_key -> (mtime, PathSpec)
        self._pathspec_cache: Dict[str, Tuple[float, pathspec.PathSpec]] = {}
        # Cache cho global gitignore patterns
        self._global_gitignore_cache: Optional[List[str]] = None
        # Cache cho git root: path -> git_root_path
        self._git_root_cache: Dict[str, Path] = {}
        # Thread safety lock
        self._lock = threading.Lock()

    def build_ignore_patterns(
        self,
        root_path: Path,
        *,
        use_default_ignores: bool = True,
        excluded_patterns: Optional[List[str]] = None,
        use_gitignore: bool = True,
    ) -> List[str]:
        patterns: List[str] = []

        # 1. Luon exclude VCS directories
        patterns.extend(self.VCS_DIRS)

        # 2. Default ignore patterns
        if use_default_ignores:
            patterns.extend(EXTENDED_IGNORE_PATTERNS)

        # 3. User-defined patterns
        if excluded_patterns:
            patterns.extend(excluded_patterns)

        # 4. Gitignore patterns
        if use_gitignore:
            git_root = self.find_git_root(root_path)
            gitignore_pats = self.read_gitignore(root_path)

            if git_root != root_path:
                parent_pats = self.read_gitignore(git_root)
                for pat in parent_pats:
                    if pat not in gitignore_pats:
                        gitignore_pats.append(pat)

            # ========= FIX: Thêm lại global gitignore =========
            global_pats = self.read_global_gitignore()
            for pat in global_pats:
                if pat not in gitignore_pats:
                    gitignore_pats.append(pat)
            # ===================================================

            patterns.extend(gitignore_pats)

        return patterns

    def build_pathspec(
        self,
        root_path: Path,
        *,
        use_default_ignores: bool = True,
        excluded_patterns: Optional[List[str]] = None,
        use_gitignore: bool = True,
    ) -> pathspec.PathSpec:
        patterns = self.build_ignore_patterns(
            root_path,
            use_default_ignores=use_default_ignores,
            excluded_patterns=excluded_patterns,
            use_gitignore=use_gitignore,
        )
        return self.get_cached_pathspec(root_path, patterns)

    def get_cached_pathspec(
        self, root_path: Path, patterns: List[str]
    ) -> pathspec.PathSpec:
        patterns_hash = hash(tuple(patterns))
        cache_key = f"{root_path}:{patterns_hash}"
        gitignore_mtime = self._get_gitignore_mtime(root_path)

        # Check cache with lock
        with self._lock:
            if cache_key in self._pathspec_cache:
                cached_mtime, cached_spec = self._pathspec_cache[cache_key]
                if cached_mtime == gitignore_mtime:
                    return cached_spec

        # Build outside lock (expensive operation)
        spec = pathspec.PathSpec.from_lines("gitignore", patterns)  # type: ignore[arg-type]

        # Store with lock
        with self._lock:
            self._pathspec_cache[cache_key] = (gitignore_mtime, spec)
        return spec

    def read_gitignore(self, root_path: Path) -> List[str]:
        """Doc .gitignore va .git/info/exclude cho mot directory cu the."""
        gitignore_path = root_path / ".gitignore"
        cache_key = str(root_path)

        # Check cache with lock
        with self._lock:
            if cache_key in self._gitignore_cache:
                cached_mtime, cached_patterns = self._gitignore_cache[cache_key]
                try:
                    current_mtime = (
                        gitignore_path.stat().st_mtime if gitignore_path.exists() else 0
                    )
                    if current_mtime == cached_mtime:
                        return cached_patterns.copy()
                except OSError:
                    pass

        # Read outside lock (I/O operation)
        patterns: List[str] = []
        gitignore_mtime = 0.0

        if gitignore_path.exists():
            try:
                gitignore_mtime = gitignore_path.stat().st_mtime
                content = gitignore_path.read_text(encoding="utf-8", errors="replace")
                # Loc bo cac line rong hoac comment
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line)
            except (OSError, IOError):
                pass

        # Doc .git/info/exclude neu o root
        exclude_path = root_path / ".git" / "info" / "exclude"
        if exclude_path.exists():
            try:
                content = exclude_path.read_text(encoding="utf-8", errors="replace")
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line)
            except (OSError, IOError):
                pass

        # Store with lock
        with self._lock:
            self._gitignore_cache[cache_key] = (gitignore_mtime, patterns.copy())
        return patterns

    def read_global_gitignore(self) -> List[str]:
        """Doc global gitignore tu home directory ( cached cho instance)."""
        if self._global_gitignore_cache is not None:
            return self._global_gitignore_cache

        patterns: List[str] = []
        home = Path.home()
        candidates = [
            home / ".config" / "git" / "ignore",
            home / ".gitignore_global",
            home / ".gitignore",
        ]

        # Use lock to update single shared cache
        with self._lock:
            if self._global_gitignore_cache is not None:
                return self._global_gitignore_cache

            for candidate in candidates:
                if candidate.exists():
                    try:
                        content = candidate.read_text(
                            encoding="utf-8", errors="replace"
                        )
                        for line in content.splitlines():
                            line = line.strip()
                            if line and not line.startswith("#"):
                                patterns.append(line)
                        break
                    except (OSError, IOError):
                        pass
            self._global_gitignore_cache = patterns
        return patterns

    def find_git_root(self, start_path: Path) -> Path:
        """Tim git root directory bang cach di nguoc len tren (co cache)."""
        path_str = str(start_path)
        with self._lock:
            if path_str in self._git_root_cache:
                return self._git_root_cache[path_str]

        root_path = start_path
        while root_path.parent != root_path:
            if (root_path / ".git").exists():
                break
            root_path = root_path.parent

        with self._lock:
            self._git_root_cache[path_str] = root_path
        return root_path

    def clear_cache(self) -> None:
        with self._lock:
            self._gitignore_cache.clear()
            self._pathspec_cache.clear()

    def _get_gitignore_mtime(self, root_path: Path) -> float:
        gitignore_file = root_path / ".gitignore"
        if gitignore_file.exists():
            return gitignore_file.stat().st_mtime
        return 0.0
