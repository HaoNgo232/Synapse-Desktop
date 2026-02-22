# Synapse Desktop

A desktop tool for managing AI coding workflows. Select files from your project, package them into structured prompts, paste into any AI chat (ChatGPT, Claude, Gemini, DeepSeek), then apply the AI's response back to your codebase.

## What It Does

**Context → AI → Apply**, in three steps:

1. **Select files** in the Context tab — browse the directory tree, check files you want to include.
2. **Copy a prompt** to clipboard — paste it into your AI chat of choice.
3. **Apply changes** — paste the AI's OPX XML response in the Apply tab, preview diffs, and apply.

## Copy Modes

- **Copy + OPX** — Full file contents + OPX formatting instructions so the AI responds in a patchable format.
- **Copy Context** — Full file contents in XML/JSON/Plain format, without OPX instructions.
- **Copy Smart** — Code signatures, function/class definitions, and relationships only. Significantly fewer tokens.
- **Copy Diff Only** — Git staged + unstaged changes only. Useful for code reviews or PR descriptions.
- **Copy Tree Map** — Project directory structure only, no file contents.

## Features

- **Token counting** — Real-time token count per file and total, with model-specific tokenizers (Claude, GPT, etc.).
- **Security scanning** — Detects API keys, passwords, and secrets before copying. Warns before you accidentally send credentials to an AI chat.
- **Git integration** — Optionally includes recent git diff and log in the prompt.
- **Related files** — Auto-selects imported/dependent files at configurable depth (1–5 levels).
- **File watcher** — Watches for file system changes and refreshes the tree automatically.
- **Prompt templates** — Built-in and custom prompt templates for common tasks.
- **Instruction history** — Saves recent instructions for quick reuse.
- **Apply with preview** — Visual diff viewer before applying changes. Auto-backup before modification.
- **Fuzzy matching** — Finds patch locations even when AI formatting is slightly off.
- **Error context** — When apply fails, copies detailed error context (including current file content and failed search patterns) for the AI to fix.
- **Operation history** — Browse, re-apply, or copy OPX from past operations.
- **Workspace config** — Excluded patterns (with presets for Node.js, Python, Java, Go), .gitignore support, relative path output.

## Requirements

- Python 3.10+
- Git (optional, for Diff Only mode and git integration)
- OS: Linux, macOS, Windows

## Installation

```bash
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop
python -m venv .venv

# Activate venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
# .\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
python main_window.py
```

On Linux/macOS, you can also run:

```bash
chmod +x start.sh
./start.sh
```

## OPX Format

Synapse uses OPX (Overwrite Patch XML) to describe file changes. When you use "Copy + OPX", the AI is instructed to respond in this format so changes can be applied automatically.

Operations:

- `new` — Create a new file
- `patch` — Find and replace a code region
- `replace` — Overwrite entire file contents
- `remove` — Delete a file
- `move` — Rename or move a file

Example:

```xml
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
```

## Data Storage

All data is stored locally at `~/.synapse-desktop/`:

- `settings.json` — User configuration
- `session.json` — Last workspace and window state
- `history.json` — Operation history
- `recent_folders.json` — Recently opened workspaces
- `backups/` — Automatic backups before each apply

## Privacy Note

Prompts may contain absolute file paths (e.g., `/home/username/...` or `C:\Users\username\...`) which could reveal your username or directory structure. Use relative paths (enabled by default in Settings) or review the prompt before sharing publicly.

## Build AppImage (Linux)

```bash
pip install pyinstaller
./build-appimage.sh
```

## Troubleshooting

- **Module not found** — Make sure you ran `pip install -r requirements.txt` in the activated venv.
- **Diff Only shows nothing** — The project must be a git repo with staged or unstaged changes.
- **Apply fails / patch mismatch** — Ask the AI to include more context lines in the `<find>` block. The error context (copied via "Copy Error Context" button) gives the AI enough information to fix its own patches.
- **Token count shows 0** — Check Settings to ensure a model is selected. The tokenizer downloads on first use and requires internet.

## Acknowledgements

Inspired by:

- [Repomix](https://github.com/yamadashy/repomix) — XML context packing format
- [Overwrite](https://github.com/mnismt/overwrite) — OPX patch protocol
- [PasteMax](https://github.com/kleneway/pastemax) — File tree UI patterns

## License

MIT © HaoNgo232
