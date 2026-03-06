---
name: rp_review
description: >-
  Review recent code changes by gathering git diffs, identifying affected
  callers and tests, and analyzing for security, performance, and breaking changes.
---
# Code Review

## Goal
Analyze recent code changes (git diff) in their full context: what changed,
what calls the changed code, what tests cover it, and whether the changes
introduce security, performance, or compatibility risks.

## Output
A review analysis covering:
- Changed files and their diffs
- Blast radius: callers of modified functions
- Test coverage: existing tests for changed files
- Risk assessment: security, performance, breaking changes

## Key Tools
- `diff_summary` — see which files changed and how
- `get_symbols` / `get_codemap` — understand structure of changed files
- `get_callers` — find functions that call modified code (blast radius)
- `get_related_tests` — find test files for changed source files
- `get_file_metrics` — assess complexity of changed files
- `estimate_tokens` — check budget before packaging
- `build_prompt` — package review context (use `include_git_changes=True`, `profile="review"`)

## Constraints
- Always assess blast radius via `get_callers` before concluding a change is safe.
- For large diffs (>20 changed files), split review by concern area (core logic, tests, API surface) rather than reviewing everything at once.
- Include related test files in the context so the reviewer can verify coverage.