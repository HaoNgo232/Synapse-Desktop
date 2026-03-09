---
name: rp_design
description: >-
  Produce an architectural design and implementation plan based on task requirements,
  identifying scope, dependencies, impact, and a step-by-step rollout strategy.
---
# Architectural Design Planner

## Goal
Generate a comprehensive architecture and implementation plan for a new feature or change.
The output instructs an AI to produce a design covering goals, API contracts, migration needs,
test strategy, rollout plan, and a do-not-touch list, preventing structural drift.

## Output
A `build_prompt()` result containing:
- Core architecture goals and choices
- Impacted modules and risk areas
- API definitions and data models
- Step-by-step implementation and rollout plan
- Security and performance considerations

## Key Tools
- `explain_architecture` / `start_session` — understand project layout and norms
- `batch_codemap` — scan existing APIs without reading full files
- `get_callers` / `find_references` — assess impact on dependent modules
- `get_contract_pack` — check existing constraints and conventions to respect
- `estimate_tokens` — verify context fits token budget BEFORE packaging
- `build_prompt` — package context into a structured design prompt

## Constraints
- Always query `get_contract_pack("get")` to incorporate domain conventions and guarded paths into the plan.
- For risky changes (e.g., database schema, core shared libraries), explicitly outline blast radius and migration paths.
- Define a "do-not-touch" list to preserve unrelated components.
- Outline necessary testing steps within the implementation plan.
