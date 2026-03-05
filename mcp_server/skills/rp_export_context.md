---
name: rp_export_context
description: >-
  Context builder and exporter workflow using Synapse MCP tools.
  Use when the user wants to gather project context and export it 
  into a prompt file to paste into an external LLM (e.g., ChatGPT, Claude Web).
---
# Oracle Export Workflow

Explore the codebase and build an optimized implementation context, 
then export it to a file (`context.xml` or similar) so the user
can manually copy it to a more powerful external AI model.

## When to Use

** WARNING: MANUAL HANDOFF ONLY - NOT for automated delegation workflows**

Use this skill ONLY when:
- User explicitly asks to "export context" for ChatGPT/Claude web/Gemini
- User wants to manually review context before pasting elsewhere
- You do NOT have sub-agent tools available
- User wants a second opinion from external AI (not internal sub-agent)

** DO NOT use this for:**
- Automated multi-agent workflows (use rp_build/rp_review/rp_refactor/rp_investigate/rp_test instead)
- Tasks where you can delegate to sub-agents directly
- Internal workflow coordination

## Step-by-Step Workflow

### Step 0: Initialize Session (MANDATORY)
```python
# Auto-discover: project structure + directory tree + technical debt
start_session()

# Hieu kien truc tong the (Optional but recommended for complex tasks)
explain_architecture(focus_directory="src")
```

### Step 1: Module-level Exploration
Find the relevant modules based on the user's task.
```python
batch_codemap(directory="src/target_module", max_files=20)
```

### Step 2: Accumulate Context
Trace dependencies and gather the exact files needed for the external LLM to understand the problem.
```python
get_callers(symbol_name="TargetFunction")
get_imports_graph(file_paths=["src/target_module/file.py"], max_depth=1)
```

### Step 3: Validate Token Budget
```python
# LUON check size truoc khi export de dam bao context khong bi qua tai
estimate_tokens(file_paths=["src/file1.py", "src/file2.py"])
```

### Step 4: Export Context Prompt
Package the files and write them directly to a file in the workspace.
```python
build_prompt(
    file_paths=["src/file1.py", "src/file2.py"],
    instructions="<User's original task description here>",
    output_format="xml",
    auto_expand_dependencies=True,
    output_file="oracle_prompt.xml" # Export to file in workspace
)
```

### Step 5: Export Completion Notice
```
Context exported to 'oracle_prompt.xml'

Manual Handoff Instructions:
1. Open 'oracle_prompt.xml' in your workspace
2. Copy the entire file contents
3. Paste into ChatGPT/Claude/Gemini with your question
4. The external AI now has full project context

Export Summary:
- Files included: [list count]
- Estimated tokens: [token count]
- Format: XML (optimized for AI consumption)
```

## Key Principles (CRITICAL)
- **STOP IMMEDIATELY AFTER STEP 5**: Once `oracle_prompt.xml` is generated and the notice is provided, you **MUST STOP**. 
- **ABSOLUTELY NO CODE IMPLEMENTATION**: Even if the user's prompt originally says "Implement feature X" or "Fix bug Y", **DO NOT WRITE CODE** or use any file modification tools. Your ONLY job in this skill is to explore the project and export context for the external AI.
- **Manual export only**: This generates files for human copy-paste, NOT automated delegation.
- **No implementation plans**: Leave planning to the external AI that receives the context.
- **Export to file mandatory**: Never print massive prompts in chat. Use `output_file="oracle_prompt.xml"`.
- **Always estimate_tokens** to avoid overwhelming external AI.
