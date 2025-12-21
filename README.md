# Synapse Desktop
A lightweight AI-assisted code editing tool for desktop.

**Synapse Desktop** is a desktop application designed to capture code context for LLMs. Built with Python & Flet, it reimplement the **Overwrite** extension workflow as a standalone tool, incorporating processing logic adapted from **Pastemax**.

- **Workflow**: Ported from the [Overwrite](https://github.com/mnismt/overwrite) VS Code extension.
- **Engine**: File processing and concurrency utility functions adapted from [Pastemax](https://github.com/kleneway/pastemax).

## Getting Started

### Prerequisites

- Python 3.10+
- pip

### Installation

#### Linux

```bash
# Clone the repository
git clone https://github.com/HaoNgo232/synapse-desktop.git
cd synapse-desktop

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
./start.sh
# OR
python main.py
```

### Build from Source

To build a standalone AppImage (Linux):

```bash
# Ensure dependencies are installed
pip install pyinstaller

# Run build script
./build-appimage.sh

# The AppImage will be in build/Synapse-Desktop-1.0.0-x86_64.AppImage
```

---

## Why "Synapse"?

The name represents the vital connection between your codebase and AI intelligence. Just like a synapse transmits signals between neurons, **Synapse Desktop** transmits precise code context to LLMs and applies their intelligence back to your project.

## Motivation

I created **Synapse Desktop** to support my thesis work, as the original tool I relied on was no longer maintained. I am sharing this project in the hope that it can be useful to others who need a simple, reliable way to prepare code context for LLMs.

## Features

### Core Features
- **Copy Context** - Select files and generate LLM-ready prompts in multiple formats
- **Copy Tree Map** - Copy only file structure without contents (saves tokens)
- **Copy Smart Context** - Extract code signatures and docstrings using Tree-sitter (reduces tokens while preserving structure)
- **Apply OPX** - Paste LLM responses in OPX format and apply changes to your codebase
- **Preview Changes** - Visual diff preview with +lines/-lines before applying

### Output Formats
Choose from multiple output formats optimized for different use cases:
- **XML** (Default) - Structured format optimized for Claude & GPT, reduces hallucination
- **Markdown** - Code blocks with syntax highlighting, human-readable
- **JSON** - Pure data format for automation and JSON Mode models
- **Plain Text** - Minimal formatting, saves the most tokens

### File Tree
- **Collapsible File Tree** - Navigate large codebases with expand/collapse folders
- **Search/Filter** - Quick search to find files in large projects
- **Token Counter** - Track token usage per file and folder
- **Line Counter** - Display line counts for files and folders
- **Gitignore Support** - Respect `.gitignore` patterns automatically
- **Excluded Folders** - Configure custom exclusion patterns
- **Ignore & Undo** - Quickly add files to ignore list and undo if needed
- **Auto-refresh** - Automatically detect file changes and update tree

### Smart Context (Tree-sitter)
Extract code structure instead of full content to save tokens while preserving understanding.

**Supported Languages:**
- Python (.py, .pyw)
- JavaScript (.js, .jsx, .mjs, .cjs)
- TypeScript (.ts, .tsx, .mts, .cts)
- Rust (.rs)
- Go (.go)
- Java (.java)
- C# (.cs)
- C (.c, .h)
- C++ (.cpp, .hpp, .cc, .cxx)
- Ruby (.rb, .rake, .gemspec)
- PHP (.php, .phtml)
- Swift (.swift)
- CSS (.css, .scss, .less)
- Solidity (.sol)

### Git Integration
- **Include Git Diff** - Optionally include working tree and staged changes in context
- **Include Git Log** - Add recent commit history for better understanding
- **Toggle in Settings** - Enable/disable git context as needed

### Security
- **Secret Detection** - Scan for API keys, tokens, and credentials before copying (powered by detect-secrets)
- **Warning Dialog** - Review detected secrets with redacted previews
- **Toggle in Settings** - Enable/disable security scanning

### History & Backup
- **History Tab** - View all previous OPX operations with success/fail stats
- **Auto Backup** - Automatic file backups before modifications
- **Undo Last Apply** - Rollback the last batch of changes
- **Re-apply from History** - Copy or re-apply previous OPX operations

### Developer Tools
- **Logs Tab** - View application logs for debugging
- **Debug Mode** - Enable verbose logging when needed
- **Memory Monitor** - Track memory usage and cache stats
- **Session Restore** - Automatically restore workspace and selections on restart

### Supported LLM Models
Token stats panel supports context limits for popular models:
- **OpenAI**: GPT-5.1, GPT-5.1 Thinking (200k context)
- **Anthropic**: Claude Opus 4.5, Claude Sonnet 4.5, Claude Haiku 4.5 (200k context)
- **Google**: Gemini 3 Pro, Gemini 3 Flash (1M context)
- **DeepSeek**: DeepSeek V3.1, DeepSeek R1 (128k context)
- **xAI**: Grok 4 (256k context)
- **Alibaba**: Qwen3 235B (256k context)
- **Meta**: Llama 4 Scout (10M context)

## Usage

### 1. Copy Context

1. Click **Open Folder** to select your project
2. Use the file tree to select files (click checkboxes)
3. Enter instructions in the text area
4. Select your preferred **Output Format** (XML, Markdown, JSON, Plain Text)
5. Click **Copy Context** (for basic context) or **Copy + OPX** (for optimization instructions)
6. Paste into your LLM chat

### 2. Copy Smart Context

1. Select files containing code you want to analyze
2. Click **Copy Smart** to extract only code signatures and docstrings
3. Smart Context uses Tree-sitter to parse and extract structure
4. Significantly reduces token count while preserving code understanding

### 3. Apply Changes

1. Get OPX response from LLM
2. Go to **Apply** tab
3. Paste the OPX XML response (or click **Paste** button)
4. Click **Preview** to see changes with visual diff
5. Click **Apply Changes** to execute
6. Use **View Backups** → **Undo Last Apply** if you need to revert

### 4. History

1. Go to **History** tab to see all previous operations
2. Click an entry to view details
3. Use **Copy OPX** to copy the original OPX
4. Use **Re-apply** to send OPX to Apply tab

### 5. Settings

- **Excluded Folders** - Add patterns like `node_modules`, `dist`
- **Presets** - Quick load common patterns (Python, Node.js, Rust, Go, Java, General)
- **Respect .gitignore** - Toggle to include/exclude gitignored files
- **Enable Security Check** - Scan for secrets before copying
- **Include Git Diff/Log** - Add git changes to context
- **Session** - Clear saved workspace and selections
- **Export/Import** - Share settings via JSON


## Project Structure

```text
synapse-desktop/
├── main.py                 # App entry point
├── requirements.txt        # Python dependencies
├── start.sh                # Linux start script
├── build-appimage.sh       # AppImage build script
│
├── assets/                 # Static assets
│   └── icon.png
│
├── components/             # Reusable UI components
│   ├── file_tree.py        # File tree with search, tokens, lines
│   ├── diff_viewer.py      # Visual diff display
│   └── token_stats.py      # Token statistics panel
│
├── config/                 # Configuration modules
│   ├── model_config.py     # LLM model definitions
│   ├── output_format.py    # Output format registry (XML, MD, JSON, Plain)
│   └── paths.py            # Application paths (~/.synapse-desktop/)
│
├── core/                   # Business logic
│   ├── constants/          # File patterns, binary extensions
│   │   └── file_patterns.py
│   │
│   ├── smart_context/      # Tree-sitter code parsing
│   │   ├── config.py       # Language configurations
│   │   ├── loader.py       # Language loader with caching
│   │   ├── parser.py       # Smart parse implementation
│   │   └── queries/        # Tree-sitter queries per language
│   │       ├── python.py
│   │       ├── javascript.py
│   │       ├── typescript.py
│   │       └── ... (14 languages)
│   │
│   ├── utils/              # Utility modules
│   │   ├── file_utils.py   # File tree scanning
│   │   ├── file_scanner.py # Async scanner with progress
│   │   ├── git_utils.py    # Git diff/log operations
│   │   ├── language_utils.py # Language detection
│   │   ├── ui_utils.py     # Safe UI updates
│   │   ├── threading_utils.py # Thread management
│   │   ├── batch_updater.py # Debounced UI updates
│   │   └── async_queue.py  # Async task queue
│   │
│   ├── opx_parser.py       # OPX XML parser
│   ├── opx_instruction.py  # OPX system prompt for LLMs
│   ├── file_actions.py     # File operations (create, modify, delete)
│   ├── token_counter.py    # Token counting with tiktoken
│   ├── prompt_generator.py # Generate LLM prompts (multi-format)
│   ├── tree_map_generator.py # Tree-only prompts
│   ├── security_check.py   # Secret scanning with detect-secrets
│   ├── theme.py            # Dark mode OLED theme
│   └── logging_config.py   # Logging setup with rotation
│
├── services/               # Background services
│   ├── clipboard_utils.py  # Clipboard operations
│   ├── file_watcher.py     # Auto-refresh on file changes
│   ├── history_service.py  # History storage
│   ├── session_state.py    # Session persistence
│   ├── recent_folders.py   # Recent folders
│   ├── settings_manager.py # Settings persistence
│   ├── memory_monitor.py   # Memory tracking
│   ├── token_display.py    # Token cache service
│   ├── line_count_display.py # Line count service
│   ├── preview_analyzer.py # Diff analysis
│   └── error_context.py    # Error context for AI
│
├── views/                  # App views/tabs
│   ├── context_view.py     # File selection tab
│   ├── apply_view.py       # Apply changes tab
│   ├── history_view.py     # History tab
│   ├── logs_view.py        # Logs tab
│   └── settings_view.py    # Settings tab
│
├── stubs/                  # Type stubs for tree-sitter
│   └── tree_sitter_*/      # Per-language type hints
│
├── tests/                  # Unit tests
│   ├── test_opx_parser.py
│   ├── test_prompt_generator.py
│   ├── test_diff_viewer.py
│   ├── test_token_counter.py
│   ├── test_git_utils.py
│   ├── test_file_actions_security.py
│   └── ...
│
└── docs/                   # Documentation
```

## Development

```bash
# Run tests
pytest tests/ -v

# Run with hot reload (development)
flet run main.py -r

# Enable debug logging
SYNAPSE_DEBUG=1 python main.py

# Type checking
pyrefly check
```

## Data Storage

Application data is stored in `~/.synapse-desktop/`:

| File | Purpose |
|------|---------|
| `settings.json` | Excluded folders, model preferences, security settings |
| `recent_folders.json` | Recently opened folders |
| `session.json` | Last session state (workspace, selections, window size) |
| `history.json` | Apply operation history |
| `logs/app.log` | Application logs (with rotation) |
| `backups/` | File backups before modifications |

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `SYNAPSE_DEBUG` | Set to `1` to enable verbose debug logging |

## Acknowledgements & Inspirations

While Synapse Desktop is a standalone project, I have learned and adapted valuable concepts from the open-source community:

### Overwrite
- **Foundation**: The entire application concept, core workflow, and "Copy Context" + "Apply OPX" cycle are directly ported/adapted from the original [Overwrite](https://github.com/mnismt/overwrite) VS Code extension.
- **OPX Protocol**: It uses the same OPX (Overwrite Protocol XML) format and system prompts to ensure compatibility with LLMs optimized for this pattern.
- **UI UX**: The clean, minimal interface and file selection experience are reimplemented to provide the familiar Overwrite feel on desktop.

### Pastemax
- **Advanced Language Detection**: Adapted from Pastemax's extensive language map to ensure perfect syntax highlighting for LLMs.
- **Concurrent Processing Pattern**: Adapted their global cancellation flag pattern (`isLoadingDirectory`) for responsive file scanning without race conditions.
- **Dashboard Aesthetics**: Adopted the modern "Dashboard Metrics" style for clear and beautiful token statistics.
- **Smart File Filtering**: Implemented robust exclusion logic similar to their ignore management.

### Repomix
- **Security Check Architecture**: Studied their secret scanning workflow design and integration patterns.
- **Secret Detection Approach**: Learned from their use of @secretlint for comprehensive secret detection.
- **User Experience**: Adopted the concept of warning dialogs with detailed secret information for transparency.
- **Output Format Registry**: Inspired by their extensible output format configuration.

I built this project independently, but it stands on the shoulders of these excellent open-source tools. I studied their logic and adapted their best ideas to creates a unified experience.

See [NOTICES.md](NOTICES.md) for full license details of adapted components.

## License
MIT License