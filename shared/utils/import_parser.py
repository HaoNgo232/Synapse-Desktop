"""
Import Parser Utilities.

Simple utilities de parse local imports va mo rong related files theo depth.
No AST parsing; chi dung regex va filesystem checks.
"""

import re
from pathlib import Path


_PY_FROM_IMPORT_RE = re.compile(r"^\s*from\s+([.\w]+)\s+import\s+(.+)$")
_PY_IMPORT_RE = re.compile(r"^\s*import\s+(.+)$")

_JS_TS_IMPORT_PATTERNS = [
    re.compile(
        r"^\s*import\s+(?:[^'\"]+?\s+from\s+)?['\"]([^'\"]+)['\"]", re.MULTILINE
    ),
    re.compile(r"^\s*export\s+[^'\"]+?\s+from\s+['\"]([^'\"]+)['\"]", re.MULTILINE),
    re.compile(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)"),
    re.compile(r"import\(\s*['\"]([^'\"]+)['\"]\s*\)"),
]

_JS_TS_EXTENSIONS = [
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mts",
    ".cts",
    ".mjs",
    ".cjs",
    ".json",
]

# --- Rust & Java Patterns ---
_RUST_USE_RE = re.compile(r"^\s*use\s+([.\w:]+)(?:::\{(.+)\})?;", re.MULTILINE)
_RUST_MOD_RE = re.compile(r"^\s*mod\s+(\w+);", re.MULTILINE)
_JAVA_IMPORT_RE = re.compile(r"^\s*import\s+([\w.]+);", re.MULTILINE)


def _normalize_rel_path(path: str) -> str:
    return path.replace("\\", "/")


def _rel_file_if_exists(candidate: Path, workspace_root: Path) -> str | None:
    if not candidate.exists() or not candidate.is_file():
        return None

    try:
        rel = candidate.resolve().relative_to(workspace_root.resolve())
    except ValueError:
        return None
    return rel.as_posix()


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = _normalize_rel_path(item)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _parse_import_list(raw_imports: str) -> list[str]:
    """Parse comma-separated imports va bo alias `as` neu co."""
    cleaned = raw_imports.split("#", 1)[0].strip().strip("()")
    if not cleaned:
        return []

    result: list[str] = []
    for part in cleaned.split(","):
        token = part.strip()
        if not token:
            continue
        name = token.split(" as ", 1)[0].strip()
        if name and name != "*":
            result.append(name)
    return result


def _resolve_python_module(
    module: str, file_path: Path, workspace_root: Path
) -> list[str]:
    module = module.strip()
    if not module:
        return []

    if module.startswith("."):
        dot_count = len(module) - len(module.lstrip("."))
        module_tail = module[dot_count:]
        base_dir = file_path.parent
        for _ in range(max(dot_count - 1, 0)):
            base_dir = base_dir.parent
        module_base = base_dir
        if module_tail:
            module_base = module_base.joinpath(
                *[p for p in module_tail.split(".") if p]
            )
    else:
        module_parts = [p for p in module.split(".") if p]
        if not module_parts:
            return []
        module_base = workspace_root.joinpath(*module_parts)

    candidates = [module_base.with_suffix(".py"), module_base / "__init__.py"]

    resolved: list[str] = []
    for candidate in candidates:
        rel = _rel_file_if_exists(candidate, workspace_root)
        if rel:
            resolved.append(rel)
    return resolved


def _resolve_js_ts_import(
    specifier: str, file_path: Path, workspace_root: Path
) -> list[str]:
    cleaned = specifier.strip().split("?", 1)[0].split("#", 1)[0]
    if not cleaned or not cleaned.startswith("."):
        return []

    import_base = (file_path.parent / cleaned).resolve()
    candidates: list[Path] = []

    if Path(cleaned).suffix:
        candidates.append(import_base)
    else:
        for ext in _JS_TS_EXTENSIONS:
            candidates.append(import_base.parent / f"{import_base.name}{ext}")
            candidates.append(import_base / f"index{ext}")

    resolved: list[str] = []
    for candidate in candidates:
        rel = _rel_file_if_exists(candidate, workspace_root)
        if rel:
            resolved.append(rel)
    return resolved


def _resolve_rust_module(
    module: str, file_path: Path, workspace_root: Path
) -> list[str]:
    """Resolve Rust crate/module to file path."""
    clean_mod = (
        module.replace("::", "/").replace("crate/", "").replace("self/", "").strip("/")
    )
    if not clean_mod:
        return []

    # Local siblings or children
    base_dirs = [file_path.parent, workspace_root / "src"]
    candidates = []

    # Try different combinations of nested paths
    # e.g. models/user/User -> models/user/user.rs or models/user.rs
    parts = clean_mod.split("/")
    for base in base_dirs:
        for i in range(len(parts), 0, -1):
            sub_path = "/".join(parts[:i])
            candidates.append(base / f"{sub_path}.rs")
            candidates.append(base / sub_path / "mod.rs")
            # Lowercase version for Rust convention
            candidates.append(base / f"{sub_path.lower()}.rs")
            candidates.append(base / sub_path.lower() / "mod.rs")

    resolved: list[str] = []
    for candidate in candidates:
        rel = _rel_file_if_exists(candidate, workspace_root)
        if rel:
            resolved.append(rel)
    return resolved


def _resolve_java_import(import_str: str, workspace_root: Path) -> list[str]:
    """Resolve Java package/class to file path (heuristic)."""
    clean_path = import_str.replace(".", "/").strip()
    if not clean_path:
        return []

    # Heuristic: Find in common src roots
    src_roots = ["src/main/java", "src/test/java", "src", "java"]
    candidates = []
    for root in src_roots:
        candidates.append(workspace_root / root / f"{clean_path}.java")

    resolved: list[str] = []
    for candidate in candidates:
        rel = _rel_file_if_exists(candidate, workspace_root)
        if rel:
            resolved.append(rel)
    return resolved


def extract_local_imports(file_path: Path, workspace_root: Path) -> list[str]:
    """
    Extract local import file paths from a source file.

    Supported forms:
    - Python: `from x.y import z`, `import x.y`
    - JavaScript/TypeScript: `import ... from './x'`, `require('./x')`
    - Rust: `use crate::x`, `mod x`
    - Java: `import x.y.z`

    Only local imports are returned. External package imports are ignored.

    Args:
        file_path: Absolute path of source file
        workspace_root: Workspace root for resolving relative paths

    Returns:
        Relative file paths resolved from workspace root
    """
    if not file_path.exists() or not file_path.is_file():
        return []

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    suffix = file_path.suffix.lower()
    found: list[str] = []

    if suffix in {".py", ".pyi"}:
        raw_lines = content.splitlines()
        joined_lines: list[str] = []
        buffer = ""
        paren_depth = 0
        for raw_line in raw_lines:
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                if not buffer:
                    continue
            buffer += (" " + raw_line) if buffer else raw_line
            paren_depth += raw_line.count("(") - raw_line.count(")")
            if paren_depth <= 0:
                joined_lines.append(buffer)
                buffer = ""
                paren_depth = 0
        if buffer:
            joined_lines.append(buffer)

        for line in joined_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            from_match = _PY_FROM_IMPORT_RE.match(line)
            if from_match:
                module = from_match.group(1).strip()
                imported = from_match.group(2)
                found.extend(_resolve_python_module(module, file_path, workspace_root))

                for name in _parse_import_list(imported):
                    found.extend(
                        _resolve_python_module(
                            f"{module}.{name}" if module else name,
                            file_path,
                            workspace_root,
                        )
                    )
                continue

            import_match = _PY_IMPORT_RE.match(line)
            if import_match:
                imported_modules = _parse_import_list(import_match.group(1))
                for module in imported_modules:
                    found.extend(
                        _resolve_python_module(module, file_path, workspace_root)
                    )

        return _dedupe_keep_order(found)

    if suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"}:
        for pattern in _JS_TS_IMPORT_PATTERNS:
            for match in pattern.finditer(content):
                specifier = match.group(1)
                found.extend(
                    _resolve_js_ts_import(specifier, file_path, workspace_root)
                )

        return _dedupe_keep_order(found)

    if suffix == ".rs":
        for match in _RUST_USE_RE.finditer(content):
            base_mod = (
                match.group(1).replace("crate", "").replace("self", "").strip(": ")
            )
            if base_mod:
                found.extend(_resolve_rust_module(base_mod, file_path, workspace_root))
            if match.group(2):
                sub_mods = [s.strip() for s in match.group(2).split(",")]
                for sm in sub_mods:
                    found.extend(
                        _resolve_rust_module(
                            f"{base_mod}::{sm}" if base_mod else sm,
                            file_path,
                            workspace_root,
                        )
                    )

        for match in _RUST_MOD_RE.finditer(content):
            found.extend(
                _resolve_rust_module(match.group(1), file_path, workspace_root)
            )

        return _dedupe_keep_order(found)

    if suffix == ".java":
        for match in _JAVA_IMPORT_RE.finditer(content):
            found.extend(_resolve_java_import(match.group(1), workspace_root))
        return _dedupe_keep_order(found)

    return []


def get_related_files(
    changed_files: list[str],
    workspace_root: Path,
    depth: int = 1,
    max_files: int = 20,
) -> list[str]:
    """
    Resolve related files by traversing local imports up to the given depth.
    """
    if depth <= 0 or max_files <= 0:
        return []

    changed_set = {_normalize_rel_path(path) for path in changed_files if path}
    if not changed_set:
        return []

    visited: set[str] = set(changed_set)
    current_level: list[str] = list(changed_set)
    related: list[str] = []

    for _ in range(depth):
        if not current_level:
            break

        next_level: list[str] = []
        for rel_path in current_level:
            file_abs = workspace_root / rel_path
            imports = extract_local_imports(file_abs, workspace_root)
            for imported_file in imports:
                normalized = _normalize_rel_path(imported_file)
                if normalized in visited:
                    continue

                visited.add(normalized)
                related.append(normalized)
                next_level.append(normalized)

                if len(related) >= max_files:
                    return related[:max_files]

        current_level = next_level

    return related[:max_files]
