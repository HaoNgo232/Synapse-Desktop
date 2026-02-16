# Synapse Desktop

Synapse Desktop is a desktop application that helps you:

1. **Select files/folders in a project** → **package them into structured prompts** to paste into ChatGPT/Claude/Gemini/DeepSeek (web).
2. **Receive XML (OPX) responses** from AI → **preview diffs and apply changes** to your codebase (with backup/undo).

## Key Features

- **Controlled Context Selection**: Browse the directory tree, check the files/folders you want to send.
- **Multiple Copy Modes**:
  - **Context**: Send full content of selected files.
  - **Smart**: Send signatures/functions/classes/docstrings (reduces tokens, ideal for review/planning).
  - **Diff Only**: Send only git changes (staged + unstaged) for reviews or PRs.
- **Apply AI Changes**:
  - Paste **OPX XML** → view **visual diff** → Apply/Reject.
  - **Auto-backup** before modification, allows for easy undo.
  - **Fuzzy matching** to find the correct patch location even if AI formatting is slightly off.

## Requirements

- **Python 3.10+**
- (Recommended) **git** for Diff Only mode
- OS: Windows / macOS / Linux

---

## Installation & Running (Quick Start)

### 1) Clone repo

```bash
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop
```

### 2) Option A — Run with script (Linux/macOS)

```bash
chmod +x start.sh
./start.sh
```

### 2) Option B — Manual Setup (Windows/macOS/Linux)

#### Create venv + install dependencies

```bash
python -m venv .venv
```

Activate venv:

- **Linux/macOS**

  ```bash
  source .venv/bin/activate
  ```

- **Windows (PowerShell)**

  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```

Install requirements and run the app:

```bash
pip install -r requirements.txt
python main_window.py
```

---

## Quick Usage (3 Steps)

### Step 1 — Select Context

- Open the **Context** tab
- Choose project folder
- Check files/folders to send to AI

### Step 2 — Copy to AI (web)

- Select **Copy Context** or **Copy Smart** (fewer tokens)
- Paste into ChatGPT/Claude/Gemini/DeepSeek and chat as usual

### Step 3 — Apply AI Changes

- Ask the AI to return **OPX XML**
- Copy the XML → paste into the **Apply** tab
- Preview diff → Apply (or Reject)

---

## What is OPX (Overwrite Patch XML)?

Synapse uses OPX to describe file changes in an automatically applicable format.

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

Common `op` types:

- `new`: create a new file
- `patch`: find & replace a code block
- `replace`: overwrite entire file
- `remove`: delete a file
- `move`: rename/move a file

---

## Data Storage (local)

App data is stored locally at: `~/.synapse-desktop/`

- `settings.json`: user configuration
- `session.json`: last workspace & session state
- `history.json`: operation history
- `backups/`: automatic backups before each apply

---

## Security & Privacy (read before sharing prompts)

- Prompts/previews may contain **absolute paths** (e.g., `C:\Users\<name>\...`), which might reveal your **username/machine structure** when pasted onto web chats.
- If you plan to share outputs or post to public issues, use **relative paths** (default: relative, can be toggled in the Settings tab) or manually redact sensitive information before sending.

---

## Build AppImage (Linux)

```bash
pip install pyinstaller
./build-appimage.sh
```

---

## Quick Troubleshooting

- **Module not found**: Ensure you have run `pip install -r requirements.txt` within the correct venv.
- **Diff Only has no data**: Check if the project is a git repo and has staged/unstaged changes.
- **Apply fails / patch mismatch**: Try asking the AI for OPX with a longer `<find>` block (more context lines).

---

## Acknowledgements

Inspired by:

- **[Repomix](https://github.com/yamadashy/repomix)** — XML context packing format
- **[Overwrite](https://github.com/mnismt/overwrite)** — OPX patch protocol
- **[PasteMax](https://github.com/kleneway/pastemax)** — file tree UI patterns

---

## License

MIT © HaoNgo232
