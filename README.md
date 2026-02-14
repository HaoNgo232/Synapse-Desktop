# Synapse Desktop
### The "White-Box" Context Engine for AI-Native Developers

> **"The Manual Transmission for AI Coding."**
>
> Synapse Desktop is a standalone sidecar tool designed to bridge your local codebase with powerful Web LLMs (ChatGPT, Claude, Gemini, DeepSeek). It gives you **deterministic control** over context and enables zero-cost API coding workflows.

---

## Why use this in the era of IDE Agents?

Modern IDE Agents are amazing "Automatic Transmissions"—fast and convenient. However, they rely on RAG (Vector Search) which is probabilistic, and they consume API credits per token.

**Synapse is built for the scenarios where IDE Agents fall short:**

### 1. The "Flat Rate" Economy
*   **The Problem:** Using IDE Agents with powerful models burns API credits quickly. A heavy refactoring session can cost $5-$10/day.
*   **The Synapse Solution:** Leverage the **Web Subscription** you already paid for. Synapse formats your code perfectly for the Web UI, allowing you to code heavily at **Zero Marginal Cost**.

### 2. Deterministic Context (vs. RAG Luck)
*   **The Problem:** IDE Agents use RAG to find files. Sometimes RAG misses a crucial config file because of low keyword similarity, leading the AI to hallucinate variables.
*   **The Synapse Solution:** You build the context **deterministically** using **Dependency Graphs** (Tree-sitter) and manual selection. You know *exactly* 100% of what the AI sees. No hidden system prompts, no missing files.

### 3. Macro-Architecture Analysis
*   **The Problem:** Dumping 50 full files into a chat window exceeds context limits or confuses the model.
*   **The Synapse Solution:** **"Smart Copy"** mode uses Tree-sitter to strip function bodies, keeping only signatures and docstrings. You can feed **your entire project structure (100+ files)** into a single prompt to ask high-level architectural questions.

---

## Feature Comparison

| Feature | IDE Agents | Synapse Desktop |
| :--- | :--- | :--- |
| **Primary Interface** | Chat inside IDE | **Any** Web UI (ChatGPT/Claude/Gemini) |
| **Cost Model** | Subscription + API Credits (Pay-per-token) | **Flat Rate** (Uses your Web Subs) |
| **Context Discovery** | **Auto (RAG)** - Probabilistic | **Manual + Graph** - Deterministic |
| **Refactoring Scale** | Micro/Medium (File implementation) | **Macro** (Architecture/Planning) |
| **Transparency** | Black Box (Hidden context) | **White Box** (Visual Diff, Secret Scan) |

---

## Quick Start

```bash
# Clone repository
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop

# Setup environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies & Run
pip install -r requirements.txt
python3 main_window.py
```

**Requirements:** Python 3.10+ (Dependencies include `pyside6`, `tree-sitter`, `detect-secrets`).

---

## Workflow: The "Sidecar" Approach

Synapse runs alongside your editor (VS Code, Neovim, IntelliJ).

1.  **Curate:** Select files manually or use **"Select Related"** (Dependency Graph) to auto-select imports.
2.  **Optimize:**
    *   *Coding?* Use **Standard Context** (Full code).
    *   *Architecture?* Use **Smart Context** (Signatures only, saves ~70% tokens).
    *   *Review?* Use **Diff Only** (Git changes).
3.  **Prompt:** Click `Copy`. Synapse wraps code in XML tags optimized for LLMs.
4.  **Chat:** Paste into **ChatGPT / Claude / DeepSeek** web interface.
5.  **Apply:** Copy the XML response -> Paste into Synapse -> **Review Diff** -> **Apply**.

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

### Smart Context (Tree-sitter Powered)
Uses language-specific parsers to extract only the "skeleton" of your code.
*   **Benefit:** Fits massive codebases into limited context windows.

### Dependency Resolver
Don't know which files are related?
*   Click **"Select Related"** to automatically find and select files imported by your current selection (supports Python/JS/TS imports).

### Security & Safety
*   **Secret Scanning:** Integrated `detect-secrets` scans your prompt before copying. Warns you if you are about to paste API Keys or Private Keys to the web.
*   **Visual Diff:** See exactly what lines will change (Green/Red) before applying AI code.
*   **Auto-Backup:** Every apply operation creates a backup. One-click Undo available.

### OPX Protocol (Overwrite Patch XML)
Forces LLMs to output structured XML (`<edit>`, `<find>`, `<replace>`).
*   **Fuzzy Matching:** If the LLM hallucinates indentation or misses a comma in the `<find>` block, Synapse's fuzzy search (`rapidfuzz`) can still locate the correct code block to patch.

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

## Acknowledgements & Inspirations

This project combines workflow patterns, security practices, and performance optimizations from:

*   **[Overwrite](https://github.com/mnismt/overwrite)** by [@mnismt](https://github.com/mnismt)
*   **[Repomix](https://github.com/yamadashy/repomix)** by [@yamadashy](https://github.com/yamadashy)
*   **[PasteMax](https://github.com/kleneway/pastemax)** by [@kleneway](https://github.com/kleneway)

---

## License

MIT © HaoNgo232
