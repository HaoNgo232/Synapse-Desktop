---
name: rp_build
description: >-
  Gather relevant source files for a task, resolve their dependencies,
  and package everything into a structured context prompt.
---
# Build Implementation Context

## Goal
Produce a token-optimized context package containing all source files,
dependencies, and project structure needed to implement a given task.
The output is a structured prompt (XML/plain) ready for an AI agent to act on.

## Output
A `build_prompt()` result containing:
- Full content of primary files relevant to the task
- Dependency files (as codemap signatures when possible to save tokens)
- Directory structure and project metadata
- User instructions embedded in the prompt

## Key Tools
- `explain_architecture` / `start_session` — understand project layout
- `batch_codemap` — scan module APIs without reading full files
- `get_imports_graph` / `get_callers` — trace dependencies and impact
- `find_references` — locate where symbols are used
- `estimate_tokens` — verify context fits token budget BEFORE packaging
- `build_prompt` — package files into final prompt (supports `output_file` for cross-agent handoff)

## Constraints
- Always check token budget with `estimate_tokens` before calling `build_prompt`. If user provides `max_tokens`, treat it as a hard ceiling.
- When total tokens exceed budget: convert low-priority files to codemap-only (signatures), or split into multiple context files by concern.
- For complex tasks spanning 3+ independent modules, split into separate `build_prompt` calls per module rather than one massive prompt.
- Use `auto_expand_dependencies=True` in `build_prompt` to automatically include imported files.