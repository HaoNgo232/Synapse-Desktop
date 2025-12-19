# Overwrite Desktop

A lightweight desktop application for AI-assisted code editing.

## Getting Started

### Prerequisites

- Python 3.10+
- pip

### Installation

#### Linux

```bash
# Clone the repository
git clone https://github.com/HaoNgo232/overwrite-desktop.git
cd overwrite-desktop

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

#### Windows

```powershell
# Clone the repository
git clone https://github.com/HaoNgo232/overwrite-desktop.git
cd overwrite-desktop

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Build from Source

To build a standalone AppImage (Linux):

```bash
# Ensure dependencies are installed
pip install pyinstaller

# Run build script
./build-appimage.sh

# The AppImage will be in build/Overwrite-Desktop-1.0.0-x86_64.AppImage
```

---

## Why This Project?

The original [Overwrite VS Code](https://github.com/mnismt/overwrite) extension has not been updated for a long time and no longer works on the latest VS Code versions or its forks (Cursor, Windsurf, etc.).

This desktop version was created to:

- **Independence** - No dependency on VS Code API updates or extension compatibility issues
- **Stability** - Works reliably without being affected by IDE updates
- **Lightweight** - Smaller footprint than Electron-based VS Code extensions
- **Long-term usability** - Can be used for years without maintenance concerns

## Features

### Core Features
- **Copy Context** - Select files and generate LLM-ready prompts with file maps and contents
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

## Usage

### 1. Copy Context

1. Click **Open Folder** to select your project
2. Use the file tree to select files (click checkboxes)
3. Enter instructions in the text area
4. Click **Copy Context** or **Copy + OPX**
5. Paste into your LLM chat

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
- **Session** - Clear saved workspace and selections

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+C` | Copy Context |
| `Ctrl+Shift+O` | Copy Context + OPX |
| `Ctrl+R` | Refresh file tree |
| `Ctrl+F` | Focus search field |
| `Escape` | Clear search |

## Project Structure

```text
overwrite-desktop/
├── main.py                 # App entry point
├── requirements.txt        # Python dependencies
├── start.sh                # Linux start script
├── build-appimage.sh       # AppImage build script
│
├── core/                   # Business logic
│   ├── opx_parser.py       # OPX XML parser
│   ├── opx_instruction.py  # OPX system prompt for LLMs
│   ├── file_actions.py     # File operations (create, modify, delete)
│   ├── file_utils.py       # File tree scanning
│   ├── token_counter.py    # Token counting with tiktoken
│   ├── prompt_generator.py # Generate LLM prompts
│   ├── tree_map_generator.py # Tree-only prompts
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

## Dependencies

| Package | Purpose |
|---------|---------|
| `Flet` | Cross-platform UI framework |
| `tiktoken` | Token counting (OpenAI) |
| `pathspec` | Gitignore parsing |
| `pyperclip` | Clipboard access |
| `psutil` | Memory monitoring |

## Data Storage

Application data is stored in `~/.overwrite-desktop/`:

| File | Purpose |
|------|---------|
| `settings.json` | Excluded folders and preferences |
| `recent_folders.json` | Recently opened folders |
| `session.json` | Last session state (workspace, selections) |
| `history.json` | Apply operation history |
| `logs/app.log` | Application logs |
| `backups/` | File backups before modifications |

## License
MIT License