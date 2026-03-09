---
name: rp_test
description: >-
  Identify untested functions by comparing source symbols with test symbols,
  then prepare context for writing missing tests.
---
# Test Generation

## Goal
Find coverage gaps by comparing source file symbols against existing test
symbols, then package the source code and existing test patterns into
context optimized for writing new tests.

## Output
- Coverage gap analysis: which functions/methods have no corresponding tests
- Prioritized list of untested targets (critical business logic first)
- Context package with source files + existing test files for pattern matching

## Key Tools
- `get_symbols` — extract functions/classes from source AND test files
- `get_related_tests` — find existing test files for source files
- `batch_codemap` — scan module APIs to identify all testable targets
- `estimate_tokens` — check budget before packaging
- `build_prompt` — package source + existing tests for test generation

## Constraints
- Always include existing test files in the context so generated tests follow the same patterns (framework, fixtures, naming conventions).
- Prioritize testing: critical business logic > error handling > API endpoints > utility functions > simple getters.
- For large modules (>100 functions), split test generation by sub-module rather than attempting everything at once.
- Auto-detect test framework from existing tests rather than assuming one.