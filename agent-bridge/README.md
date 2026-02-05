# Agent Bridge 🌉

Universal bridge to convert Antigravity agents (Markdown + Frontmatter) to various AI IDE formats.

## Support
- [x] **Kiro CLI** (.kiro/ structure)
- [x] **GitHub Copilot** (.github/copilot-instructions.md)

## Installation
```bash
pip install -e .
```

## Usage
### Convert to Kiro
```bash
agent-bridge kiro --source .agent --output .kiro
```

### Update Agents/Skills from Kit
```bash
agent-bridge update-kit
```
*Clones the latest Antigravity Kit and merges it into your .agent folder.*

### Convert to GitHub Copilot
```bash
agent-bridge copilot --source .agent
```
*Note: This will automatically create `.github/agents/` and `.github/skills/` directories according to official spec.*

## Credits
Built with 🧠 for the agentic future.
