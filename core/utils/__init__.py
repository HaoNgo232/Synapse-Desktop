"""
Core Utilities Package

Chứa các utility modules:
- file_utils: File system operations, gitignore, tree scanning
- git_utils: Git operations (diff, log, status)
- language_utils: Language detection cho syntax highlighting
- threading_utils: Thread management và cancellation
- qt_utils: PySide6 utilities (signals, debounce, main-thread scheduling)
"""

# Re-export commonly used items for convenience
from core.utils.file_utils import (
    TreeItem,
    scan_directory,
    is_binary_by_extension,
    is_binary_file,
    flatten_tree_files,
    get_selected_file_paths,
)

from core.utils.git_utils import (
    GitDiffResult,
    GitLogResult,
    GitCommit,
    is_git_installed,
    is_git_repo,
    get_git_diffs,
    get_git_logs,
)

from core.utils.language_utils import (
    get_language_from_filename,
    get_language_from_path,
    get_llm_compatible_language,
)

from core.utils.threading_utils import (
    get_app_stop_event,
    signal_app_shutdown,
    is_app_stopping,
    shutdown_all,
)

from core.utils.safe_timer import (
    SafeTimer,
    DebouncedCallback,
)

from core.utils.background_processor import (
    BackgroundProcessor,
    BatchProcessor,
    TaskHandle,
    TaskPriority,
    get_background_processor,
    shutdown_background_processor,
)

__all__ = [
    # file_utils
    "TreeItem",
    "scan_directory",
    "is_binary_by_extension",
    "is_binary_file",
    "flatten_tree_files",
    "get_selected_file_paths",
    # git_utils
    "GitDiffResult",
    "GitLogResult",
    "GitCommit",
    "is_git_installed",
    "is_git_repo",
    "get_git_diffs",
    "get_git_logs",
    # language_utils
    "get_language_from_filename",
    "get_language_from_path",
    "get_llm_compatible_language",
    # threading_utils
    "get_app_stop_event",
    "signal_app_shutdown",
    "is_app_stopping",
    "shutdown_all",
    # safe_timer
    "SafeTimer",
    "DebouncedCallback",
    # background_processor
    "BackgroundProcessor",
    "BatchProcessor",
    "TaskHandle",
    "TaskPriority",
    "get_background_processor",
    "shutdown_background_processor",
]
