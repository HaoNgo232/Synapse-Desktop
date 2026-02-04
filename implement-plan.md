# Synapse Desktop - Implementation Plan

> Tài liệu này lưu trữ các cải thiện đã xác định, tính năng mới, và context kỹ thuật để triển khai.

---

## 📊 Tổng Quan Đánh Giá

Sau khi review codebase và phân tích các đề xuất từ AI, dưới đây là những cải thiện **thực sự đáng làm** với project hiện tại.

---

## 🚀 Tier 1: Quick Wins (1-3 ngày)

### 1.1 Cache PathSpec cho Lazy Loading

**Vấn đề hiện tại:**

- Mỗi lần expand folder, `load_folder_children()` trong `file_utils.py` rebuild `PathSpec.from_lines()`
- Đã có `_gitignore_cache` cho patterns, nhưng PathSpec object được tạo mới mỗi lần

**Giải pháp:**

```python
# Thêm vào file_utils.py hoặc session_state.py
_pathspec_cache: Dict[str, Tuple[float, PathSpec]] = {}

def get_cached_pathspec(root_path: Path, patterns: list) -> PathSpec:
    """Cache PathSpec object, invalidate khi .gitignore thay đổi"""
    cache_key = str(root_path)
    gitignore_mtime = _get_gitignore_mtime(root_path)

    if cache_key in _pathspec_cache:
        cached_mtime, cached_spec = _pathspec_cache[cache_key]
        if cached_mtime == gitignore_mtime:
            return cached_spec

    spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    _pathspec_cache[cache_key] = (gitignore_mtime, spec)
    return spec
```

**Độ khó:** 🟢 Thấp  
**ROI:** Medium - Giảm CPU khi expand nhiều folders  
**Files cần sửa:** `core/utils/file_utils.py`

---

### 1.2 Tích hợp VirtualFileTreeComponent theo Ngưỡng

**Vấn đề hiện tại:**

- `VirtualFileTreeComponent` đã được implement trong `components/virtual_file_tree.py`
- Nhưng `ContextView` chỉ dùng `FileTreeComponent`
- Với project >5000 files, performance sẽ kém

**Giải pháp:**

```python
# Trong context_view.py
VIRTUAL_TREE_THRESHOLD = 5000

def _create_file_tree_component(self, total_items: int):
    if total_items > VIRTUAL_TREE_THRESHOLD:
        return VirtualFileTreeComponent(
            page=self.page,
            on_selection_changed=self._on_selection_changed,
            show_tokens=True,
            show_lines=False,
        )
    else:
        return FileTreeComponent(
            page=self.page,
            on_selection_changed=self._on_selection_changed,
            on_preview=self._preview_file,
            show_tokens=True,
            show_lines=False,
        )
```

**Độ khó:** 🟡 Medium  
**ROI:** High - Significant improvement cho large repos  
**Trade-offs:**

- Cần ensure callback compatibility giữa 2 components
- VirtualFileTree thiếu một số features (preview button)
- Testing cần cover cả 2 paths

**Files cần sửa:**

- `views/context_view.py` - Integration logic
- `components/virtual_file_tree.py` - Add missing features

---

## 🌟 Tier 2: Tính Năng Mới Đáng Thêm

### 2.1 ⭐ Select Related Files (Dependency Graph) ✅ DONE

**Status:** Implemented on 2026-02-04

**Implementation:**
- **File:** `core/dependency_resolver.py` - DependencyResolver class
- **UI:** Button "Select Related" trong toolbar của ContextView
- **Tests:** `test_tier2.py` - 5 tests passed

**Mô tả:**
Khi user chọn một file, có option để tự động chọn các files mà file đó import/require.

**Tại sao hữu ích:**

- LLMs thường cần context của imports để hiểu code
- User không phải manually tìm và chọn dependencies
- Giảm lỗi "thiếu context" khi generate code

**Context kỹ thuật - Project đã có sẵn:**

1. **Tree-sitter parsers** cho 15 ngôn ngữ (`core/smart_context/`)
2. **Import queries** đã định nghĩa:
   - Python: `@definition.import` capture trong `queries/python.py`
   - JS/TS: Có thể thêm import query tương tự
3. **Path resolution** cần implement thêm

**Cách triển khai:**

```python
# Tạo file mới: core/dependency_resolver.py

from tree_sitter import Parser, Query
from core.smart_context.loader import get_language, get_query
from pathlib import Path
from typing import Set, Optional

class DependencyResolver:
    """Resolve imports/requires trong file để tìm related files."""

    # Query để capture imports
    IMPORT_QUERIES = {
        "python": """
            (import_statement name: (dotted_name) @import)
            (import_from_statement module_name: (dotted_name) @import)
        """,
        "javascript": """
            (import_statement source: (string) @import)
            (call_expression
                function: (identifier) @func (#eq? @func "require")
                arguments: (arguments (string) @import))
        """,
        "typescript": """
            (import_statement source: (string) @import)
        """,
    }

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self._file_index: Dict[str, Path] = {}  # filename -> full path

    def build_file_index(self, tree_item: TreeItem):
        """Build index: filename -> full path cho resolve."""
        self._index_recursive(tree_item)

    def get_related_files(self, file_path: Path) -> Set[Path]:
        """
        Parse file và trả về set các files được import.

        Returns:
            Set of resolved file paths trong workspace
        """
        if not file_path.exists():
            return set()

        ext = file_path.suffix.lstrip(".")
        lang_name = self._get_lang_name(ext)

        if lang_name not in self.IMPORT_QUERIES:
            return set()

        content = file_path.read_text(encoding="utf-8", errors="ignore")
        language = get_language(ext)

        if not language:
            return set()

        # Parse và extract imports
        parser = Parser(language)
        tree = parser.parse(bytes(content, "utf-8"))
        query = Query(language, self.IMPORT_QUERIES[lang_name])

        captures = query.captures(tree.root_node)
        import_names = self._extract_import_names(captures, content)

        # Resolve to actual file paths
        return self._resolve_imports(import_names, file_path)

    def _resolve_imports(
        self,
        import_names: Set[str],
        source_file: Path
    ) -> Set[Path]:
        """
        Resolve import names thành actual file paths.

        Strategies:
        1. Relative imports: ./module, ../module
        2. Absolute imports: module_name -> search in workspace
        3. Package imports: package.submodule -> search directories
        """
        resolved = set()
        source_dir = source_file.parent

        for import_name in import_names:
            # Relative import
            if import_name.startswith("."):
                resolved_path = self._resolve_relative(import_name, source_dir)
                if resolved_path:
                    resolved.add(resolved_path)
            else:
                # Absolute import - search in workspace
                resolved_path = self._resolve_absolute(import_name)
                if resolved_path:
                    resolved.add(resolved_path)

        return resolved

    def _resolve_relative(
        self,
        import_path: str,
        source_dir: Path
    ) -> Optional[Path]:
        """Resolve relative import như ./utils hoặc ../models"""
        # Xử lý ./ và ../
        clean_path = import_path.lstrip(".")

        # Tính parent levels
        parent_levels = len(import_path) - len(clean_path)

        target_dir = source_dir
        for _ in range(parent_levels - 1):  # -1 vì . đầu tiên = current
            target_dir = target_dir.parent

        # Try với các extensions
        for ext in [".py", ".ts", ".tsx", ".js", ".jsx", ""]:
            candidate = target_dir / (clean_path.replace(".", "/") + ext)
            if candidate.exists() and candidate.is_file():
                return candidate

            # Try as directory với index file
            if ext == "":
                for index in ["index.ts", "index.js", "__init__.py"]:
                    index_file = target_dir / clean_path.replace(".", "/") / index
                    if index_file.exists():
                        return index_file

        return None

    def _resolve_absolute(self, import_name: str) -> Optional[Path]:
        """Resolve absolute import bằng file index."""
        # Convert module.submodule -> module/submodule
        path_parts = import_name.replace(".", "/")

        # Search trong file index
        for filename, full_path in self._file_index.items():
            if path_parts in str(full_path):
                return full_path

        return None
```

**UI Integration:**

```python
# Thêm vào FileTreeComponent hoặc ContextView

def _select_related_files(self, file_path: str):
    """Auto-select files được import bởi file hiện tại."""
    resolver = DependencyResolver(self.workspace_root)
    resolver.build_file_index(self.tree)

    related = resolver.get_related_files(Path(file_path))

    for related_path in related:
        self.selected_paths.add(str(related_path))

    self._render_tree()

    if self.on_selection_changed:
        self.on_selection_changed(self.selected_paths)
```

**Độ khó:** 🟡 Medium  
**Thời gian ước tính:** 3-5 ngày  
**ROI:** High - Đây là killer feature cho AI context tools

**Trade-offs:**

- ✅ **Pros:**
  - Tree-sitter đã có sẵn, không cần dependency mới
  - Import queries cho Python đã có
  - Cực kỳ hữu ích cho LLM context
- ⚠️ **Cons:**
  - Path resolution phức tạp (relative vs absolute, aliases)
  - Cần handle edge cases: circular imports, missing files
  - JS/TS có path aliases (tsconfig.json) khó resolve
  - Performance với large codebases cần caching

**Phạm vi MVP:**

1. Phase 1: Python only (đơn giản nhất)
2. Phase 2: JS/TS basic imports
3. Phase 3: Advanced (aliases, monorepo)

---

### 2.2 Fuzzy Search với RapidFuzz

**Mô tả:**
Thay thế substring search bằng fuzzy matching để user có thể gõ sai chính tả nhẹ.

**Context:**

- `rapidfuzz` đã có trong `requirements.txt`
- Hiện tại search trong `FileTreeComponent._search_in_item()` dùng substring

**Giải pháp:**

```python
# Trong components/file_tree.py

from rapidfuzz import fuzz, process

class FileTreeComponent:
    FUZZY_THRESHOLD = 70  # Minimum score để match

    def _perform_fuzzy_search(self):
        """Fuzzy search với RapidFuzz"""
        if not self.tree or not self.search_query:
            return

        # Collect all filenames
        all_items = list(self._path_index.values())
        filenames = [item.label for item in all_items]

        # Fuzzy match
        matches = process.extract(
            self.search_query,
            filenames,
            scorer=fuzz.WRatio,
            limit=100,
            score_cutoff=self.FUZZY_THRESHOLD,
        )

        # Convert matches back to paths
        self.matched_paths.clear()
        for match_name, score, idx in matches:
            item = all_items[idx]
            self.matched_paths.add(item.path)
            # Expand parents
            self._expand_parents_of(self.tree, item.path)
```

**Độ khó:** 🟢 Thấp  
**Thời gian:** 1 ngày  
**ROI:** Medium

**Trade-offs:**

- ✅ Tìm được files ngay cả khi gõ sai
- ⚠️ Có thể match quá nhiều results không liên quan
- ⚠️ Cần tune threshold cho phù hợp

---

### 2.3 Context Presets cho LLM

**Mô tả:**
Cho phép user lưu và load các "preset" context configurations:

- "Bug Fix": Auto include recent git diff + test files
- "Feature Dev": Include related files + interfaces
- "Code Review": Include changed files only

**Giải pháp:**

```python
# Tạo file mới: services/context_presets.py

@dataclass
class ContextPreset:
    name: str
    description: str
    auto_select_patterns: List[str]  # Glob patterns
    include_git_diff: bool
    include_tests: bool
    max_tokens: Optional[int]
    output_style: OutputStyle

DEFAULT_PRESETS = [
    ContextPreset(
        name="Bug Fix",
        description="Include recent changes and related tests",
        auto_select_patterns=["**/test_*.py", "**/*_test.py"],
        include_git_diff=True,
        include_tests=True,
        max_tokens=8000,
        output_style=OutputStyle.XML,
    ),
    ContextPreset(
        name="Documentation",
        description="Focus on signatures and docstrings",
        auto_select_patterns=[],
        include_git_diff=False,
        include_tests=False,
        max_tokens=4000,
        output_style=OutputStyle.SMART,
    ),
]
```

**Độ khó:** 🟡 Medium  
**Thời gian:** 2-3 ngày  
**ROI:** Medium

---

## 🔧 Tier 3: Performance Optimizations (Khi cần)

### 3.1 Background Prompt Generation với Progress

**Vấn đề:**
Khi copy context với nhiều files (100+), UI có thể freeze.

**Giải pháp:**

```python
async def _generate_prompt_async(
    self,
    selected_paths: Set[str],
    progress_callback: Callable[[int, int], None]
) -> str:
    """Generate prompt in background với progress updates."""
    total = len(selected_paths)
    chunks = []

    for i, path in enumerate(selected_paths):
        if self._is_cancelled:
            raise CancelledException()

        content = await aiofiles.open(path).read()
        chunks.append(self._format_file(path, content))

        progress_callback(i + 1, total)
        await asyncio.sleep(0)  # Yield to event loop

    return "\n".join(chunks)
```

**Độ khó:** 🟡 Medium  
**ROI:** High cho large selections  
**Trade-offs:** Thêm complexity, cần cancel mechanism

---

### 3.2 Streaming Git Diff

**Vấn đề:**
`get_diff_only()` load toàn bộ diff vào memory.

**Giải pháp:**

```python
def stream_git_diff(repo_path: Path) -> Iterator[str]:
    """Stream git diff từng chunk thay vì load hết."""
    process = subprocess.Popen(
        ["git", "diff", "--no-color"],
        cwd=repo_path,
        stdout=subprocess.PIPE,
        text=True,
    )

    for line in process.stdout:
        yield line
```

**Độ khó:** 🟢 Thấp  
**ROI:** Low (chỉ ảnh hưởng với diff rất lớn)

---

## ❌ Không Nên Làm

### Async/Aiofiles Migration

- **Lý do:** Risk/reward ratio quá cao, codebase stable
- **Alternative:** Chỉ async hóa specific hotpaths

### Control Reference Pattern

- **Lý do:** Flet không design cho pattern này, sẽ gây bugs

### Rust pyo3 Worker

- **Lý do:** Token counting đã dùng `rs-bpe`, thêm layer = more complexity

---

## 📅 Roadmap Đề Xuất

```
Week 1:
├── [1.1] Cache PathSpec
└── [1.2] VirtualFileTree integration

Week 2-3:
├── [2.1] Select Related Files (MVP: Python only)
└── [2.2] Fuzzy Search

Week 4:
├── [2.1] Select Related Files (JS/TS)
└── [2.3] Context Presets (optional)

Future:
├── [3.1] Background Prompt Generation
└── Performance monitoring & tuning
```

---

## 📝 Notes

### Các claim từ AI reviews đã kiểm chứng là SAI:

1. ❌ "Deferred token không notify UI" → Đây là by design để tránh spam
2. ❌ "Scan dùng Python thay vì Rust" → Đã integrate scandir-rs
3. ❌ "Full re-render quá thường xuyên" → Đã có nhiều optimizations

### Các claim ĐÚNG:

1. ✅ VirtualFileTreeComponent chưa được tích hợp
2. ✅ PathSpec rebuild mỗi lần expand
3. ✅ Có thể thêm fuzzy search

---

_Last updated: 2026-02-03_
