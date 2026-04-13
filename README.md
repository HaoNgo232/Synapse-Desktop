# Synapse Desktop

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-blue)
![Platform](https://img.shields.io/badge/platform-Linux%20%20%7C%20Windows%20%7C%20macOS-orange)
![Qt](https://img.shields.io/badge/GUI-PySide6%20(Qt6)-41cd52)

> ⚠️ Tested on **Linux**. Windows, macOS has not been tested.

## What problem does Synapse Desktop solve?

When using AI (ChatGPT, Claude, Gemini) for coding assistance, you often encounter 3 repetitive problems:

**1. Time-consuming context packaging.** You have to open each file, copy the content, and paste it into the chat. Every time a file changes or you switch tasks, you have to start over.

**2. Constantly exceeding token limits.** AI models have context limits. Sending the entire codebase causes overflow, while sending too little information leads to incorrect AI responses.

**3. High-risk code application.** AI returns code as text. You must manually copy each snippet and paste it into the correct position in the right file. One wrong line can break everything.

Synapse Desktop solves all three problems in a single app:
- Select files from a tree → bundle them into a structured prompt → 1-click copy.
- Accurate token counting per model, with warnings when limits are exceeded.
- AI returns patches in OPX format → visual diff preview → automatic application to the codebase.

---

## Key Features

### File Selection and Context Packaging

Open a project folder → the file tree displays the entire structure → tick to select files to send to the AI. The token count updates in real-time as you select/deselect.

**4 Copy Modes:**

| Mode | Copied Content | When to Use |
|--------|-------------------|--------------|
| **Copy Context** | Full content of selected files | When the AI needs to read and edit specific code |
| **Copy + OPX** | Like Copy Context, plus instructions for the AI to return patches in OPX format | When you want the AI to return code that can be applied automatically |
| **Compress** | Only signatures (function names, classes, parameters) — no body | When the AI needs to understand project structure while saving 70-80% of tokens |
| **Git Diff** | Only changed lines in git | Code review, debugging, checking recent changes |

Additionally, there is **Copy Tree Map**, which only copies the directory structure without file content. Helpful for asking about overall architecture.

### Intelligent File Selection Support

- **Related Files**: Enable this mode, and when you select file A, Synapse automatically finds and adds files that A import or depend on. Select depth 1-5 as needed.
- **AI Suggest Select**: Write a task description in the Instructions box → click "AI Suggest Select" → AI reads the project structure and automatically selects relevant files. Requires API key configuration in Settings.
- **Context Presets**: Save your selection + instructions as a preset. Next time, just select the preset. Useful for repetitive work on the same group of files. [Details](docs/PRESETS.md)

### Applying Code from AI

When using Copy + OPX mode, the AI will return code in OPX (Overwrite Patch XML) format. How to use:

1. Copy the XML response from the AI.
2. Switch to the **Apply** tab in Synapse.
3. Paste it in → click **Preview** → view visual diffs for each file.
4. Confirm → Synapse applies the changes and automatically backs up the original files.

If the AI returns a faulty patch (pattern mismatch), click **Copy Error Context** to send the error information back to the AI for self-correction.

**Continuous Memory**: When enabled in Settings, the AI will include a summary block of what has been done. Synapse saves this to `.synapse/memory.xml` and automatically injects it into the next prompt, helping the AI remember context across sessions.

### Prompt Templates

Pre-built template system for common tasks: bug hunting, code review, security audit, performance optimization, refactoring, etc. Select a template → content is filled into the Instructions box. You can create your own custom templates.

### Accurate Token Counting

- Counts tokens according to the tokenizer of the selected model (GPT-4, Claude, Gemini, etc.).
- Displays breakdown: how many tokens for file content, instructions, tree map, git diff, overhead.
- Warns when exceeding the model's context limit.

### Security

- **Secret scanning**: Scans for API keys and passwords in files before copying. If detected, displays a warning with a masked preview.
- **Relative paths**: Enable in Settings to hide absolute paths on your personal machine.
- All data is processed locally; no telemetry is sent.

### MCP Server (for AI IDEs)

Synapse can run headless as an MCP server for AI IDEs (Cursor, Claude Code, etc.) to interact directly with the workspace.

**Currently, the MCP server provides 1 tool: `manage_selection`** — allowing the AI agent to select/deselect files in the workspace. Other tasks (reading files, searching, git) should use the IDE's built-in tools or LSP, as they are well-optimized and have lower overhead.

Configuration: Settings → MCP Server Integration → Install to [IDE].

---

## Interface

**Context tab** — Select files, write instructions, copy context:
![Context tab](assets/image.png)

**Apply tab** — Paste OPX from AI, view diff, apply changes:
![Apply tab](assets/image-1.png)

**History tab** — History of copy/apply actions:
![History tab](assets/image-2.png)

**Settings tab** — Configure app, MCP, security:
![Settings tab](assets/image-3.png)

---

## Installation

### Requirements
- Python 3.10+
- Git (not required, but needed for Git Diff or branch detection)

### Linux (Stable)
```bash
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop
chmod +x start.sh
./start.sh
```

### Windows (Beta)
Double-click `start.bat`, or use `build-windows.ps1` to build as `.exe`.

### Build AppImage (Linux)
```bash
chmod +x build-appimage.sh
./build-appimage.sh
```

### Manual Installation
```bash
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main_window.py
```

### Data Storage
All data is stored at `~/.config/synapse-desktop/` (Linux) or `~/.synapse-desktop/` (Windows). Includes: `settings.json`, `session.json`, `history.json`, `recent_folders.json`, `logs/`, `backups/`.

### Environment Variables
- `SYNAPSE_DEBUG=1`: Enables detailed debug logging.

---

## OPX Format

Synapse uses OPX (Overwrite Patch XML) as the format for AI code changes. Example:

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