# Synapse Desktop
A lightweight AI-assisted code editing tool for desktop.

**Synapse Desktop** captures AI context efficiently for your desktop. Built with Python & Flet, it synthesizes the best workflows from the **Overwrite** extension and high-performance logic from **Pastemax** into a unified, standalone application.

- **Core Concept & Workflow**: Adapted from the original [Overwrite](https://github.com/mnismt/overwrite) VS Code extension by mnismt.
- **Advanced Engine**: High-performance file processing, concurrency logic, and language detection algorithms ported and adapted from [Pastemax](https://github.com/kleneway/pastemax) by kleneway.

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

## Features

### Core Features
- **Copy Context** - Select files and generate LLM-ready prompts in multiple formats (XML, Markdown, JSON, Plain Text)
- **Copy Tree Map** - Copy only file structure without contents (saves tokens)
- **Apply OPX** - Paste LLM responses in OPX format and apply changes to your codebase
- **Preview Changes** - Visual diff preview with +lines/-lines before applying

### File Tree
- **Collapsible File Tree** - Navigate large codebases with expand/collapse folders
- **Search/Filter** - Quick search to find files in large projects
- **Token Counter** - Track token usage per file and folder
- **Gitignore Support** - Respect `.gitignore` patterns automatically
- **Excluded Folders** - Configure custom exclusion patterns
- **Ignore & Undo** - Quickly add files to ignore list and undo if needed

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
- **Security Check** - Scan for secrets (API keys, tokens) before copying to prevent leaks (powered by detect-secrets)

## Usage

### 1. Copy Context

1. Click **Open Folder** to select your project
2. Use the file tree to select files (click checkboxes)
3. Enter instructions in the text area
4. Select your preferred **Output Format** (XML, Markdown, JSON, Plain Text)
5. Click **Copy Context** (for basic context) or **Copy + OPX** (for optimization instructions)
6. Paste into your LLM chat

### 2. Apply Changes

1. Get OPX response from LLM
2. Go to **Apply** tab
3. Paste the OPX XML response (or click **Paste** button)
4. Click **Preview** to see changes with visual diff
5. Click **Apply Changes** to execute
6. Use **View Backups** → **Undo Last Apply** if you need to revert

### 3. History

1. Go to **History** tab to see all previous operations
2. Click an entry to view details
3. Use **Copy OPX** to copy the original OPX
4. Use **Re-apply** to send OPX to Apply tab

### 4. Settings

- **Excluded Folders** - Add patterns like `node_modules`, `dist`
- **Presets** - Quick load common patterns (Python, Node.js, Rust, etc.)
- **Respect .gitignore** - Toggle to include/exclude gitignored files
- **Enable Security Check** - Scan for secrets before copying (prevents accidental API key leaks)
- **Session** - Clear saved workspace and selections


## Project Structure

```text
synapse-desktop/
├── main.py                 # App entry point
├── requirements.txt        # Python dependencies
├── start.sh                # Linux start script
├── build-appimage.sh       # AppImage build script
│
├── core/                   # Business logic
│   ├── opx_parser.py       # OPX XML parser
│   ├── opx_instruction.py  # OPX system prompt for LLMs
│   ├── file_actions.py     # File operations (create, modify, delete)
│   ├── file_utils.py       # File tree scanning with language detection
│   ├── token_counter.py    # Token counting with tiktoken
│   ├── prompt_generator.py # Generate LLM prompts
│   ├── tree_map_generator.py # Tree-only prompts
│   ├── language_utils.py   # Language ID for LLMs
│   ├── security_check.py   # Secret scanning (powered by detect-secrets)
│   ├── theme.py            # Dark mode OLED theme
│   └── logging_config.py   # Logging setup
│
├── components/             # Reusable UI components
│   ├── file_tree.py        # File tree with search
│   ├── diff_viewer.py      # Visual diff display
│   └── token_stats.py      # Token statistics panel
│
├── views/                  # App views/tabs
│   ├── context_view.py     # File selection tab
│   ├── apply_view.py       # Apply changes tab
│   ├── history_view.py     # History tab
│   ├── logs_view.py        # Logs tab
│   └── settings_view.py    # Settings tab
│
├── services/               # Background services
│   ├── clipboard_utils.py  # Clipboard operations
│   ├── history_service.py  # History storage
│   ├── session_state.py    # Session persistence
│   ├── recent_folders.py   # Recent folders
│   ├── settings_manager.py # Settings persistence
│   ├── memory_monitor.py   # Memory tracking
│   ├── token_display.py    # Token cache service
│   ├── preview_analyzer.py # Diff analysis
│   └── error_context.py    # Error context for AI
│
├── tests/                  # Unit tests
│   ├── test_opx_parser.py
│   ├── test_diff_viewer.py
│   ├── test_recent_folders.py
│   └── test_session_state.py
│
├── assets/                 # Static assets
│   └── icon.png
│
└── docs/ai/                # AI DevKit documentation
    ├── requirements/
    ├── design/
    ├── planning/
    ├── implementation/
    ├── testing/
    ├── deployment/
    └── monitoring/
```

## Development

```bash
# Run tests
pytest tests/ -v

# Run with hot reload (development)
flet run main.py -r

# Enable debug logging
OVERWRITE_DEBUG=1 python main.py
```

## Data Storage

Application data is stored in `~/.synapse-desktop/`:

| File | Purpose |
|------|---------|
| `settings.json` | Excluded folders and model preferences |
| `recent_folders.json` | Recently opened folders |
| `session.json` | Last session state (workspace, selections) |
| `history.json` | Apply operation history |
| `logs/app.log` | Application logs |
| `backups/` | File backups before modifications |

## Acknowledgements & Inspirations

While Synapse Desktop is a standalone project, I have learned and adapted valuable concepts from the open-source community:

### Pastemax
- **Advanced Language Detection**: Adapted from Pastemax's extensive language map to ensure perfect syntax highlighting for LLMs.
- **Concurrent Processing Pattern**: Adapted their global cancellation flag pattern (`isLoadingDirectory`) for responsive file scanning without race conditions.
- **Dashboard Aesthetics**: Adopted the modern "Dashboard Metrics" style for clear and beautiful token statistics.
- **Smart File Filtering**: Implemented robust exclusion logic similar to their ignore management.

### Repomix
- **Security Check Architecture**: Studied their secret scanning workflow design and integration patterns.
- **Secret Detection Approach**: Learned from their use of @secretlint for comprehensive secret detection.
- **User Experience**: Adopted the concept of warning dialogs with detailed secret information for transparency.

I believe in open collaboration and learning from the best to create better tools for everyone.

See [NOTICES.md](NOTICES.md) for full license details of adapted components.

## License
MIT License