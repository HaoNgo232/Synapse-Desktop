"""
File System Utilities - File tree scanning voi gitignore support

Port tu: /home/hao/Desktop/labs/overwrite/src/utils/file-system.ts
Su dung pathspec thay vi ignore library.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import pathspec


@dataclass
class TreeItem:
    """
    Mot item trong file tree (file hoac folder).
    Tuong duong VscodeTreeItem trong TypeScript.
    """
    label: str  # Ten hien thi (filename/dirname)
    path: str  # Duong dan tuyet doi
    is_dir: bool = False
    children: list["TreeItem"] = field(default_factory=list)


# Danh sach binary extensions - COPY NGUYEN TU TYPESCRIPT
BINARY_EXTENSIONS = {
    # Images
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".svg", ".ico", ".heic", ".avif",
    # Videos
    ".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v", ".3gp", ".ogv",
    # Audio
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus", ".oga",
    # Archives
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".lzma", ".cab", ".dmg", ".iso",
    # Executables
    ".exe", ".dll", ".so", ".dylib", ".app", ".deb", ".rpm", ".msi", ".pkg",
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp",
    # Fonts
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    # Other binary
    ".bin", ".dat", ".db", ".sqlite", ".sqlite3", ".class", ".pyc", ".o", ".obj",
}


def is_binary_by_extension(file_path: Path) -> bool:
    """Check if file is binary based on extension"""
    return file_path.suffix.lower() in BINARY_EXTENSIONS


def scan_directory(
    root_path: Path,
    excluded_patterns: Optional[list[str]] = None,
    use_gitignore: bool = True
) -> TreeItem:
    """
    Scan mot directory va tra ve tree structure.
    
    Args:
        root_path: Thu muc goc can scan
        excluded_patterns: Danh sach patterns de exclude (giong gitignore format)
        use_gitignore: Co doc .gitignore khong
        
    Returns:
        TreeItem root chua toan bo cay thu muc
    """
    root_path = root_path.resolve()
    
    # Build ignore spec
    ignore_patterns: list[str] = []
    
    # Always exclude .git, .hg, .svn
    ignore_patterns.extend([".git", ".hg", ".svn"])
    
    # Add user-defined patterns
    if excluded_patterns:
        ignore_patterns.extend(excluded_patterns)
    
    # Read .gitignore if enabled
    if use_gitignore:
        gitignore_patterns = _read_gitignore(root_path)
        ignore_patterns.extend(gitignore_patterns)
    
    # Create pathspec matcher
    spec = pathspec.PathSpec.from_lines("gitwildmatch", ignore_patterns)
    
    # Build tree recursively
    return _build_tree(root_path, root_path, spec)


def _build_tree(current_path: Path, root_path: Path, spec: pathspec.PathSpec) -> TreeItem:
    """Build tree structure recursively"""
    item = TreeItem(
        label=current_path.name or str(current_path),
        path=str(current_path),
        is_dir=current_path.is_dir()
    )
    
    if not current_path.is_dir():
        return item
    
    try:
        entries = list(current_path.iterdir())
    except PermissionError:
        return item
    
    # Sort: directories first, then alphabetically
    entries.sort(key=lambda e: (not e.is_dir(), e.name.lower()))
    
    for entry in entries:
        # Get relative path for ignore matching
        try:
            rel_path = entry.relative_to(root_path)
        except ValueError:
            continue
        
        rel_path_str = str(rel_path)
        
        # Add trailing slash for directories (pathspec expects this)
        if entry.is_dir():
            rel_path_str += "/"
        
        # Check if should be ignored
        if spec.match_file(rel_path_str):
            continue
        
        # Recurse for directories
        if entry.is_dir():
            child = _build_tree(entry, root_path, spec)
            item.children.append(child)
        else:
            item.children.append(TreeItem(
                label=entry.name,
                path=str(entry),
                is_dir=False
            ))
    
    return item


def _read_gitignore(root_path: Path) -> list[str]:
    """
    Doc .gitignore va .git/info/exclude.
    Logic tuong tu TypeScript nhung don gian hoa.
    """
    patterns: list[str] = []
    
    # 1) Project .gitignore
    gitignore_path = root_path / ".gitignore"
    if gitignore_path.exists():
        try:
            content = gitignore_path.read_text(encoding="utf-8", errors="replace")
            patterns.extend(content.splitlines())
        except (OSError, IOError):
            pass
    
    # 2) .git/info/exclude
    exclude_path = root_path / ".git" / "info" / "exclude"
    if exclude_path.exists():
        try:
            content = exclude_path.read_text(encoding="utf-8", errors="replace")
            patterns.extend(content.splitlines())
        except (OSError, IOError):
            pass
    
    # 3) Global gitignore (simplified - just check common locations)
    home = Path.home()
    global_ignore_candidates = [
        home / ".config" / "git" / "ignore",
        home / ".gitignore_global",
        home / ".gitignore",
    ]
    
    for candidate in global_ignore_candidates:
        if candidate.exists():
            try:
                content = candidate.read_text(encoding="utf-8", errors="replace")
                patterns.extend(content.splitlines())
                break  # Chi doc mot file
            except (OSError, IOError):
                pass
    
    return patterns


def flatten_tree_files(tree: TreeItem) -> list[Path]:
    """
    Flatten tree thanh list cac file paths (khong bao gom directories).
    Huu ich khi can list tat ca files de dem token.
    """
    files: list[Path] = []
    
    def _walk(item: TreeItem):
        if not item.is_dir:
            files.append(Path(item.path))
        for child in item.children:
            _walk(child)
    
    _walk(tree)
    return files


def get_selected_file_paths(tree: TreeItem, selected_paths: set[str]) -> list[Path]:
    """
    Loc ra cac file paths duoc chon tu set cac duong dan.
    
    Args:
        tree: TreeItem root
        selected_paths: Set cac duong dan duoc tick
        
    Returns:
        List cac Path objects cho files duoc chon (chi files, khong co dirs)
    """
    result: list[Path] = []
    
    def _walk(item: TreeItem):
        if item.path in selected_paths:
            if not item.is_dir:
                result.append(Path(item.path))
            else:
                # Neu chon folder thi lay tat ca files trong do
                for f in flatten_tree_files(item):
                    result.append(f)
        else:
            # Van can check children vi co the chon file trong folder chua duoc chon
            for child in item.children:
                _walk(child)
    
    _walk(tree)
    return result
