# Synapse Desktop

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Linux%20(Stable)%20%7C%20Windows%20(Beta)-orange)
![Qt](https://img.shields.io/badge/GUI-PySide6%20(Qt6)-41cd52)
![MCP](https://img.shields.io/badge/MCP-Server%20Ready-blueviolet)
![Version](https://img.shields.io/badge/version-1.1.0-purple)

A desktop application that bridges your codebase and AI assistants (ChatGPT, Claude, Gemini, or any OpenAI-compatible API). Synapse Desktop lets you select files from a project tree, package them into structured prompts with accurate token counts, and then apply AI-generated code changes back to your codebase — all with visual diffs, auto-backup, and continuous memory across sessions.

**Now supports Model Context Protocol (MCP):** Run Synapse as a headless server to expose your workspace directly to AI clients (Cursor, GitHub Copilot, Claude Code, Antigravity) via standardized tools, enabling seamless AI-codebase integration without manual copy/paste workflows.

> ⚠️ **Platform Status:** Currently stable on **Linux**. The **Windows** version is in experimental/beta phase. **macOS** is currently unsupported/untested due to lack of testing environments.

---

## 🌟 Why Use Synapse? (Value Proposition)

When working with LLMs for coding, managing context is a massive pain. Copy-pasting multiple files is tedious, and guessing token counts leads to truncated responses. Applying the AI's response back to your codebase is equally risky. 

**Synapse solves this by providing:**
- **Smart Context Packaging:** Select files in your project → copy a structured prompt with exact token counts → paste into ChatGPT / Claude.
- **AST Optimization:** Use "Smart Copy" to extract only function signatures and class definitions from code, saving 70-80% of your token budget while giving the AI the big picture.
- **Safe Code Application:** Paste XML responses (OPX format) from the AI → view visual diffs → apply to codebase with seamless auto-backup.
- **Autonomous Exploration (MCP Mode):** Let your AI Editors (Cursor, Copilot, etc.) use Synapse's advanced AST tools, token counting, and dependency graphs natively.

---

## ✨ Key Features

### Context Management
- **Tree selection**: Browse the directory tree and select files/folders to send.
- **Copy modes**:
  - `Context`: Full content of the files.
  - `Smart`: Only signatures/structures (reduces tokens by 70–80%).
  - `Diff Only`: Only git changes (for code review).
- **Context Presets**: Save and restore file selections with instructions for recurring tasks. Quick access via dropdown or `Ctrl+Shift+S` shortcut. [Learn more](docs/PRESETS.md)
- **AI Suggest Select**: Write your instructions, and a connected LLM automatically selects the most relevant files from the tree.
- **Prompt Templates**: Built-in and custom templates for common tasks (bug hunting, refactoring, security audit, etc.).
- **Related Files**: Automatically discover and include files that import or are imported by your selection.
- **Content Search**: Search file contents directly from the tree search bar using `code:` prefix (e.g., `code:def main`).

### Apply AI Changes
- **OPX format**: AI returns changes in structured XML format.
- **Visual diff**: Preview changes before applying.
- **Auto-backup**: Automatically backs up files before overwriting, allowing undo operations.
- **Continuous Memory**: AI summarizes its actions; Synapse saves this to `.synapse/memory.xml` and injects it into future prompts for multi-session continuity.
- **Error Context**: One-click "Copy Error Context" provides the AI with detailed diagnostics (file content, search pattern, OPX instruction) for self-repair.

### MCP Server Integration (IDE Backend for AI Agents)
- **Direct AI Access**: Run Synapse as an MCP server to expose specialized workspace analysis tools directly to AI clients.
- **19 Comprehensive Tools**: Provides a suite of tools categorized for optimal usage by AI agents.

  **Workflow Tools (NEW)**
  *Advanced multi-step workflows for AI agent handoff:*
  - `rp_build` — Context Builder: Auto-detect scope, optimize token budget, generate handoff prompt
  - `rp_review` — Code Review: Deep review with surrounding context (imports, callers, tests)
  - `rp_refactor` — Two-Pass Refactor: Analyze first (discover), then plan (safe refactoring)
  - `rp_investigate` — Bug Investigation: Trace execution path from error traces
  
  [📖 Workflow Tools Documentation](docs/WORKFLOW_TOOLS.md)

  **Advanced Tools**
  *Tools providing capabilities like AST parsing and accurate token counting:*
  - `get_project_structure` — Project summary with frameworks and file stats.
  - `get_codemap` — Extract AST code structure (function/class signatures only).
  - `get_symbols` — Structured JSON symbol list for programmatic analysis.
  - `estimate_tokens` — Accurate LLM token counting using proper tokenizers.
  - `get_imports_graph` — Cross-file dependency graph resolution.
  - `diff_summary` — Function-level git change analysis.
  - `build_prompt` — Package files into a structured prompt format (Ideal for Cross-Agent Delegation).
  - `find_references` — Find symbol usages (filters out comments and strings).
  - `manage_selection` — Track selected files for context building.

  **Basic Operations**
  *Standard filesystem operations. AI clients (like Cursor or Copilot) with native file-reading tools should prioritize their built-in tools over these to reduce MCP overhead:*
  - `start_session` — Project discovery (structure + tree + todos).
  - `list_files` — List all workspace files respecting `.gitignore`.
  - `list_directories` — Show directory tree structure.
  - `read_file_range` — Read file contents with line range support.
  - `get_file_metrics` — LOC, functions/classes count, TODO/FIXME/HACK, complexity.
  - `find_todos` — Scan entire project for TODO/FIXME/HACK comments.

- **Auto-Configuration**: One-click installation of MCP config files via Settings tab (supports Cursor, VS Code, Claude Code).
- **Headless Operation**: No GUI overhead when running in MCP mode — pure stdio transport for maximum efficiency.

---

## 🚀 Usage Workflow

### 1. Standard GUI Workflow (Copy-Paste)
1. **Select Context**: Open your project folder. Check the required files in the tree. Token counts update in real time.
2. **Copy to AI**: Click **Copy Context**, **Copy Smart**, or **Copy Diff Only**. Paste into the AI chat and request the OPX format in return.
3. **Apply Changes**: Copy the XML response from the AI. Paste into the Apply tab → **Preview** → review diffs → **Apply Changes**.

### 2. MCP Server Workflow (Autonomous)
1. **Setup MCP Integration** (Settings → MCP Server Integration). Click **Install to Cursor** (or your preferred AI client).
2. **Use AI Client**: Open your AI client. Synapse tools are now available directly in AI conversations. Example: *"Use `get_project_structure` to analyze this codebase."*
3. **AI Explores Autonomously**: The AI client spawns Synapse in headless mode (`--run-mcp`). No manual copy/paste—the AI uses Synapse's advanced AST and dependency parsing natively.
4. **Cross-Agent Delegation (Pro Tip)**: Ask your Planning Agent to use the `build_prompt` tool to generate a `spec.xml` file containing the full project architecture. Then, tell your Coding Agent to read that file. This transfers massive context between AI agents efficiently without crashing the chat window!

*(Manual MCP Server Launch: `python main_window.py --run-mcp /path/to/workspace`)*

---

## 🖥️ Application Interface

**1. Context Management (Main Interface)**
![Select files and folders to send to AI](assets/image.png)
*Select files and view the calculated token count before copying the prompt.*

**2. Apply Changes (Apply Tab)**
![Apply OPX XML content and view code diff](assets/image-1.png)
*Paste OPX XML from the AI and review visual diffs before confirming file overwrites.*

**3. Operation History (History Tab)**
![Manage copy and apply history](assets/image-2.png)
*Review the list of successful or failed apply/copy tasks.*

**4. Settings (Settings Tab)**
![Settings interface](assets/image-3.png)
*Configure file rules, access permissions, privacy options, and MCP Server Integration.*

---

## ⚙️ Installation & Configuration

### Prerequisites
Python 3.10+, Git (optional, for branch detection and diff context).

### Quick Start
**Linux (Stable)**
```bash
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop
chmod +x start.sh
./start.sh
```

**Windows (Experimental)**
Double-click `start.bat`, or use `.\build-windows.ps1` to compile into a `.exe`.

### Manual Installation
```bash
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop
python -m venv .venv
source .venv/bin/activate  # Or .\.venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
python main_window.py
```

### Configuration Data
Synapse stores all data locally at `~/.config/synapse-desktop/` (Linux) or `~/.synapse-desktop/` (Windows). No telemetry is collected.
Contains: `settings.json`, `session.json`, `history.json`, `recent_folders.json`, `logs/`, and `backups/`.

---

## 🔧 OPX Format & Continuous Memory

**OPX (Overwrite Patch XML)**
Synapse expects AI to return changes in this structured XML format:
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
Operations supported: `new`, `patch`, `replace`, `remove`, `move`.

**AI Continuous Memory**
When enabled in Settings, the AI is instructed to include a `<synapse_memory>` block summarizing its actions. Synapse saves the last 5 memory blocks to `.synapse/memory.xml` in your workspace and automatically injects them into subsequent prompts, giving the AI long-term memory across sessions.

---

## 🛡️ Security and Privacy

- **Local Only**: All settings and context data are processed locally. No external telemetry.
- **Relative Paths**: Enable **Use Relative Paths** in Settings to obfuscate your local machine directory names structure.
- **Secret Scanning**: Synapse pre-scans selected files for API keys and passwords before copying context.
- **MCP Security**: Runs via local `stdio` UNIX sockets. Validates all file paths strictly to prevent directory traversal attacks.

---

## 🛠️ Troubleshooting

- **"Module not found"**: Ensure your venv is activated (`source .venv/bin/activate`) and run `pip install -r requirements.txt`.
- **Apply failed "pattern not found"**: Ask the AI to provide a longer, more unique code block within the `<find>` tag.
- **Cascade failures during Apply**: If multiple edits target the exact same file, block 1 might change the text that block 2 is trying to `<find>`. Use **Copy Error Context** to give the AI context so it can rewrite the OPX.
- **Slow directory scanning**: Install `scandir-rs` (`pip install scandir-rs`) for 3–70x faster scanning.
- **MCP Connection Timeout**: If Cursor/Copilot report "context deadline exceeded", test manually with `python main_window.py --run-mcp /path/to/workspace` to ensure no Python dependency errors are blocking startup.

---

## 🏗️ Architecture & Contributing (Under the Hood)

This section is intended for developers who wish to understand or contribute to the Synapse Codebase.

### Tech Stack
- **GUI**: PySide6 (Qt 6)
- **Tokenization**: tiktoken / HuggingFace tokenizers
- **Protocol**: MCP (Model Context Protocol) via `FastMCP`
- **Fast I/O**: scandir-rs (optional)

### Key Design Decisions
- **PySide6 over Electron**: Much lower memory footprint and faster startup.
- **Mixin UI Pattern**: `ContextViewQt` composes behavior from focused Mixin modules (`UIBuilderMixin`, `CopyActionsMixin`, etc.).
- **Service Container**: Pure dependency injection via `ServiceContainer` instead of massive global singletons.
- **Thread-safe**: Aggressive use of global cancellation flags, `threading.Lock`, and `SignalBridge` for pushing background updates to the main thread securely.

### Key Modules
- `main_window.py`: Entry point for GUI and MCP mode.
- `views/`: Qt UI modules (`context_view_qt`, `apply_view_qt`, `history_view_qt`, etc).
- `services/`: Core logic (`token_display`, `prompt_build_service`, `workspace_index`).
- `core/`: Base infrastructure (`theme`, `file_scanner`, `threading_utils`).
- `mcp_server/`: FastMCP implementation (`server.py`, `config_installer.py`).

### Development
- Code Style: Type hints everywhere.
- Thread Safety: Never call Qt widget methods from a background thread directly. Use `SignalBridge`.
- Running Tests: `python -m pytest tests/ -v`

---

## Acknowledgements
Inspired by [Repomix](https://github.com/yamadashy/repomix), [Overwrite](https://github.com/mnismt/overwrite), and [PasteMax](https://github.com/kleneway/pastemax).

## License
MIT © HaoNgo232
