<!-- README.md — Updated 2026-02-23 -->
<!-- Sections marked with [UPDATED] or [NEW] indicate changes from the original README -->

# Synapse Desktop

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Qt](https://img.shields.io/badge/GUI-PySide6%20(Qt6)-41cd52)
![Version](https://img.shields.io/badge/version-1.0.0-purple)

<!-- [UPDATED] Expanded project description -->
A desktop application that bridges your codebase and AI assistants (ChatGPT, Claude, Gemini, or any OpenAI-compatible API). Synapse Desktop lets you select files from a project tree, package them into structured prompts with accurate token counts, and then apply AI-generated code changes back to your codebase — all with visual diffs, auto-backup, and continuous memory across sessions.

- **Send Context**: Select files in your project → copy structured prompt → paste into ChatGPT / Claude / Gemini
- **Apply Changes**: Paste XML response from AI → view visual diff → apply to codebase with auto-backup
- **AI Suggest Select**: Let an LLM automatically pick the relevant files based on your instructions

## Application Interface

**1. Context Management (Main Interface)**
![Select files and folders to send to AI](assets/image.png)
*Select files and view the calculated token count before copying the prompt.*

**2. Apply Changes (Apply Tab)**
![Apply OPX XML content and view code diff](assets/image-1.png)
*Paste OPX XML from the AI and review visual diffs before confirming file overwrites.*

**3. Operation History (History Tab)**
![Manage copy and apply history](assets/image-2.png)
*Review the list of successful or failed apply/copy tasks.*

**4. Settings (Settings Tab)**
![Settings interface](assets/image-3.png)
*Configure file rules, access permissions, and privacy options in the Settings tab.*

---

**Key design decisions:**

- **PySide6 (Qt 6)** — Cross-platform native UI with full control over the rendering pipeline. Chosen over Electron for lower memory footprint and faster startup.
- **Mixin pattern** — `ContextViewQt` composes behavior from `UIBuilderMixin`, `CopyActionsMixin`, `RelatedFilesMixin`, and `TreeManagementMixin` to keep each concern in a focused module.
- **Service Container** — `ServiceContainer` (`services/service_container.py`) acts as the composition root; services are injected into views rather than imported globally. Existing module-level singletons (`cache_registry`, `encoder_registry`) remain accessible for backward compatibility.
- **Thread-safe by design** — Global cancellation flags (`_is_scanning`, `is_counting_tokens`) with `threading.Lock`, `SignalBridge` for scheduling callbacks on the main thread, and `SafeTimer` to avoid race conditions during folder switches.
- **OPX (Overwrite Patch XML)** — A structured XML format for describing file changes (`new`, `patch`, `replace`, `remove`, `move`), enabling reliable round-trip between the AI and the filesystem.
- **Rust-accelerated scanning** — Optional `scandir-rs` integration for 3–70× faster directory traversal; transparent fallback to Python `os.scandir`.

---

<!-- [NEW] Tech stack section -->
## Tech Stack & Dependencies

| Layer | Technology | Purpose |
|---|---|---|
| GUI Framework | **PySide6** (Qt 6) | Cross-platform native widgets, signals/slots |
| Language | **Python 3.10+** | Type hints, `match` statements, `pathlib` |
| Tokenization | **tiktoken / HuggingFace tokenizers** | Accurate token counting per model |
| Fast I/O | **scandir-rs** *(optional)* | Rust-based directory walker (3–70× faster) |
| Ignore patterns | **pathspec** | Gitignore-compatible pattern matching |
| Memory monitoring | **psutil** | RSS tracking and cache pressure alerts |
| Version control | **Git** *(optional)* | Branch detection, diff context, change log |

All Python dependencies are listed in `requirements.txt`.

---

<!-- [NEW] Key modules section -->
## Key Modules & Components

### Entry Point

| File | Description |
|---|---|
| `main_window.py` | `SynapseMainWindow` — top bar, tab widget, status bar, session restore, memory monitor. The `main()` function bootstraps the app: ensures directories, initializes encoders, registers caches, applies the theme, and shows the window. |

### Views (`views/`)

| File | Description |
|---|---|
| `context_view_qt.py` | File tree browser, token counting display, copy actions (Context / Smart / Diff Only), related-file resolution, AI Suggest Select, prompt template management. Uses mixin pattern for separation. |
| `apply_view_qt.py` | OPX input editor (left panel) and preview/results viewer (right panel, 40:60 splitter). Parses OPX, shows visual diffs via `DiffViewerWidget`, applies changes with auto-backup, and saves continuous AI memory. |
| `history_view_qt.py` | 35:65 master–detail layout. Entries grouped by date, searchable. Detail panel shows progress bar, file change rows, error cards, and action buttons (Copy OPX / Re-apply / Delete). |
| `logs_view_qt.py` | Log viewer with level filtering, auto-scroll, colored formatting, debug mode toggle, and copy-to-clipboard. Reads from rotating log files in `~/.config/synapse-desktop/logs/`. |
| `settings_view_qt.py` | Three-column card layout. Manages excluded patterns (tag chips), gitignore toggle, security scan, AI Context Builder (API key, base URL, model picker with server fetch), repository rules, session management, import/export. Auto-saves with 800 ms debounce. |

### Services (`services/`)

| File | Description |
|---|---|
| `service_container.py` | Composition root. Owns `PromptBuildService` and `QtClipboardService`; references `cache_registry` and `encoder_registry` singletons. |
| `token_display.py` | `TokenDisplayService` — caches per-file token counts, batches parallel counting, supports folder aggregation with a dedicated folder cache, and schedules deferred counting for large projects. |
| `encoder_registry.py` | Singleton accessor for `TokenizationService`. Reads the active model from settings and resolves the HuggingFace tokenizer repo. |
| `cache_adapters.py` | Adapter classes (`TokenCacheAdapter`, `SecurityCacheAdapter`, `IgnoreCacheAdapter`, `RelationshipCacheAdapter`) wrapping internal caches behind a unified `ICacheable` protocol for bulk invalidation. |
| `memory_monitor.py` | `MemoryMonitor` — periodic RSS tracking via `psutil`, warning thresholds (500 MB / 1 GB), callback-based updates to the top bar. |
| `session_state.py` | Persists workspace path, selected files, expanded folders, instructions text, window geometry to `session.json`. Clean session mode: only workspace + instructions are restored on launch. |
| `recent_folders.py` | Manages a JSON list of the 10 most recently opened folders with existence validation. |

### Core (`core/`)

| File | Description |
|---|---|
| `core/theme.py` | Centralized dark theme: `ThemeColors`, `ThemeFonts`, `ThemeSpacing`, `ThemeRadius`. All views reference these tokens. `apply_theme()` generates and sets the global QSS. |
| `core/logging_config.py` | Rotating file handler (5 × 2 MB), memory-buffered writes, runtime debug toggle, log cleanup. Convenience functions: `log_info`, `log_error`, `log_warning`, `log_debug`. |
| `core/utils/file_scanner.py` | `FileScanner` with global cancellation flag, throttled progress callbacks (200 ms), gitignore + default ignore support, and optional Rust (`scandir-rs`) backend. Also provides `scan_directory_lazy` for on-demand subtree loading. |
| `core/utils/qt_utils.py` | `SignalBridge` (thread-safe main-thread callback scheduling), `DebouncedTimer`, `BackgroundWorker` / `schedule_background` helpers. |
| `core/utils/threading_utils.py` | `TaskManager` with per-view cancellation, global stop event for graceful shutdown, active-view tracking. |

### Components (`components/`)

| File | Description |
|---|---|
| `components/toast_qt.py` | Global toast notification system. `ToastManager` (singleton) stacks up to 5 toasts top-center with glassmorphism, slide + fade animation, and auto-dismiss. Convenience API: `toast_success`, `toast_error`, `toast_warning`, `toast_info`. |

### Configuration (`config/`)

| File | Description |
|---|---|
| `config/paths.py` | Centralized path definitions. App data lives at `$XDG_CONFIG_HOME/synapse-desktop/` (Linux), with automatic migration from the legacy `~/.synapse-desktop/` location. Exports: `APP_DIR`, `BACKUP_DIR`, `LOG_DIR`, `SETTINGS_FILE`, `SESSION_FILE`, `HISTORY_FILE`, `RECENT_FOLDERS_FILE`. |

---

## Key Features

### Context Management
- **Tree selection**: Browse the directory tree and select files/folders to send.
- **Copy modes**:
  - `Context`: Full content of the files.
  - `Smart`: Only signatures/structures (reduces tokens by 70–80%).
  - `Diff Only`: Only git changes (for code review).
<!-- [UPDATED] Added AI Suggest Select feature -->
- **AI Suggest Select**: Write your instructions, and a connected LLM automatically selects the most relevant files from the tree.
- **Prompt Templates**: Built-in and custom templates for common tasks (bug hunting, refactoring, security audit, etc.).
- **Related Files**: Automatically discover and include files that import or are imported by your selection.

### Apply AI Changes
- **OPX format**: AI returns changes in structured XML format.
- **Visual diff**: Preview changes before applying.
- **Auto-backup**: Automatically backs up files before overwriting, allowing undo operations.
<!-- [NEW] -->
- **Continuous Memory**: AI summarizes its actions; Synapse saves this to `.synapse/memory.xml` and injects it into future prompts for multi-session continuity.
- **Error Context**: One-click "Copy Error Context" provides the AI with detailed diagnostics (file content, search pattern, OPX instruction) for self-repair.

---

## Usage Workflow

1. **Select Context** (Context tab)
   - Open your project folder via **Open Folder** or the **Recent** dropdown.
   - Check the required files in the tree. Token counts update in real time.

2. **Copy to AI**
   - Click **Copy Context**, **Copy Smart**, or **Copy Diff Only**.
   - Paste into the AI chat and request the OPX format in return.

3. **Apply Changes** (Apply tab)
   - Copy the XML response from the AI.
   - Paste into the Apply tab → **Preview** → review diffs → **Apply Changes**.
   - If errors occur, click **Copy Error Context** and paste it back to the AI.

---

## Installation

**Requirements**: Python 3.10+, Git (optional, for branch detection and diff context)

### Auto-script (Linux/macOS)
~~~bash
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop
chmod +x start.sh
./start.sh
~~~

### Manual Installation
~~~bash
# 1. Clone the repository
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate the venv
source .venv/bin/activate          # Linux/macOS
.\.venv\Scripts\Activate.ps1       # Windows

# 4. Install dependencies and run
pip install -r requirements.txt
python main_window.py
~~~

<!-- [NEW] Optional performance dependency -->
### Optional: Faster Scanning with scandir-rs

For large projects (10k+ files), install the Rust-based directory scanner for 3–70× faster tree loading:

~~~bash
pip install scandir-rs
~~~

Synapse automatically detects and uses it when available; no configuration needed.

---

<!-- [NEW] Configuration section -->
## Configuration

### App Data Location

Synapse stores all data locally. The directory is resolved in this order:

1. `$XDG_CONFIG_HOME/synapse-desktop/` (if `XDG_CONFIG_HOME` is set)
2. `~/.config/synapse-desktop/` (Linux standard)
3. `~/.synapse-desktop/` (legacy fallback — auto-migrated on first run)

| File / Directory | Purpose |
|---|---|
| `settings.json` | Excluded patterns, toggles, AI provider config |
| `session.json` | Last workspace, instructions text, window size |
| `history.json` | Apply operation history |
| `recent_folders.json` | Last 10 opened folders |
| `logs/app.log` | Rotating log files (5 × 2 MB) |
| `backups/` | Auto-backups before file modifications |

### Environment Variables

| Variable | Description |
|---|---|
| `SYNAPSE_DEBUG` | Set to `1`, `true`, or `yes` to enable DEBUG-level logging to both console and file. |

### AI Context Builder (Settings Tab)

To use the **AI Suggest Select** feature, configure an OpenAI-compatible provider in the Settings tab:

| Field | Example |
|---|---|
| API Key | `sk-...` |
| Base URL | `https://api.openai.com/v1` (OpenAI), `https://openrouter.ai/api/v1` (OpenRouter), `http://localhost:1234/v1` (local LLM) |
| Model | `gpt-4o`, `claude-sonnet-4-20250514`, or any model returned by **Fetch Models** |

### Repository Rules

Files listed in the **Repository Rules** setting (e.g., `.cursorrules`, `prompt.md`) are treated as instruction files. When selected, their content is grouped separately from source code in the generated prompt.

---

## OPX Format

Synapse uses OPX (Overwrite Patch XML) to describe file changes:

~~~xml
<edit file="src/app.py" op="patch">
  <find occurrence="first">
<<<
print("hello")
>>>
  </find>
  <put>
<<<
print("hello world")
>>>
  </put>
</edit>
~~~

Operations: `new` (create file), `patch` (find & replace), `replace` (overwrite completely), `remove` (delete), `move` (rename).

<!-- [NEW] Memory block -->
### Continuous Memory

When **Enable AI Continuous Memory** is on (Settings → Security card), the AI is instructed to include a `<synapse_memory>` block summarizing its actions and next steps. Synapse saves the last 5 memory blocks to `.synapse/memory.xml` in your workspace and injects them into subsequent prompts.

---

## Security and Privacy

- **Paths**: Prompts may contain absolute paths. Enable **Use Relative Paths** in Settings to protect your privacy.
- **Storage**: All data is stored locally (see [Configuration](#configuration) above). No telemetry is collected.
- **Security scan**: Before copying, Synapse scans selected files for API keys and passwords. This can be toggled on/off in Settings.
- **AI API Key**: Stored locally in `settings.json`. It is excluded from the **Export Settings** payload (the `to_safe_dict()` method strips it).

---

<!-- [NEW] Development guidelines -->
## Development Guidelines

### Project Structure

~~~
Synapse-Desktop/
├── main_window.py          # App entry point
├── config/                 # Paths, model config
├── core/                   # Infrastructure (theme, logging, scanning, tokenization)
│   └── utils/              # Qt helpers, threading, file utilities
├── services/               # Business logic (session, cache, tokens, AI worker)
├── views/                  # Tab views (Context, Apply, History, Logs, Settings)
│   └── context/            # ContextView mixins (_ui_builder, _copy_actions, etc.)
├── components/             # Reusable Qt widgets (toast, diff viewer, toggle switch)
├── assets/                 # Fonts, icons, images
└── tests/                  # Unit and UI tests
~~~

### Code Style

- **Type hints** on all public function signatures.
- **Docstrings** in Vietnamese comments are acceptable (legacy); new code should prefer English.
- **Thread safety**: Always use `threading.Lock` or `SignalBridge` when updating shared state. Never call Qt widget methods from background threads directly.
- **Imports**: Use lazy imports inside functions when needed to avoid circular dependencies (see `main_window.py` for examples).

### Running Tests

~~~bash
python -m pytest tests/ -v
~~~

### Commit Conventions

The project uses conventional commits:

- `feat:` — New feature
- `fix:` — Bug fix
- `refactor:` — Code restructuring without behavior change
- `docs:` — Documentation only
- `test:` — Adding or updating tests

---

## Troubleshooting

<!-- [UPDATED] Expanded troubleshooting -->

**"Module not found"**: Ensure your venv is activated and dependencies are installed.
~~~bash
source .venv/bin/activate
pip install -r requirements.txt
~~~

**No data in Diff Only mode**: Ensure the project is a git repository with uncommitted changes.
~~~bash
git status
git diff
~~~

**Apply failed "pattern not found"**: Ask the AI to provide a longer, more unique code block within the `<find>` tag. The search pattern must exactly match the current file content (after any prior patches in the same session).

**Cascade failures during Apply**: When multiple `<edit>` blocks target the same file, a successful early patch changes the file content, causing later patches to fail because their `<find>` patterns no longer match. Use **Copy Error Context** to send detailed diagnostics back to the AI.

**High memory usage warning**: Click the 🧹 button in the top bar to clear token caches and trigger garbage collection. For very large projects (50k+ files), consider using `.gitignore` or excluded patterns to reduce the scanned tree.

**Token counts seem wrong after changing model**: The token cache is model-specific. Switch models in Settings and the cache will be automatically cleared and recounted.

**Slow directory scanning**: Install `scandir-rs` (`pip install scandir-rs`) for significantly faster scanning, especially on Windows.

**Logs not appearing**: Check that the log directory exists and is writable: `~/.config/synapse-desktop/logs/`. Enable **Debug Mode** in the Logs tab for verbose output.

---

## Acknowledgements

Inspired by:

- **[Repomix](https://github.com/yamadashy/repomix)**
- **[Overwrite](https://github.com/mnismt/overwrite)**
- **[PasteMax](https://github.com/kleneway/pastemax)**

## License

MIT © HaoNgo232
