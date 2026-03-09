---
name: rp_investigate
description: >-
  Trace execution paths from an error or bug report to find the root cause,
  gathering surrounding context (callers, imports, tests) along the way.
---
# Bug Investigation

## Goal
Starting from a bug description or error trace, follow the execution path
through the codebase to identify the root cause. Produce a Root Cause Analysis
(RCA) before proposing any fix.

## Output
A Root Cause Analysis containing:
- What happened (observed behavior)
- Why it happened (code-level cause)
- Which code paths are affected
- Proposed fix strategy with affected files

## Key Tools
- `get_symbols` — understand structure of files mentioned in error trace
- `blast_radius` — trace backwards from error point (find dependents)
- `get_imports_graph` — understand dependency chain
- `get_related_tests` — check if failing code has tests
- `manage_selection` — accumulate suspect files during investigation
- `build_prompt` — package investigation context (use `profile="bugfix"`)

## Constraints
- Always produce an RCA before writing any fix. Fixes without root cause understanding tend to be superficial patches.
- For multi-component bugs (e.g., DB + API + UI), fix layers bottom-up: data layer first, then service layer, then presentation.
- Use `manage_selection` to accumulate files as you trace — don't try to identify all files upfront.