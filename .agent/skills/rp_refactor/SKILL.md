---
name: rp_refactor
description: >-
  Analyze dependencies, callers, and coupling before refactoring,
  then produce a safe incremental refactoring plan.
---
# Safe Refactoring

## Goal
Understand the full dependency and coupling landscape of target code,
then produce a phased refactoring plan where each phase is atomic,
testable, and reversible.

## Output
Two phases:
1. **Discovery report**: dependency graph, callers, tests, coupling points, risk areas
2. **Refactoring plan**: ordered list of atomic changes, each with expected test verification

## Key Tools
- `blast_radius` — analyze impact and find all callers/dependents
- `get_imports_graph` — trace dependency chain
- `get_related_tests` — identify existing test coverage
- `batch_codemap` — understand module APIs
- `build_prompt` — package context per refactoring phase

## Constraints
- Never refactor everything in one pass. Break into atomic phases: extract → update callers one by one → remove deprecated code.
- Each phase must be independently testable. If tests fail, the phase can be reverted without affecting other phases.
- Always map blast radius before modifying any public interface. Callers you miss will break silently.
- When updating callers, produce one context per caller (or small group) rather than bundling all callers into one massive prompt.