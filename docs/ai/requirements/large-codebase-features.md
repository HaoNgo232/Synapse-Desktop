---
phase: requirements
title: Large Codebase Features & Improvements
description: New features and improvements for working efficiently with large codebases
---

# Requirements: Large Codebase Features & Improvements

## Problem Statement

### Current Challenges
When working with large codebases (thousands of files, millions of lines):

1. **Performance Issues**
   - File tree scanning can take 10+ seconds for large repositories
   - Token counting blocks UI thread, causing freezes
   - Memory usage grows linearly with file count (500MB+ for large projects)
   - No progress indication during long operations

2. **Usability Limitations**
   - Selecting many files is tedious (no bulk selection patterns)
   - No way to save/restore common file selections
   - Hard to work with multiple related file groups
   - No incremental/lazy loading of file tree

3. **Missing Features**
   - No file content caching for faster re-counting
   - No project-specific presets (beyond language presets)
   - No workspace partitioning (work with subsets)
   - Limited search capabilities (no regex, no content search)

4. **Weak Fallback Mechanisms**
   - Parser fails completely on malformed OPX
   - No partial application when some files fail
   - No retry mechanism for transient errors
   - No graceful degradation on resource constraints

## Goals & Objectives

### Primary Goals
1. **Performance for Large Codebases**
   - Support projects with 10,000+ files without UI freezes
   - Keep memory usage under 300MB for typical use cases
   - Provide instant UI feedback during long operations

2. **Enhanced Productivity**
   - Reduce time to select relevant files by 80%
   - Enable working with multiple file groups simultaneously
   - Support team collaboration on common selections

3. **Robust Error Handling**
   - Apply partial changes when possible (don't fail all-or-nothing)
   - Recover from transient errors automatically
   - Provide clear guidance when errors occur

### Secondary Goals
- Improve token counting accuracy and speed
- Better integration with git workflows
- Enhanced search and filtering capabilities
- Smarter defaults based on project patterns

### Non-Goals
- Full IDE features (debugging, refactoring tools)
- Real-time collaboration (beyond shared presets)
- Custom OPX dialect extensions
- Plugin/extension system

## User Stories & Use Cases

### UC-1: Working with Monorepo
**As a** developer working in a large monorepo  
**I want to** quickly select only files from one microservice  
**So that** I can generate focused context for LLM without irrelevant code

**Acceptance Criteria:**
- Can create named file selection "groups" (e.g., "auth-service")
- Can switch between groups in one click
- Groups persist across sessions
- Can share groups via export/import

### UC-2: Incremental File Tree Loading
**As a** developer opening a 50,000-file repository  
**I want to** see the file tree structure immediately  
**So that** I don't have to wait 30 seconds before I can do anything

**Acceptance Criteria:**
- Top-level folders visible within 500ms
- Subdirectories load on-demand when expanded
- Progress indicator shows loading state
- Can search before full tree is loaded

### UC-3: Token Counting Performance
**As a** developer selecting 200 large files  
**I want to** see token counts update smoothly  
**So that** the UI remains responsive during counting

**Acceptance Criteria:**
- Token counts update incrementally (show progress)
- UI remains responsive during counting
- Can cancel long-running count operation
- Results cached for unchanged files

### UC-4: Partial OPX Application
**As a** developer applying OPX with 20 file changes  
**I want** successful changes to be applied even if 2 files fail  
**So that** I don't lose all progress due to one error

**Acceptance Criteria:**
- Each file operation is independent
- Success/failure reported per file
- Option to retry failed operations
- Backups created before each change

### UC-5: Smart File Selection
**As a** developer  
**I want to** select all files matching a pattern with one action  
**So that** I don't have to click hundreds of checkboxes

**Acceptance Criteria:**
- Select by glob pattern (e.g., "**/*.test.ts")
- Select by git status (modified, untracked)
- Select by file size/age
- Combine multiple criteria

### UC-6: Workspace Partitioning
**As a** developer working on a feature spanning 3 packages  
**I want to** focus only on those packages temporarily  
**So that** I don't see irrelevant files in other areas

**Acceptance Criteria:**
- Can "pin" folders to create focused view
- Can quickly toggle between full view and focused view
- Selection state preserved per view
- Breadcrumbs show current context

## Success Criteria

### Performance Metrics
- ✅ File tree initial render: < 1 second for any project size
- ✅ Token counting: < 100ms per file (with caching)
- ✅ Memory usage: < 300MB for 10,000 files
- ✅ Search results: < 500ms for any query

### Usability Metrics
- ✅ Reduce file selection time from 5min → 30sec for 100-file selections
- ✅ 80% of users report improved productivity
- ✅ Zero data loss from partial failures

### Reliability Metrics
- ✅ 95% of OPX operations succeed (up from 85%)
- ✅ Automatic recovery from 90% of transient errors
- ✅ Zero crashes from memory exhaustion

## Proposed New Features

### 1. File Selection Groups (Workspaces)
- **What:** Named, persistent file selections
- **Why:** Quick switching between contexts (e.g., frontend, backend, tests)
- **How:** Store as `.overwrite/groups.json` in project root

### 2. Incremental File Tree Loading
- **What:** Lazy-load subdirectories on expansion
- **Why:** Instant startup for large projects
- **How:** Background thread populates tree depth-first

### 3. Smart Selection Tools
- **What:** Select files by pattern/criteria
- **Why:** Bulk operations without manual clicking
- **How:** Pattern dialog with preview of matches

### 4. Token Count Caching
- **What:** Persistent cache of file token counts
- **Why:** Instant re-counting for unchanged files
- **How:** Store hash + count in SQLite database

### 5. Partial OPX Application
- **What:** Independent file operation execution
- **Why:** Don't lose progress on single failure
- **How:** Try-catch per file with detailed reporting

### 6. Git Integration Enhancements
- **What:** Quick select by git status, diff view
- **Why:** Common workflow is "select changed files"
- **How:** Use pygit2 for fast git operations

### 7. Project-Specific Presets
- **What:** Auto-detected project patterns
- **Why:** Smart defaults based on actual usage
- **How:** ML-based pattern learning from history

### 8. Advanced Search
- **What:** Regex search, content search, combined filters
- **Why:** Find relevant files faster
- **How:** Use ripgrep for content search

### 9. Batch Operations
- **What:** Apply same operation to multiple groups
- **Why:** Efficient multi-context workflows
- **How:** Queue system with parallel execution

### 10. Memory-Aware Operations
- **What:** Graceful degradation on memory pressure
- **Why:** Prevent crashes on resource-constrained systems
- **How:** Monitor memory, disable caching when low

## Improvements to Existing Features

### Enhanced File Tree
- Add virtual scrolling for 1000+ file lists
- Show file size and last modified date
- Folder-level statistics (file count, total tokens)
- Keyboard navigation (arrow keys, vim keys)

### Better Diff Viewer
- Side-by-side diff view option
- Syntax highlighting in diff
- Word-level diff highlighting
- Jump to next/previous change

### Improved History
- Search history entries
- Filter by date range, success/failure
- Export history as CSV/JSON
- Statistics dashboard (success rate over time)

### Enhanced Settings
- Import/export all settings
- Reset to defaults per section
- Settings validation and hints
- Settings search

## Fallback Mechanisms

### 1. Progressive OPX Parsing
**Current:** Parser fails on first error, returns nothing  
**Improved:** Continue parsing, collect errors, return partial results

```python
# Instead of raising exception immediately
if not required_field:
    errors.append(f"Missing field in edit #{i}")
    continue  # Try next edit
```

### 2. Graceful File Operation Degradation
**Current:** Operation fails if file locked or permission denied  
**Improved:** Retry with exponential backoff, then skip with warning

```python
for attempt in range(3):
    try:
        perform_operation()
        break
    except PermissionError as e:
        if attempt < 2:
            time.sleep(0.1 * (2 ** attempt))
        else:
            log_warning(f"Skipped {file}: {e}")
```

### 3. Memory Pressure Handling
**Current:** App may crash if memory exhausted  
**Improved:** Monitor memory, clear caches, disable features

```python
if memory_mb > 800:
    clear_token_cache()
    disable_thumbnails()
    trigger_gc()
```

### 4. Token Counter Fallback Chain
**Current:** Uses tiktoken only  
**Improved:** Fallback chain: tiktoken → estimation → word count

```python
try:
    return tiktoken_count(text)
except Exception:
    try:
        return estimate_tokens(text)  # len(text) / 4
    except:
        return len(text.split())  # Word count
```

### 5. Partial Tree Loading Fallback
**Current:** All-or-nothing tree scan  
**Improved:** Load partial tree if timeout/error

```python
try:
    tree = scan_directory_with_timeout(path, timeout=10)
except TimeoutError:
    tree = scan_top_level_only(path)
    show_warning("Large project, showing top level only")
```

### 6. Gitignore Parser Fallback
**Current:** pathspec library required  
**Improved:** Simple glob fallback if pathspec unavailable

```python
try:
    spec = pathspec.PathSpec.from_lines(...)
except Exception:
    spec = SimpleGlobMatcher(patterns)  # Basic glob support
```

### 7. Clipboard Operation Fallback
**Current:** pyperclip with limited platform support  
**Improved:** Try multiple backends, fallback to file export

```python
try:
    pyperclip.copy(text)
except:
    try:
        use_platform_clipboard(text)
    except:
        export_to_file(text, "context_export.txt")
        show_message("Exported to context_export.txt")
```

### 8. Theme Fallback
**Current:** Custom theme only  
**Improved:** Detect system theme preference, provide alternatives

```python
try:
    theme = load_custom_theme()
except:
    if is_system_dark_mode():
        theme = builtin_dark_theme()
    else:
        theme = builtin_light_theme()
```

## Constraints & Assumptions

### Technical Constraints
- Must remain single-executable desktop app (no server dependency)
- Python 3.10+ only (can use modern features)
- Flet framework limitations (async, threading model)
- Cross-platform (Linux, Windows, macOS)

### Performance Constraints
- Startup time must be < 3 seconds
- Memory budget: 500MB typical, 1GB maximum
- UI must remain responsive (no 100ms+ freezes)

### Compatibility Constraints
- Must not break existing OPX format
- Must migrate existing user settings automatically
- Backwards compatible with old history/session files

### Assumptions
- Users work with git repositories (90%+ case)
- Modern hardware (4GB+ RAM, SSD)
- Python environment available for source installs
- Users understand basic regex/glob patterns

## Questions & Open Items

### Technical Decisions Needed
1. **Token cache storage:** SQLite vs JSON file?
   - SQLite: Better for large datasets, requires dependency
   - JSON: Simple, already used elsewhere

2. **Tree loading strategy:** Virtual scroll vs pagination vs lazy load?
   - Virtual scroll: Best UX but complex
   - Pagination: Simple but disruptive
   - Lazy load: Good balance

3. **Group storage:** Project-local vs global?
   - Project-local: Better for teams (commit to repo)
   - Global: Works for any project immediately

### UX Decisions Needed
1. How to expose "select by pattern" feature?
   - Context menu on tree root
   - Toolbar button
   - Keyboard shortcut

2. Should we auto-enable features based on project size?
   - Auto-enable incremental loading for 1000+ files
   - Auto-disable token caching for small projects

3. How much telemetry/analytics to collect?
   - Performance metrics (startup time, memory)
   - Feature usage
   - Error rates

### Research Needed
1. Benchmark different tree rendering approaches
2. Profile memory usage patterns
3. Test OPX parser on real-world edge cases
4. Survey users on most-wanted features
