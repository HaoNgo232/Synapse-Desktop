# Synapse Desktop

**Copy your codebase into any AI chat — with full control over what gets sent.**

Synapse Desktop is a lightweight desktop app that lets you select files from any project, format them as a structured prompt, and paste into ChatGPT / Claude / Gemini / DeepSeek. When the AI replies with code changes, paste them back and Synapse applies the diff for you.

```
Your Code  ──→  [ Synapse ]  ──→  Any Web AI  ──→  [ Synapse ]  ──→  Applied Changes
              select & copy        paste & chat       paste back        review & apply
```

---

## Quick Start

```bash
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop

# Option 1: one-command startup script
chmod +x start.sh
./start.sh

# Option 2: manual setup

python3 -m venv .venv
source .venv/bin/activate      # Linux/Mac
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
python3 main_window.py
```

> **Requires:** Python 3.10+

---

## 60-Second Flow

1. Open your project in **Context** tab.
2. Check files/folders you want AI to see.
3. Click **Copy Context** (or **Copy Smart** for fewer tokens).
4. Paste prompt into ChatGPT / Claude / Gemini / DeepSeek.
5. Copy AI XML response, paste into **Apply** tab.

---

## How It Works (3 Steps)

### Step 1 — Select & Copy

Open a project folder. Check the files you need. Click **Copy**.

| Copy Mode          | What It Does                                                   | Best For                                          |
| ------------------ | -------------------------------------------------------------- | ------------------------------------------------- |
| **Copy Context**   | Full source code, wrapped in XML/Markdown/JSON                 | Implementation tasks, bug fixing                  |
| **Copy Smart**     | Signatures & docstrings only (bodies stripped via Tree-sitter) | Architecture review, planning (~70% fewer tokens) |
| **Copy Diff Only** | Only git changes (staged + unstaged)                           | Code review, PR descriptions                      |

**Extras:**
- **Select Related** — auto-selects imported files using dependency graph (Python/JS/TS)
- **Secret Scan** — warns before you copy API keys or private keys to the web
- Token counter shows exactly how much context you're sending

### Step 2 — Chat with AI

Paste into any web AI. The prompt is pre-formatted with file paths and structure so the AI understands your codebase layout.

### Step 3 — Apply Changes

Copy the AI's response (XML format). Paste into Synapse's **Apply** tab.

- **Visual Diff** — see green/red line-by-line changes before applying
- **Auto-Backup** — every apply creates a backup, one-click undo
- **Fuzzy Matching** — even if the AI hallucinates indentation, Synapse's fuzzy search (`rapidfuzz`) still finds the right code block

---

## The 3 Tabs

| Tab         | What You Do                                              |
| ----------- | -------------------------------------------------------- |
| **Context** | Browse file tree, select files, copy prompt to clipboard |
| **Apply**   | Paste AI response, preview diff, apply or reject changes |
| **History** | See all past operations, undo any apply with one click   |

---

## Why Not Just Use an IDE Agent?

|                     | IDE Agents (Copilot, Cursor) | Synapse Desktop                              |
| ------------------- | ---------------------------- | -------------------------------------------- |
| **Cost**            | API credits per token        | **$0** — uses your existing web subscription |
| **Context control** | Auto (RAG) — may miss files  | **You pick exactly** what the AI sees        |
| **Transparency**    | Hidden system prompts        | **White box** — visual diff, secret scan     |
| **Scale**           | Good for single-file edits   | Feed **100+ file signatures** in one prompt  |

Synapse is a **sidecar** — it runs alongside your editor (VS Code, Neovim, etc.), not instead of it.

---

## OPX Protocol

OPX (Overwrite Patch XML) is the format Synapse uses to apply AI-generated changes:

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

| Operation | Description                 |
| --------- | --------------------------- |
| `new`     | Create a new file           |
| `patch`   | Find & replace a code block |
| `replace` | Overwrite entire file       |
| `remove`  | Delete a file               |
| `move`    | Rename or move a file       |

---

## Supported Languages (Smart Context)

Python, JavaScript, TypeScript, Rust, Go, Java, C#, C, C++, Ruby, PHP, Swift, CSS/SCSS/LESS, Solidity

---

## Safety Features

| Feature              | How It Works                                                                                |
| -------------------- | ------------------------------------------------------------------------------------------- |
| **Secret Scanning**  | `detect-secrets` scans your prompt before copy — warns about API keys, tokens, passwords   |
| **Binary Detection** | Magic-byte analysis (not just extensions) — skips executables, images, videos automatically |
| **Visual Diff**      | Green/red line-by-line preview before any file is modified                                  |
| **Auto-Backup**      | Every apply creates a timestamped backup in `~/.synapse-desktop/backups/`                   |

---

## Data Storage

All data stored locally at `~/.synapse-desktop/`:

| File            | Purpose                             |
| --------------- | ----------------------------------- |
| `settings.json` | User preferences                    |
| `session.json`  | Last workspace & selection state    |
| `history.json`  | Operation history                   |
| `backups/`      | Auto-backup files before each apply |

---

## Build AppImage (Linux)

```bash
pip install pyinstaller
./build-appimage.sh
```

---

## Acknowledgements

Inspired by:

- **[Repomix](https://github.com/yamadashy/repomix)** — XML context packing format
- **[Overwrite](https://github.com/mnismt/overwrite)** — OPX patch protocol
- **[PasteMax](https://github.com/kleneway/pastemax)** — file tree UI patterns

---

## License

MIT © HaoNgo232
