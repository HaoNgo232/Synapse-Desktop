# Synapse Desktop

**Synapse Desktop** is a lightweight desktop application (Python + Flet) designed to **extract context from your codebase for LLMs** (ChatGPT, Claude, Gemini, etc.) and **safely apply LLM-suggested changes** to your project with full control.

The goal of Synapse Desktop is to make the development loop:

> Select Files → Generate optimized prompt → Send to LLM → Receive Patch → Preview Diff → Apply → Backup/Undo

**fast, secure, and free from path hallucinations.**

---

## Why Synapse Desktop?

When working with LLMs on large codebases, you often face several challenges:

- **Context Selection**: Hard to decide which files to send. Too few and the LLM lacks understanding; too many and you **waste tokens**.
- **Hallucinations**: LLMs frequently hallucinate file paths or project structures if the context is unclear.
- **Manual Applying**: Copy-pasting patches manually is error-prone (wrong indentation, missing segments, applying to the wrong file).
- **Security Risks**: Accidental exposure of **secrets** (API keys, tokens, credentials) when copying code to LLMs.

Synapse Desktop solves these problems by providing:
- An intuitive file tree for selection.
- Optimized prompt generation formats for LLMs.
- "Smart Context" mode to drastically reduce token usage.
- The "Apply OPX" system with diff preview, backups, and undo functionality.

---

## Works with Any AI Chat

Synapse Desktop is **not tied to any specific AI provider**. Since it generates structured text (XML, Markdown, JSON, or Plain Text), you can copy and paste the output into **any AI chat interface**:

**Free Chat UIs (Save Money!):**
- ChatGPT Free (OpenAI)
- Gemini (Google) - 1M+ token context window
- Claude Free (Anthropic)
- Microsoft Copilot (Bing Chat)
- Grok (xAI)
- DeepSeek Chat
- Perplexity
- ...

**Paid/API Services:**
- ChatGPT Plus/Pro
- Claude Pro
- Gemini Advanced
- ...

**Local LLMs:**
- Ollama
- LM Studio
- Jan
- GPT4All
- Text Generation WebUI
- ...

**Why This Matters:**
- **Zero LLM subscription cost**: Use free tiers with large context windows (Gemini: 1M tokens, Claude: 200K tokens)
- **Multi-model comparison**: Send the same context to GPT-4, Claude, and Gemini to get "second opinions"
- **No vendor lock-in**: Switch between models freely based on your needs
- **Future-proof**: Works with any new AI chat that accepts text input

---

## When to Use Synapse Desktop

### Synapse vs. IDE AI Assistants (Copilot, Cursor, Cody)

| Aspect | IDE AI (Copilot/Cursor) | Synapse Desktop |
|--------|-------------------------|-----------------|
| **Cost** | $10-20/month subscription | Free (uses free chat UIs) |
| **Model choice** | Locked to provider's model | Any model you want |
| **Context control** | Auto-detect (may miss files) | Manual selection with token count |
| **Secret scanning** | Often sends automatically | Scans BEFORE you copy |
| **Preview changes** | Usually applies directly | Full diff preview |
| **Undo changes** | Depends on git/IDE undo | Automatic backup + 1-click undo |
| **Inline completion** | Yes | No (different use case) |

### Use Synapse Desktop When:

1. **Saving Money**: You don't want to pay for Copilot/Cursor subscription. Use Synapse + Gemini/ChatGPT Free instead.

2. **Multi-Model Review**: You want to compare solutions from GPT-4, Claude, and Gemini before choosing the best one.

3. **Precise Context Control**: You need to send exactly the right files with known token count, not rely on auto-detection.

4. **Security-First Workflow**: You work with sensitive code and need to scan for secrets BEFORE sending context.

5. **Safe Code Changes**: You want to preview diffs and have automatic backups before applying any changes.

6. **Legacy/Restricted Environments**: Your IDE doesn't have AI extensions, or company policy restricts AI integrations.

7. **Complex Refactoring**: Multi-file changes that need careful review before application.

### Use IDE AI When:

- You need **inline code completion** as you type
- You have a subscription and are satisfied with the default model
- Simple, single-file edits that don't need preview

**Note**: Synapse Desktop and IDE AI can work **together**. Use IDE AI for quick completions, and Synapse for complex tasks requiring context control, multi-model comparison, or safe application.

---

## Key Features

### 1) Copy Context (Prompt Preparation)
- Select files/folders from the visual tree.
- Enter "User Instructions" for the task.
- Export prompts in multiple formats:
  - **XML (Default, Repomix-style)**: Highly structured, minimizes hallucinations.
  - **Markdown**: Human-readable and widely supported.
  - **JSON**: Ideal for automation or JSON-mode interactions.
  - **Plain Text**: Minimalist and token-efficient.

### 2) Copy Tree Map (Folder Structure Only)
- Copies the **file structure** without file contents.
- Useful for:
  - Discussing architecture.
  - Low token budgets.
  - Initial planning before the LLM needs to read specific code.

### 3) Copy Smart Context (Token Saving via Tree-sitter)
- Instead of sending full source code, Smart Context extracts:
  - Signatures (classes/functions/methods).
  - Imports.
  - Relevant docstrings and comments.
- Helps the LLM understand the structure while significantly reducing token consumption.

**Currently Supported Languages for Smart Context:**
Python, JavaScript, TypeScript, Rust, Go, Java, C#, C, C++, Ruby, PHP, Swift, CSS/SCSS/LESS, Solidity.

### 4) Git Integration (Recently Changed Context)
- Options to include:
  - `git diff` (working tree / staged changes).
  - `git log` (recent commit history).
- Includes a **Copy Diff Only** mode: perfect for code reviews or incremental updates.

### 5) Security Check (Secret Leak Prevention)
- Scans for secrets before copying (powered by **detect-secrets**).
- Displays alerts and provides a redacted preview.
- Allows opening the file preview directly at the suspicious line.

### 6) Apply OPX (Controlled Patch Application)
Synapse Desktop supports applying LLM responses using the **OPX (Overwrite Patch XML)** format:

- `new` → Create a new file.
- `patch` → Search & replace within a specific region (safer than full file overwrites).
- `replace` → Overwrite the entire file content.
- `remove` → Delete a file.
- `move` → Rename or move a file.

**Before Applying:**
- Use the **Preview** tab to see a clear diff (+/-) for every affected file.

**When Applying:**
- Automatically creates a **backup** before any modification.
- Features a one-click **Undo Last Apply** from Backups/History.

### 7) History & Session Restore
- The History tab logs all apply operations (success/fail, action summaries).
- Automatically restores your workspace and file selections after restarting the app.

---

## Recommended Workflow

### A. Sending Context to LLM
1. **Open Folder** → Select your workspace.
2. Tick the files needed for context.
3. Enter your instructions (what you want the LLM to do).
4. Select the **Output Format** (XML is recommended).
5. Click:
   - **Copy Context** (for standard context packing).
   - **Copy + OPX** (includes instructions for the LLM to reply with an OPX patch).

### B. Applying LLM Changes
1. LLM provides an OPX XML block.
2. Go to the **Apply** tab.
3. Paste the OPX content → Click **Preview** to review the diff.
4. Click **Apply Changes**.
5. If something goes wrong: **View Backups → Undo Last Apply**.

---

## Installation & Setup

### Requirements
- Python 3.10+
- pip

### Installation (Linux)
```bash
git clone https://github.com/HaoNgo232/synapse-desktop.git
cd synapse-desktop

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
./start.sh
# or
python main.py
```

---

## Build AppImage (Linux)
```bash
pip install pyinstaller
./build-appimage.sh
```

---

## Data Storage
Synapse Desktop stores data at:

`~/.synapse-desktop/`

| File/Folder | Purpose |
|---|---|
| `settings.json` | Excluded folders, model settings, security, git options. |
| `session.json` | Workspace path, selections, and window state. |
| `history.json` | History of OPX apply operations. |
| `logs/app.log` | Application logs (rotated). |
| `backups/` | Automated file backups created before any modification. |

---

## What is OPX? (Quick Summary)
OPX (Overwrite Patch XML) is an XML-based patch format for describing file operations.

Example patch:
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

Benefits:
- Automated preview and application.
- Targeted search & replace minimizes errors.
- Reduced risk compared to full file replacements.

---

## Acknowledgements
- Workflow inspired by **Overwrite** (VS Code extension).
- Logic and concurrency adapted from **Pastemax**.
- Security scan patterns inspired by **Repomix**.

---

## License
MIT
