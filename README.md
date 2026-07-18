# Synapse Desktop

> **Manually select the right code context, copy it to AI web chat for planning, then give your IDE agent a laser-focused task.**

> _Personal note: This is a local desktop tool built to cut AI costs. Instead of letting an IDE agent explore your entire codebase (burning tokens), you pick the relevant files yourself, use a free chat model to think through the problem, and only then hand the agent a clear, bounded task._

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [What Problem Does This Solve?](#what-problem-does-this-solve)
- [Core Workflow](#core-workflow)
- [Core Philosophy](#core-philosophy)
- [Key Features](#key-features)
- [Copy Modes](#copy-modes)
- [Apply Tab — Patch Workflow](#apply-tab--patch-workflow)
- [Prompt Templates](#prompt-templates)
- [Security and Privacy](#security-and-privacy)
- [Interface](#interface)
- [Example Workflows](#example-workflows)
- [Environment Variables and CLI Options](#environment-variables-and-cli-options)
- [Troubleshooting](#troubleshooting)
- [When NOT to Use This](#when-not-to-use-this)
- [License](#license)

---

## Overview

Synapse Desktop is a local desktop application for developers who use AI coding assistants.

It lets you **manually select project files**, package them into a structured prompt, and send that context to any AI web chat. The AI helps you plan, analyze, or generate patches. You then give the result to your IDE agent — which now has a clear task instead of an open-ended exploration job.

```
You pick files → Synapse packages context → Web chat plans → IDE agent executes
```

**Who this is for:**

- Developers paying for Cursor, Claude Code, Cline, Windsurf, or similar IDE agents
- Anyone who wants to use free/cheap web chat (ChatGPT, Claude, Gemini) for the thinking phase
- Developers who want precise control over what context is sent to AI

**Who this is NOT for:**

- People who want fully automated AI workflows with no manual steps
- Teams looking for a shared or cloud context management platform
- Developers who are happy with their current AI agent costs

---

## Quick Start

**Requirements:** Python 3.10+ · Git (optional, for Git Diff and branch detection)

### 🚀 Linux

```bash
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop
chmod +x start.sh && ./start.sh
```

### 🚀 Windows (PowerShell)

```powershell
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop
.\start.bat
```

### 🔧 Manual Install — Linux / macOS

```bash
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### 🔧 Manual Install — Windows PowerShell

```powershell
git clone https://github.com/HaoNgo232/Synapse-Desktop.git
cd Synapse-Desktop
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

### 📦 Build AppImage (Linux)

```bash
chmod +x build-appimage.sh && ./build-appimage.sh
```

### 📦 Build Windows EXE

```powershell
.\build-windows.ps1
```

**First run:** The app opens to the **Context** tab. Click **Open Folder** in the top bar and select your project directory. The file tree populates on the left.

![Context tab — no workspace open](assets/app_ui/context_tab_no_workspace_state.png)

---

## What Problem Does This Solve?

IDE agents are powerful. They can read files, search code, trace dependencies, and understand a codebase on their own.

But that exploration is not free.

Every time an agent scans your project to understand what's relevant, it spends:

- Tool calls and API requests
- Tokens reading files you already know aren't relevant
- Time on back-and-forth turns before implementation even starts
- Quota from your paid subscription

**Synapse Desktop front-loads that work manually.**

You already know which files matter for your task. Synapse lets you select them, package them cleanly, and hand a focused context to a web chat model for the thinking phase — before your paid agent touches a single file.

**Use this when:**

- You want to use free ChatGPT / Claude / Gemini web for planning before writing code
- You're approaching a context window limit and need to be selective
- You want to review a git diff without sending your entire codebase
- You want to generate a Search/Replace patch and apply it safely with a diff preview
- You want to understand a module before asking an agent to modify it

---

## Core Workflow

```
1. Open your project folder
        ↓
2. Select relevant files in the tree (tick checkboxes)
        ↓
3. Write your task in the Instructions field
        ↓
4. Choose a Copy Mode (Full / Smart / Tree Map / Apply)
        ↓
5. Click Copy — context is on your clipboard
        ↓
6. Paste into AI web chat (ChatGPT, Claude, Gemini…)
        ↓
7. Get analysis, plan, or Search/Replace patch
        ↓
8. Paste result into your IDE agent  ← much cheaper, focused task
```

**Mental model:** You are the context engineer. You decide what the AI sees. Synapse packages it cleanly and counts the tokens so you stay within limits.

---

## Core Philosophy

> **Manual selection is the main idea.**

Synapse does not auto-select files. It does not crawl your repo and guess what's relevant. That is intentional.

The value is not automation — it is **human-guided context selection**:

```
Human picks files → cheaper AI planning → focused IDE agent execution
```

This split works because:

- Web chat models (free tier or subscription) are excellent at planning and analysis
- IDE agents are excellent at editing, running tests, and iterating on implementation
- The expensive part (agent exploration) is avoided when you already know the relevant files

---

## Key Features

### Visual File Selection

Open a project folder and tick files in a tree view. Token count updates in real time as you select or deselect files. Folders can be expanded lazily — only loaded when you open them.

![Context tab with file tree](assets/app_ui/context_tab_open_with_tree_state.png)

---

### Real-Time Token Counter

The toolbar shows a live token usage bar. It tracks:

- File content tokens
- Instruction tokens
- Total vs. model context window limit

The bar turns amber near the limit and red when exceeded. Switch to **Smart Context** mode to reduce token usage by ~70%.

---

### Context Presets

Save your current file selection and instructions as a named preset. Reload it in one click. Useful when you repeatedly work on the same module or feature area.

Use `Ctrl+Shift+S` to quick-save a preset. Use `Ctrl+Shift+L` to focus the preset selector.

---

### Prompt Templates

Built-in templates for common tasks. Select one from the **Templates** dropdown in the Instructions panel to pre-fill a structured prompt.

| Template              | What it does                                               |
| --------------------- | ---------------------------------------------------------- |
| Bug Hunter            | Find logic errors, race conditions, edge cases             |
| Security Auditor      | Check OWASP Top 10, detect secrets                         |
| Architecture Reviewer | Review SOLID compliance, design patterns                   |
| Code Explainer        | Explain architecture and execution flows                   |
| Test Writer           | Generate unit and integration tests                        |
| Doc Generator         | Create or update README and architecture docs              |
| Performance Optimizer | Analyze Big O, memory leaks, blocking operations           |
| ROI Analyzer          | Evaluate codebase from technical and business perspectives |

You can also create your own custom templates via **Templates → Manage/Add Custom Template...**.

---

### Related Files Auto-Detection

Enable **Related** mode in the toolbar to automatically add files that are imported by your selected files. Choose depth from 1 (direct imports) to 5 (wide discovery).

| Depth | Label          | What it includes                          |
| ----- | -------------- | ----------------------------------------- |
| 1     | Direct         | Files directly imported by your selection |
| 2     | Nearby         | One hop further                           |
| 3     | Extended chain | Two hops further                          |
| 4     | Wide discovery | Three hops further                        |
| 5     | Maximum depth  | Full import graph                         |

---

### Improve Instructions

Write your raw task draft in the Instructions field and click **Improve Instructions**. The app calls your configured LLM API to analyze, restructure, and rewrite your draft into a highly polished, plain-text professional prompt (copy-paste ready) for external AI webchats. Requires an API key in Settings.

---

### AI Pick Files (File Suggestions)

Write your instruction in the Instructions field and click **AI Pick Files** (brain icon). If you are feeling a bit too lazy to manually search for files in a huge codebase, or just want a quick starting point, Synapse runs a read-only background Codex Agent that securely scans your workspace, explores file structures, and automatically suggests relevant files step-by-step.

- **Secure Read-Only Scan**: The AI is confined to a read-only sandbox and cannot modify any workspace files.
- **Sensitive File Filter**: Credentials and secret configs (like `.env`, private keys, v.v.) are automatically filtered out.
- **Auto-Apply or Review**: Suggestions are applied automatically or shown for review if there are more than 50 files suggested.

---

### Apply Tab — Patch Workflow

Paste a Search/Replace response from AI chat, preview the diffs, and apply changes safely. Backups are created automatically before any file is modified.

![Apply tab with patch preview](assets/app_ui/apply_tab_with_search_replace_patching_state.png)

---

### History Tab

Every apply operation is logged. Review past operations, copy the original patch, or re-apply it from the History tab.

![History tab](assets/app_ui/history_tab_no_workspace_state.png)

---

### MCP Server Integration

Synapse can run as an MCP server for AI clients (Cursor, Claude Code, and other MCP-compatible tools). Install the config from **Settings → MCP Server Integration**.

---

## Copy Modes

Select a mode using the **Full / Smart / Apply** buttons in the right panel, then click **Copy**.

| Mode                       | What it copies                                                                        | Best for                                                |
| -------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| **Full Context**           | Complete content of selected files                                                    | Planning, debugging, code review, spec generation       |
| **Smart Context**          | Code structure only — signatures, docstrings, class/function declarations (no bodies) | Architecture analysis, lower token usage (~70% savings) |
| **Apply (Search/Replace)** | Full content + Aider-style patch instructions                                         | Generating patches to apply via the Apply tab           |
| **Tree Map only**          | Directory structure only (no file content)                                            | Asking AI which files to select next                    |
| **Git Diff**               | Recent git changes only                                                               | Reviewing uncommitted work, PR descriptions             |

**Sub-options:**

- **Include Git Diff** — append staged and unstaged changes to the context
- **Tree Map only** — send only the directory tree, no file content
- **Include full tree** — attach the entire project directory structure

---

## Apply Tab — Patch Workflow

The Apply tab lets you take a Search/Replace response from AI and apply it to your codebase with a visual diff preview.

**Supported patch operations:**

```
Create a new file:
<<<<<<< SEARCH path/to/new_file.ext
=======
[file content]
>>>>>>> REPLACE

Modify a file (find and replace):
<<<<<<< SEARCH path/to/file.ext - Brief description
[exact original code to replace]
=======
[replacement code]
>>>>>>> REPLACE

Delete a file:
<<<<<<< DELETE path/to/file.ext
>>>>>>> DELETE

Rename or move a file:
<<<<<<< RENAME path/to/old_file.ext
=======
path/to/new_file.ext
>>>>>>> RENAME
```

**How to use:**

1. Get a Search/Replace response from AI web chat
2. Open the **Apply** tab
3. Paste the response (or click **Paste** to pull from clipboard)
4. Click **Preview** to see visual diffs before applying
5. Click **Apply Changes** to write to disk (backups are created automatically)

If a patch fails, click **Copy Error Context for AI Fix** to send the full error context back to the AI for correction.

---

## Prompt Templates

Templates are pre-written instructions for common tasks. They are injected into the Instructions field when selected.

**Lite tier** (default): Focused, concise prompts for everyday tasks.

**How to use a template:**

1. Click **Templates** in the Instructions panel
2. Select a template (e.g., Bug Hunter)
3. The instructions field is pre-filled
4. Optionally edit the instructions
5. Click **Copy** to package the context

**Creating custom templates:**

1. Click **Templates → Manage/Add Custom Template...**
2. Enter a name, description, and prompt content
3. Save — the template appears in the dropdown immediately

---

## Security and Privacy

### Local-First

Synapse Desktop processes your project locally. Your code is not uploaded by Synapse Desktop. You decide what to copy and where to paste it.

### Secret Scanning

Before copying context, Synapse scans for possible secrets such as:

- API keys
- Access tokens
- Passwords
- Private credentials

If a secret-like value is found, the app shows a warning with a masked preview. You can choose to copy anyway or cancel.

### Relative Paths

Enable **Use Relative Paths** in Settings to avoid exposing absolute local machine paths in prompts.

Example: `/home/username/work/project/src/app.py` becomes `src/app.py`.

### Safety Recommendations

Before applying patches:

- Use git and commit your current work
- Review the diff preview before applying
- Keep backups enabled (on by default)
- Avoid sending secrets to external AI providers
- Prefer small patches over large patches

---

## Interface

### Context Tab

Select files, write instructions, choose copy mode, and prepare context. The main workspace of the app.

![Context tab](assets/app_ui/context_tab_open_with_tree_state.png)

---

### Apply Tab

Paste Search/Replace blocks from AI, preview diffs, and apply changes safely.

![Apply tab](assets/app_ui/apply_tab_with_search_replace_patching_state.png)

---

### History Tab

Review copy and apply history. Re-apply past patches or copy the original OPX content.

![History tab](assets/app_ui/history_tab_no_workspace_state.png)

---

### Settings Tab

Configure models, token counting, security options, MCP integration, and app behavior.

![Settings tab](assets/app_ui/setting_tab.png)

---

## Example Workflows

### Workflow A: Web Chat Planning to Save IDE Agent Cost

Use this when you want to plan a change before asking your IDE agent to implement it.

**Steps:**

1. Open your project folder
2. Select the relevant files in the tree
3. Write your task in the Instructions field
4. Click **Copy** (Full mode)
5. Paste into ChatGPT / Claude / Gemini Web
6. Use this prompt:

```
Analyze the selected code context and create a practical implementation plan.

Task:
[Describe your task here]

Do not write the full code.
Do not return a patch.

Focus on:
- What the current code does
- Which files matter
- What needs to change
- Implementation steps
- Risks
- Test plan
- Acceptance criteria
```

7. Copy the plan from the AI response
8. Paste into your IDE agent with this prompt:

```
Implement this plan.

Use the provided plan as guidance.
Avoid exploring unrelated files unless necessary.
Keep the implementation focused.

Plan:
[Paste plan here]
```

---

### Workflow B: Ask Web Chat Which Files to Select

Use this when you don't know which files are relevant to your task.

**Steps:**

1. Click **Tree Map only** checkbox in the right panel
2. Click **Copy**
3. Paste into web chat with this prompt:

```
Here is the project tree.

Task:
[Describe your task]

Which files are likely relevant?
Return a prioritized list and explain briefly why.
```

4. Select the suggested files in Synapse Desktop
5. Proceed with your preferred copy mode

---

### Workflow C: Generate a Search/Replace Patch

Use this when you want AI to generate precise code changes you can apply safely.

**Steps:**

1. Select the relevant files
2. Select **Apply (Search/Replace)** mode
3. Click **Copy**
4. Paste into web chat with this prompt:

```
Implement this focused change.

Return only Search/Replace blocks.
Keep the patch small and minimal.

Task:
[Describe your task]
```

5. Copy the AI response
6. Open the **Apply** tab
7. Paste the response
8. Click **Preview** to review diffs
9. Click **Apply Changes**

---

### Workflow D: Review a Git Diff

Use this when you want AI to review your recent changes.

**Steps:**

1. Enable **Include Git Diff** in the right panel
2. Set the number of commits to include (0 = uncommitted only)
3. Click **Copy**
4. Paste into web chat with this prompt:

```
Review this git diff.

Focus on:
- Correctness
- Edge cases
- Security issues
- Performance risks
- Missing tests
- Maintainability

Return findings by severity.
```

---

### Workflow E: Code Understanding and Architecture Analysis

Use this when onboarding to a new codebase or module.

**Steps:**

1. Select the key files for the module you want to understand
2. Select **Smart Context** mode (saves ~70% tokens)
3. Click **Copy**
4. Paste into web chat with this prompt:

```
Analyze the selected code context.

Explain:
1. The main responsibility of this module
2. How the important files relate to each other
3. The main data flow
4. The most important functions/classes
5. Possible design issues
6. What files I should inspect next if I want to modify this feature

Do not write implementation code.
```

---

### Workflow F: Bug Analysis

Use this when you have a bug and want AI to identify the root cause before touching code.

**Steps:**

1. Select the files most likely related to the bug
2. Write a description of the bug in the Instructions field
3. Select **Bug Hunter** from the Templates dropdown
4. Click **Copy**
5. Paste into web chat and get the analysis
6. Use the analysis to guide your IDE agent to the fix

---

## Environment Variables and CLI Options

### Environment Variables

| Variable        | Description                                 |
| --------------- | ------------------------------------------- |
| `SYNAPSE_DEBUG` | Set to `1` to enable detailed debug logging |

### CLI Arguments

| Argument                | Description                                          |
| ----------------------- | ---------------------------------------------------- |
| `--run-mcp [workspace]` | Start in MCP server mode (for AI client integration) |

---

## Troubleshooting

**App does not start on Linux**

Make sure `python3-venv` is installed:

```bash
sudo apt install python3-venv
```

---

**`pip install` fails with tree-sitter errors**

Ensure you have a C compiler installed:

```bash
# Linux
sudo apt install build-essential

# macOS
xcode-select --install
```

---

**Token count shows 0 after selecting files**

The token counter runs in the background. Wait a moment after selecting files. If it stays at 0, try clicking **Reload** (F5) to refresh the tree.

---

**Patch apply fails with "Search text not found"**

The AI may have generated a search pattern that doesn't match the current file content exactly. Click **Copy Error Context for AI Fix** and send it back to the AI — it includes the current file content and the failed search block so the AI can correct the patch immediately.

---

**MCP server not detected by Cursor / Claude Code**

1. Go to **Settings → MCP Server Integration**
2. Click **Install to [IDE Name]**
3. Review the JSON preview
4. Click **Install**
5. Restart your IDE

---

**Window icon shows Python logo instead of Synapse logo on Windows**

This is a Windows AppUserModelID issue. It is handled automatically when running from the built EXE. When running from source, it may show the Python icon — this is cosmetic only.

---

**"No valid patch found" shown immediately after pasting**

The auto-detection debounces for 800ms. Wait briefly after pasting. If it still shows "no valid patch", check that the AI response contains `<<<<<<< SEARCH` or `<<<<<<< DELETE` markers.

---

## When NOT to Use This

- **You want fully automated context selection.** Synapse requires manual file selection. Use an IDE agent directly if you want full automation.
- **You need real-time collaboration.** Synapse is a single-user local tool with no sharing or sync features.
- **Your project has thousands of files and you don't know where to start.** Use the Related Files presets or the Tree Map workflow first to identify relevant files.
- **You want to apply patches to files outside your workspace.** The Apply tab enforces workspace boundaries for security.
- **You need a CI/CD integration.** Synapse is a desktop GUI tool, not a CLI pipeline tool.

---

## Inspirations and Credits

Synapse Desktop was inspired by and references several excellent tools in the AI development space:

- **[RepoPrompt](https://repoprompt.com/)**: Inspired the core interface concept and context management workflow. Since RepoPrompt is native and exclusive to macOS, Synapse Desktop was built using Python/PySide6 to bring a similar cross-platform tool to Windows and Linux developers.
- **[Overwrite](https://github.com/mnismt/overwrite)**: The patch apply mechanism was inspired by Overwrite's OPX XML format.
- **[Aider](https://github.com/Aider-AI/aider)**: The patch apply mechanism also supports the popular and compact search/replace block format popularized by Aider.

---

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
