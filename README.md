# Synapse Desktop

> Extract codebase context for LLMs and apply changes

**Workflow:**
> Select Files → Generate optimized prompt → Send to LLM → Receive Patch → Preview Diff → Apply → Backup/Undo (optional)

## Quick Start

```bash
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
python main.py
```

**Requirements:** Python 3.10+

---

## What's Included

| Component | Description |
|-----------|-------------|
| **Context Tab** | Select files, generate prompts, copy to any AI chat |
| **Apply Tab** | Preview diffs, apply patches, automatic backups |
| **History Tab** | View past operations, one-click undo |

---

## Core Features

| Feature | Description |
|---------|-------------|
| **Copy Context** | Export files as XML/Markdown/JSON prompt |
| **Copy Smart** | Tree-sitter powered - signatures only, saves tokens |
| **Copy Diff Only** | Export git changes with optional file content |
| **Select Related** | Auto-add imported files (1-3 depth levels) |
| **Secret Scan** | Detect secrets before copying |
| **Apply OPX** | Preview diff, apply patch, backup, undo |

---

## Use Case

Synapse generates structured text output, so you can copy context to **any AI chat interface** - ChatGPT, Claude, Gemini, local LLMs, or any future AI.

**When to use:**
- **Codebase review** - Export entire repo for AI to review architecture, find bugs, suggest improvements
- **Security audit** - Quick scan for vulnerabilities by feeding code to AI
- Multi-file refactoring with precise context control
- Comparing responses from different LLMs
- Complex changes needing diff preview

---

## Usage

### Send Context to LLM

```
1. Open folder
2. Select files (or use "Select Related" for imports)
3. Enter instructions
4. Click "Copy Context" or "Copy + OPX"
5. Paste to any AI chat
```

### Apply LLM Response

```
1. LLM responds with OPX block
2. Go to Apply tab
3. Paste → Preview → Apply
4. If wrong: View Backups → Undo
```

---

## Supported Languages (Smart Context)

Python, JavaScript, TypeScript, Rust, Go, Java, C#, C, C++, Ruby, PHP, Swift, CSS/SCSS/LESS, Solidity

---

## OPX Operations

| Operation | Description |
|-----------|-------------|
| `new` | Create new file |
| `patch` | Search & replace |
| `replace` | Overwrite file |
| `remove` | Delete file |
| `move` | Rename/move file |

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

---

## Data Storage

Location: `~/.synapse-desktop/`

| Path | Purpose |
|------|---------|
| `settings.json` | Preferences |
| `session.json` | Workspace state |
| `history.json` | Operation history |
| `backups/` | Auto backups |

---

## Build AppImage

```bash
pip install pyinstaller
./build-appimage.sh
```

---

## Acknowledgements

- Workflow inspired by **Overwrite** (VS Code extension)
- Concurrency from **Pastemax**
- Security patterns from **Repomix**

---

## License

MIT © HaoNgo232
