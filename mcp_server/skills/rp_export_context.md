---
name: rp_export_context
description: >-
  Explore the codebase and export a structured context file (e.g., context.xml)
  for pasting into an external LLM like ChatGPT or Claude Web.
---
# Export Context for External LLM

## Goal
Gather relevant project files and package them into a file on disk
(e.g., `context.xml`) that the user can copy-paste into an external
LLM for planning, review, or implementation.

## Output
A file written to the workspace (via `build_prompt` with `output_file`)
containing structured project context. The agent reports the file path,
token count, and included files, then STOPS.

## Key Tools
- `explain_architecture` / `batch_codemap` — understand which files are relevant
- `get_imports_graph` / `get_callers` — trace dependencies to ensure complete context
- `estimate_tokens` — verify context fits the target LLM's context window
- `build_prompt` — package and write to file (use `output_file="context.xml"` or similar)

## Constraints
- **MUST write to file** via `output_file` parameter. Never print the full prompt inline.
- **STOP after exporting.** Do not implement code, do not write a plan, do not modify any files. The purpose is to produce a context file for the user to use elsewhere.
- Always run `estimate_tokens` before `build_prompt` to avoid exceeding the external LLM's context window.
- Use `auto_expand_dependencies=True` to include imported files automatically.