# Port Features từ PasteMax & Repomix sang Synapse-Desktop

> **Document Purpose**: Liệt kê chi tiết các features/logic có thể port từ PasteMax và Repomix sang Synapse-Desktop, kèm so sánh hiện trạng và hướng dẫn triển khai.
>
> **Last Updated**: 2024-12-20 (Feature #1 COMPLETED)

---

## Tong quan Projects

| Aspect | PasteMax | Repomix | Synapse-Desktop |
|--------|----------|---------|-----------------|
| **Language** | TypeScript/Electron | TypeScript/Node.js | Python/Flet |
| **Type** | Desktop GUI | CLI + Web | Desktop GUI |
| **Focus** | File viewer for LLM | Pack repo to single file | AI context + Apply changes |
| **Repo** | github.com/kleneway/pastemax | github.com/yamadashy/repomix | Local |

---

## 🎯 Feature List để Port

### Legend
- ✅ Synapse đã có đầy đủ
- ⚠️ Synapse có nhưng cần cải thiện  
- ❌ Synapse chưa có
- 🔥 High Priority | ⭐ Medium Priority | 💡 Nice to have

---

## Feature #1: Extended Default Ignore Patterns - COMPLETED

### Source
- **From**: Repomix (`src/config/defaultIgnore.ts`)
- **Lines**: 1-164

### Mo ta
Repomix co danh sach ignore patterns rat comprehensive cho nhieu ngon ngu/frameworks:
- Python, JavaScript, TypeScript, Rust, Go, Java, PHP, Ruby
- IDE configs, build outputs, lock files
- OS-specific files

### So sanh voi Synapse

| Aspect | Synapse truoc | Synapse sau (COMPLETED) | Repomix |
|--------|---------------|-------------------------|---------|
| **Python patterns** | Basic | FULL | Full |
| **JS/Node patterns** | Basic | FULL | Full |
| **Rust patterns** | None | FULL | Full |
| **Go patterns** | None | FULL | Full |
| **PHP/Ruby/Elixir** | None | FULL | Full |

### Implementation Details (COMPLETED 2024-12-20)

**File modified**: `core/file_utils.py`

**Changes made**:
1. Added `EXTENDED_IGNORE_PATTERNS` constant (82 patterns)
2. Added `use_default_ignores` parameter to `scan_directory()`
3. Patterns include: node_modules, __pycache__, .venv, Cargo.lock, go.sum, etc.

**Code snippet**:
```python
# Extended Ignore Patterns - Port tu Repomix (src/config/defaultIgnore.ts)
EXTENDED_IGNORE_PATTERNS = [
    "**/node_modules/**",
    "**/__pycache__/**",
    "**/venv/**",
    "**/Cargo.lock",
    "**/go.sum",
    # ... 77 more patterns
]

def scan_directory(
    root_path: Path,
    excluded_patterns: Optional[list[str]] = None,
    use_gitignore: bool = True,
    use_default_ignores: bool = True,  # NEW
) -> TreeItem:
```

### Effort: Low | Impact: High | Status: COMPLETED

---

## Feature #2: OS-Specific Path Exclusions - COMPLETED

### Source
- **From**: PasteMax (`electron/ignore-manager.js`)
- **Lines**: 40-85

### Mô tả
PasteMax có logic để exclude các system paths theo từng OS:
- Windows: Reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9), System32
- macOS: .Spotlight-, .Trashes, .fseventsd
- Linux: /proc/, /sys/, /dev/

### Implementation Details (COMPLETED 2024-12-20)

**File modified**: `core/file_utils.py`

**Changes made**:
1. Added `is_system_path(file_path: Path) -> bool` function
2. Integrated into `_build_tree()` loop to skip system paths before ignore pattern check
3. Supports Windows (Reserved names, System32), macOS (.DS_Store, .Trashes), Linux (/proc, /sys, /dev)

### Effort: Low | Impact: Medium | Status: COMPLETED

---

## Feature #3: Smart Markdown Delimiter - COMPLETED

### Source
- **From**: Repomix (`src/core/output/outputGenerate.ts`)
- **Lines**: 26-31

### Mô tả
Khi file content chứa backticks (```), cần dùng nhiều backticks hơn cho code block wrapper để tránh broken markdown.

### Implementation Details (COMPLETED 2024-12-20)

**File modified**: `core/prompt_generator.py`

**Changes made**:
1. Added `calculate_markdown_delimiter(contents: list[str]) -> str` function
2. Refactored `generate_file_contents()` to use 3-phase approach:
   - Phase 1: Read all file contents
   - Phase 2: Calculate smart delimiter
   - Phase 3: Generate output with dynamic delimiter
3. Refactored `generate_smart_context()` similarly

**Test results**:
- No backticks in content -> Uses "```" (3 backticks)
- Content has 3 backticks -> Uses "````" (4 backticks)
- Content has 5 backticks -> Uses "``````" (6 backticks)

### Effort: Low | Impact: Medium | Status: COMPLETED

---

## Feature #4: Git Diff/Log Integration - COMPLETED
 
### Source
- **From**: Repomix (`src/core/git/gitDiffHandle.ts`, `gitLogHandle.ts`)
- **Note**: Code thực tế dùng NULL separator (\x00) logic robust hơn doc mô tả.
 
### Mô tả
Repomix có thể include git changes vào context:
- Working tree changes (uncommitted)
- Staged changes
- Commit history với file list
 
### Implementation Details (COMPLETED 2024-12-20)
 
**File created**: `core/git_utils.py`
**File modified**: `services/settings_manager.py`, `views/context_view.py`, `core/prompt_generator.py`
 
**Changes made**:
1. Implemented robust git diff/log fetching in `core/git_utils.py` using `subprocess` and NULL separator parsing.
2. Updated `generate_prompt()` to include `<git_changes>` section with `<git_diff_worktree>`, `<git_diff_staged>`, and `<git_log>`.
3. Integrated into Context View: automatically fetches git context when copying if enabled in settings (`include_git_changes=True`).
 
### Effort: Medium | Impact: Very High | Status: COMPLETED

---

## Feature #5: Parallel Processing với Worker Pool ⭐

### Source
- **From**: Repomix (`src/shared/processConcurrency.ts`)
- **Lines**: 1-95

### Mô tả
Repomix sử dụng worker pool để:
- Token counting parallel
- Security check parallel
- Dynamic thread count based on CPU

### So sánh với Synapse

| Aspect | Synapse hiện tại | Repomix |
|--------|------------------|---------|
| **Token counting** | ⚠️ Sequential | ✅ Parallel workers |
| **Security check** | ⚠️ Sequential | ✅ Parallel workers |
| **CPU-aware scaling** | ❌ None | ✅ Dynamic threads |

### File cần sửa trong Synapse
- `core/token_counter.py` - add parallel batch counting
- `core/security_check.py` - add parallel scanning

### Code Reference từ Repomix

```typescript
// repomix/src/shared/processConcurrency.ts
const TASKS_PER_THREAD = 100;

export const getProcessConcurrency = (): number => {
  return typeof os.availableParallelism === 'function' 
    ? os.availableParallelism() 
    : os.cpus().length;
};

export const getWorkerThreadCount = (numOfTasks: number) => {
  const processConcurrency = getProcessConcurrency();
  const minThreads = 1;
  const maxThreads = Math.max(
    minThreads, 
    Math.min(processConcurrency, Math.ceil(numOfTasks / TASKS_PER_THREAD))
  );
  return { minThreads, maxThreads };
};
```

### Python Implementation

```python
# Thêm vào core/token_counter.py
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict
from pathlib import Path

TASKS_PER_WORKER = 100

def get_worker_count(num_tasks: int) -> int:
    """Calculate optimal worker count based on tasks and CPU."""
    cpu_count = os.cpu_count() or 4
    return max(1, min(cpu_count, (num_tasks + TASKS_PER_WORKER - 1) // TASKS_PER_WORKER))

def count_tokens_batch(file_paths: list[Path]) -> Dict[str, int]:
    """Count tokens for multiple files in parallel."""
    if len(file_paths) < 10:
        # Not worth parallelizing for small batches
        return {str(p): count_tokens_for_file(p) for p in file_paths}
    
    worker_count = get_worker_count(len(file_paths))
    results: Dict[str, int] = {}
    
    with ProcessPoolExecutor(max_workers=worker_count) as executor:
        future_to_path = {
            executor.submit(count_tokens_for_file, path): path 
            for path in file_paths
        }
        
        for future in as_completed(future_to_path):
            path = future_to_path[future]
            try:
                results[str(path)] = future.result()
            except Exception:
                results[str(path)] = 0
    
    return results
```

### Implementation Steps
1. Thêm parallel functions vào `token_counter.py`
2. Tương tự cho `security_check.py`
3. Gọi batch functions khi load folder lớn
4. Add progress callback cho UI

### Effort: Medium | Impact: High (cho large repos)

---

## Feature #6: File Line Count Display ⭐

### Source
- **From**: Repomix (`src/core/file/fileTreeGenerate.ts`)
- **Lines**: 69-87

### Mô tả
Hiển thị số lines bên cạnh mỗi file trong tree view:
```
src/
  main.py (125 lines)
  utils.py (45 lines)
```

### So sánh với Synapse

| Aspect | Synapse hiện tại | Repomix |
|--------|------------------|---------|
| **Token count display** | ✅ Yes | ✅ Yes |
| **Line count display** | ❌ None | ✅ Yes |

### File cần sửa trong Synapse
- `components/file_tree.py` - thêm line count vào display

### Code Reference từ Repomix

```typescript
// repomix/src/core/file/fileTreeGenerate.ts
const calculateFileLineCounts = (files: ProcessedFile[]): Record<string, number> => {
  const lineCounts: Record<string, number> = {};
  for (const file of files) {
    const content = file.content;
    if (content.length === 0) {
      lineCounts[file.path] = 0;
    } else {
      const newlineCount = (content.match(/\n/g) || []).length;
      lineCounts[file.path] = content.endsWith('\n') ? newlineCount : newlineCount + 1;
    }
  }
  return lineCounts;
};
```

### Python Implementation

```python
# Thêm vào core/file_utils.py
def count_file_lines(file_path: Path) -> int:
    """Count lines in a file."""
    try:
        content = file_path.read_text(encoding='utf-8', errors='replace')
        if not content:
            return 0
        newline_count = content.count('\n')
        return newline_count if content.endswith('\n') else newline_count + 1
    except Exception:
        return 0
```

### Implementation Steps
1. Thêm function `count_file_lines()`
2. Store trong TreeItem hoặc cache riêng
3. Update UI display trong file_tree.py
4. Add setting toggle to show/hide

### Effort: Low | Impact: Low

---

## Feature #7: Binary Extensions Enhancement 💡

### Source
- **From**: PasteMax (`electron/excluded-files.js`)
- **Lines**: 140-200

### Mô tả
PasteMax có thêm nhiều binary extensions mà Synapse chưa có.

### So sánh với Synapse

| Category | Synapse | PasteMax thêm |
|----------|---------|---------------|
| **Images** | ✅ Basic | `.heic`, `.heif`, `.psd`, `.icns` |
| **Archive** | ✅ Basic | `.asar` |
| **Fonts** | ✅ Basic | - |

### File cần sửa trong Synapse
- `core/file_utils.py` - extend `BINARY_EXTENSIONS`

### Extensions cần thêm

```python
# Thêm vào BINARY_EXTENSIONS trong core/file_utils.py
ADDITIONAL_BINARY = {
    # Images
    ".heic", ".heif", ".psd", ".icns", ".raw", ".cr2", ".nef",
    # Electron
    ".asar",
    # Database
    ".mdb", ".accdb",
    # Other
    ".swf", ".fla",
}
```

### Effort: Very Low | Impact: Low

---

## Feature #8: Update Checker 💡

### Source
- **From**: PasteMax (`electron/update-checker.js`)
- **Lines**: 1-139

### Mô tả
Auto check GitHub releases cho new versions.

### So sánh với Synapse

| Aspect | Synapse hiện tại | PasteMax |
|--------|------------------|----------|
| **Update check** | ❌ None | ✅ GitHub API |
| **Version compare** | ❌ N/A | ✅ Semver |

### File cần tạo trong Synapse
- `services/update_checker.py` - new file

### Python Implementation

```python
# Tạo services/update_checker.py
import urllib.request
import json
from packaging import version
from typing import Optional
from dataclasses import dataclass

GITHUB_REPO = "HaoNgo232/synapse-desktop"
CURRENT_VERSION = "1.0.0"  # Read from config

@dataclass
class UpdateInfo:
    is_available: bool
    current_version: str
    latest_version: Optional[str]
    release_url: Optional[str]
    error: Optional[str] = None

def check_for_updates() -> UpdateInfo:
    """Check GitHub for new releases."""
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={"User-Agent": "Synapse-Desktop"})
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
        
        latest = data.get("tag_name", "").lstrip("v")
        release_url = data.get("html_url")
        
        is_available = version.parse(latest) > version.parse(CURRENT_VERSION)
        
        return UpdateInfo(
            is_available=is_available,
            current_version=CURRENT_VERSION,
            latest_version=latest,
            release_url=release_url
        )
    except Exception as e:
        return UpdateInfo(
            is_available=False,
            current_version=CURRENT_VERSION,
            latest_version=None,
            release_url=None,
            error=str(e)
        )
```

### Implementation Steps
1. Tạo `services/update_checker.py`
2. Gọi khi app khởi động (async)
3. Hiển thị notification nếu có update
4. Add button trong Settings để manual check

### Effort: Low | Impact: Low

---

## Feature #9: Multiple Output Formats ⭐

### Source
- **From**: Repomix (`src/core/output/outputStyles/`)

### Mô tả
Repomix hỗ trợ nhiều output formats:
- XML (parsable)
- Markdown
- Plain text  
- JSON

### So sánh với Synapse

| Format | Synapse hiện tại | Repomix |
|--------|------------------|---------|
| **XML-like** | ⚠️ Custom tags | ✅ Valid XML |
| **Markdown** | ❌ None | ✅ Yes |
| **Plain text** | ❌ None | ✅ Yes |
| **JSON** | ❌ None | ✅ Yes |

### File cần sửa trong Synapse
- `core/prompt_generator.py` - add format parameter
- `views/context_view.py` - add format selector

### Implementation Concept

```python
# Thêm vào core/prompt_generator.py
from enum import Enum

class OutputFormat(Enum):
    XML = "xml"
    MARKDOWN = "markdown"
    PLAIN = "plain"

def generate_prompt(
    tree: TreeItem,
    selected_paths: set[str],
    user_instructions: str = "",
    output_format: OutputFormat = OutputFormat.XML
) -> str:
    if output_format == OutputFormat.XML:
        return _generate_xml_format(...)
    elif output_format == OutputFormat.MARKDOWN:
        return _generate_markdown_format(...)
    else:
        return _generate_plain_format(...)
```

### Effort: Medium | Impact: Medium

---

## Feature #10: Security Check on Git Diffs 🔥

### Source
- **From**: Repomix (`src/core/security/securityCheck.ts`)
- **Lines**: 20-50

### Mô tả
Repomix chạy security check không chỉ trên files mà còn trên git diffs và logs.

### So sánh với Synapse

| Aspect | Synapse hiện tại | Repomix |
|--------|------------------|---------|
| **Scan files** | ✅ Yes | ✅ Yes |
| **Scan git diffs** | ❌ None | ✅ Yes |
| **Scan git logs** | ❌ None | ✅ Yes |

### File cần sửa trong Synapse
- `core/security_check.py` - extend to handle git content

### Implementation Steps
1. Sau khi lấy git diffs (Feature #4), pass vào security scanner
2. Thêm type field để phân biệt source (file/gitDiff/gitLog)
3. Hiển thị warnings riêng cho git content

### Effort: Low (sau khi có Feature #4) | Impact: High

---

## Feature #11: Compressed/Smart Context Enhancement ⭐

### Source
- **From**: Repomix (`src/core/treeSitter/`)

### Mô tả
Repomix có tree-sitter support rất comprehensive với:
- Multiple languages (Python, JS, TS, Rust, Go, etc.)
- Language-specific queries
- Parse strategies per language

### So sánh với Synapse

| Language | Synapse hiện tại | Repomix |
|----------|------------------|---------|
| **Python** | ✅ Basic | ✅ Full queries |
| **JavaScript** | ✅ Basic | ✅ Full queries |
| **TypeScript** | ⚠️ Via JS | ✅ Separate |
| **Rust** | ❌ None | ✅ Yes |
| **Go** | ❌ None | ✅ Yes |
| **Java** | ❌ None | ✅ Yes |

### Files cần sửa trong Synapse
- `core/smart_context/languages.py` - add more languages
- `core/smart_context/parser.py` - improve queries

### Implementation Steps
1. Review Repomix queries tại `src/core/treeSitter/queries/`
2. Port queries cho thêm languages
3. Improve capture types cho Python/JS

### Effort: High | Impact: Medium

---

## Feature #12: File Processing Queue với Status 💡

### Source
- **From**: PasteMax (`electron/file-processor.js`)
- **Lines**: 30-45

### Mô tả
PasteMax sử dụng p-queue cho concurrent directory processing với throttling.

### So sánh với Synapse

| Aspect | Synapse hiện tại | PasteMax |
|--------|------------------|----------|
| **Concurrent dirs** | ⚠️ Basic | ✅ PQueue based |
| **Status updates** | ⚠️ Basic | ✅ Throttled |
| **Progress callback** | ⚠️ Basic | ✅ Detailed |

### Code Reference từ PasteMax

```javascript
// pastemax/electron/file-processor.js
const CONCURRENT_DIRS = os.cpus().length * 2;
const STATUS_UPDATE_INTERVAL = 200; // ms throttle
```

### Effort: Medium | Impact: Medium (cho large repos)

---

## 📋 Implementation Priority Matrix

| Priority | Feature | Effort | Impact | Dependencies |
|----------|---------|--------|--------|--------------|
| **P0** | #1 Extended Ignore Patterns | Low | High | None |
| **P0** | #2 OS-Specific Exclusions | Low | Medium | None |
| **P0** | #4 Git Diff/Log Integration | Medium | Very High | None |
| **P1** | #10 Security Check on Git | Low | High | #4 |
| **P1** | #3 Smart Markdown Delimiter | Low | Medium | None |
| **P1** | #5 Parallel Processing | Medium | High | None |
| **P2** | #9 Multiple Output Formats | Medium | Medium | None |
| **P2** | #6 Line Count Display | Low | Low | None |
| **P3** | #7 Binary Extensions | Very Low | Low | None |
| **P3** | #8 Update Checker | Low | Low | None |
| **P3** | #11 Smart Context Enhancement | High | Medium | None |
| **P3** | #12 File Processing Queue | Medium | Medium | None |

---

## 🚀 Suggested Implementation Order

### Phase 1: Quick Wins (1-2 days)
1. ✅ Feature #1: Extended Ignore Patterns
2. ✅ Feature #2: OS-Specific Exclusions
3. ✅ Feature #7: Binary Extensions
4. ✅ Feature #3: Smart Markdown Delimiter

### Phase 2: High Impact (3-5 days)
5. ✅ Feature #4: Git Diff/Log Integration
6. ✅ Feature #10: Security Check on Git Diffs
7. ✅ Feature #5: Parallel Processing

### Phase 3: Polish (2-3 days)
8. ✅ Feature #9: Multiple Output Formats
9. ✅ Feature #6: Line Count Display
10. ✅ Feature #8: Update Checker

### Phase 4: Advanced (ongoing)
11. ✅ Feature #11: Smart Context Enhancement
12. ✅ Feature #12: File Processing Queue

---

## 📁 Files Reference

### Synapse Files to Modify
- `core/file_utils.py` - #1, #2, #6, #7
- `core/prompt_generator.py` - #3, #9
- `core/token_counter.py` - #5
- `core/security_check.py` - #5, #10
- `components/file_tree.py` - #6
- `views/context_view.py` - #9

### Synapse Files to Create
- `core/git_utils.py` - #4
- `services/update_checker.py` - #8

### Source Reference Files
- `repomix/src/config/defaultIgnore.ts`
- `repomix/src/core/output/outputGenerate.ts`
- `repomix/src/core/git/gitDiffHandle.ts`
- `repomix/src/shared/processConcurrency.ts`
- `pastemax/electron/ignore-manager.js`
- `pastemax/electron/file-processor.js`
- `pastemax/electron/update-checker.js`

---

## Notes

- Khi implement, nhớ chạy tests hiện có để đảm bảo không break
- Mỗi feature nên có unit tests riêng
- Consider backward compatibility với existing user data
