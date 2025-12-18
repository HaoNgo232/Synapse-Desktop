# Overwrite Desktop

A lightweight desktop application for AI-assisted code editing.

## Why This Project?

The original [Overwrite VS Code Extension](https://marketplace.visualstudio.com/items?itemName=peymanmortazavi.overwrite) is no longer maintained and has stopped working on recent versions of VS Code and its forks (Cursor, Windsurf, etc.).

This desktop version was created to:

- **Independence** - No dependency on VS Code API updates or extension compatibility issues
- **Stability** - Works reliably without being affected by IDE updates
- **Lightweight** - Smaller footprint than Electron-based VS Code extensions
- **Long-term usability** - Can be used for years without maintenance concerns

## Features

- **Copy Context** - Select files and generate LLM-ready prompts with file maps and contents
- **Apply OPX** - Paste LLM responses in OPX format and apply changes to your codebase
- **Collapsible File Tree** - Navigate large codebases with expand/collapse folders
- **Token Counter** - Track token usage before sending to LLM
- **Gitignore Support** - Respect `.gitignore` patterns automatically
- **Excluded Folders** - Configure custom exclusion patterns

## Screenshots

_Coming soon_

---

## Installation

### Prerequisites

- Python 3.10+
- pip

### Linux

```bash
# Clone the repository
git clone https://github.com/yourusername/overwrite-desktop.git
cd overwrite-desktop

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Windows

```powershell
# Clone the repository
git clone https://github.com/yourusername/overwrite-desktop.git
cd overwrite-desktop

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

---

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
3. Paste the OPX XML response
4. Click **Preview** to see changes
5. Click **Apply Changes** to execute

### 3. Settings

- **Excluded Folders** - Add patterns like `node_modules`, `dist`
- **Respect .gitignore** - Toggle to include/exclude gitignored files

---

## OPX Format

OPX (Overwrite Patch XML) is the format used for code changes:

```xml
<!-- Create new file -->
<edit file="src/utils.py" op="new">
  <put>
<<<
def hello():
    return "Hello, World!"
>>>
  </put>
</edit>

<!-- Modify existing file -->
<edit file="src/main.py" op="patch">
  <find>
<<<
old_code()
>>>
  </find>
  <put>
<<<
new_code()
>>>
  </put>
</edit>

<!-- Replace entire file -->
<edit file="src/config.py" op="replace">
  <put>
<<<
NEW_CONFIG = True
>>>
  </put>
</edit>

<!-- Delete file -->
<edit file="src/old.py" op="remove"/>

<!-- Rename/Move file -->
<edit file="src/old.py" op="move">
  <to file="src/new.py"/>
</edit>
```

---

## Project Structure

```
overwrite-desktop/
├── main.py              # App entry point
├── requirements.txt     # Python dependencies
├── core/                # Business logic
│   ├── opx_parser.py   # OPX XML parser
│   ├── file_actions.py # File operations
│   ├── file_utils.py   # File tree scanning
│   ├── token_counter.py# Token counting
│   └── prompt_generator.py
├── views/               # UI views
│   ├── context_view.py # File selection tab
│   ├── apply_view.py   # Apply changes tab
│   └── settings_view.py
└── tests/               # Unit tests
```

---

## Development

```bash
# Run tests
pytest tests/ -v

# Run with hot reload (development)
flet run main.py -r
```

---

## Dependencies

- [Flet](https://flet.dev/) - Cross-platform UI framework
- [tiktoken](https://github.com/openai/tiktoken) - Token counting
- [pathspec](https://github.com/cpburnz/python-pathspec) - Gitignore parsing
- [pyperclip](https://github.com/asweigart/pyperclip) - Clipboard access

---

## License

MIT License
