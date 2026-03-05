"""
Skill Installer - Tu dong cai dat Synapse Agent Skills vao cac IDE.

Agent Skills la open standard (agentskills.io) cho phep AI agents
su dung cac workflow chuyen biet. Module nay tao 5 skill folders
(rp_build, rp_review, rp_refactor, rp_investigate, rp_test)
trong thu muc skills tuong ung cua tung IDE.

Ho tro:
- Claude Code:      ~/.claude/skills/<name>/SKILL.md
- Cursor:           ~/.cursor/skills/<name>/SKILL.md
- Antigravity:      ~/.agents/skills/<name>/SKILL.md
- Kiro CLI:         ~/.kiro/skills/<name>/SKILL.md
- VS Code (Copilot): <workspace>/.github/skills/<name>/SKILL.md
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger("synapse.mcp.skill_installer")

# ---------------------------------------------------------------------------
# Dinh nghia vi tri luu skills cho tung IDE
# is_global: True = luu vao home dir (~), False = luu vao workspace
# ---------------------------------------------------------------------------
SKILL_TARGETS: dict[str, dict] = {
    "Claude Code": {
        "skills_dir": "~/.claude/skills",
        "is_global": True,
    },
    "Cursor": {
        "skills_dir": "~/.cursor/skills",
        "is_global": True,
    },
    "Antigravity": {
        "skills_dir": "~/.agents/skills",
        "is_global": True,
    },
    "Kiro CLI": {
        "skills_dir": "~/.kiro/skills",
        "is_global": True,
    },
    "VS Code (Copilot)": {
        "skills_dir": ".github/skills",
        "is_global": False,
    },
}

# ---------------------------------------------------------------------------
# 5 Skill templates - moi skill gom name, description, va body markdown
# Format chuan Agent Skills: YAML frontmatter + Markdown instructions
# ---------------------------------------------------------------------------
SKILL_TEMPLATES: dict[str, dict[str, str]] = {
    "rp_build": {
        "name": "rp_build",
        "description": (
            "Prepare optimized context for a coding task using Synapse MCP. "
            "Use when user wants to build context, start a new implementation task, "
            "or prepare a handoff prompt for another agent."
        ),
        "body": """\
# Context Builder (rp_build)

Prepare optimized context for implementing a new feature or task using the
Synapse MCP `rp_build` tool.

## When to Use

- Starting a new feature implementation
- Need to understand code structure before making changes
- Want to hand off context to another AI agent
- User asks to "build context" or "prepare implementation context"

## Instructions

1. Identify the task description from the user's request
2. Call the `rp_build` MCP tool with these parameters:
   - `task_description`: Clear description of what needs to be implemented
   - `file_paths`: (Optional) Known relevant files
   - `max_tokens`: Token budget (default: 100,000)
   - `include_codemap`: Include code structure signatures (default: True)
   - `output_file`: (Optional) Path to write prompt for cross-agent handoff

```
rp_build(
    task_description="<user's task>",
    file_paths=["path/to/file.py"],  # optional
    max_tokens=100000,
    output_file="context.xml"  # optional
)
```

## What It Does

- Detects relevant files from task description
- Traces dependencies automatically
- Slices large files to include only relevant sections
- Optimizes content to fit token budget
- Generates structured handoff prompt
""",
    },
    "rp_review": {
        "name": "rp_review",
        "description": (
            "Deep code review with full surrounding context using Synapse MCP. "
            "Use when user wants to review code changes, check a PR, "
            "or understand impact of recent modifications."
        ),
        "body": """\
# Code Review (rp_review)

Perform deep code review with full surrounding context using the
Synapse MCP `rp_review` tool.

## When to Use

- Before merging a PR or pushing changes
- Need to understand impact of recent changes
- Want AI to detect side effects and breaking changes
- User asks to "review code" or "check changes"

## Instructions

1. Call the `rp_review` MCP tool with these parameters:
   - `review_focus`: (Optional) Focus area - "security", "performance", "correctness"
   - `include_tests`: Pull related test files (default: True)
   - `include_callers`: Pull files that call changed functions (default: True)
   - `max_tokens`: Token budget (default: 120,000)
   - `base_ref`: (Optional) Git ref to diff against

```
rp_review(
    review_focus="security",  # optional
    include_tests=True,
    include_callers=True,
    max_tokens=120000
)
```

## What It Does

- Pulls git diff (staged + unstaged changes)
- Identifies changed functions/classes (not just lines)
- Finds surrounding context: imports, callers, tests
- Packages everything into comprehensive review prompt
""",
    },
    "rp_refactor": {
        "name": "rp_refactor",
        "description": (
            "Two-pass refactoring workflow using Synapse MCP. "
            "Use when user wants to refactor code safely with analysis-first approach."
        ),
        "body": """\
# Two-Pass Refactor (rp_refactor)

Safe refactoring with analysis-first approach using the
Synapse MCP `rp_refactor` tool.

## When to Use

- Large refactoring that affects multiple files
- Need to ensure backward compatibility
- Want to understand risks before making changes
- User asks to "refactor" or "restructure" code

## Instructions

### Phase 1: Discovery (always run first)

```
rp_refactor(
    refactor_scope="<what to refactor>",
    phase="discover",
    file_paths=["path/to/file.py"]  # optional
)
```

Review the discovery report before proceeding.

### Phase 2: Planning (after reviewing discovery)

```
rp_refactor(
    refactor_scope="<what to refactor>",
    phase="plan",
    discovery_report="<paste discovery output>"
)
```

## What It Does

**Phase 1 (discover):**
- Analyzes code structure WITHOUT making changes
- Finds all dependencies and coupling points
- Identifies risk areas and backward compatibility concerns

**Phase 2 (plan):**
- Takes discovery report as input
- Generates concrete refactoring plan
- Ensures backward compatibility
- Suggests migration steps if needed
""",
    },
    "rp_investigate": {
        "name": "rp_investigate",
        "description": (
            "Automated bug investigation using Synapse MCP. "
            "Use when user reports a bug, has an error trace, "
            "or needs to trace execution path to find root cause."
        ),
        "body": """\
# Bug Investigation (rp_investigate)

Automated bug investigation by tracing execution path using the
Synapse MCP `rp_investigate` tool.

## When to Use

- Debugging complex issues spanning multiple files
- Have an error trace but don't know where to start
- Need to understand execution flow
- User reports a bug or error

## Instructions

1. Collect bug description and any error trace from the user
2. Call the `rp_investigate` MCP tool:

```
# With error trace
rp_investigate(
    bug_description="<description of the bug>",
    error_trace="<paste traceback/stack trace>",
    max_depth=4
)

# Without error trace (manual entry points)
rp_investigate(
    bug_description="<description>",
    entry_files=["path/to/suspect.py"],
    max_depth=3
)
```

## What It Does

- Parses error traces (Python traceback, JS stack traces)
- Reads code at each trace point
- Follows function calls (callers and callees) via BFS
- Slices large files to show only relevant sections
- Packages everything into investigation prompt
""",
    },
    "rp_test": {
        "name": "rp_test",
        "description": (
            "Test generation workflow using Synapse MCP. "
            "Use when user wants to write tests, find coverage gaps, "
            "or improve test coverage for existing code."
        ),
        "body": """\
# Test Generation (rp_test)

Analyze code, find test coverage gaps, and prepare optimized context
for writing tests using the Synapse MCP `rp_test` tool.

## When to Use

- Building unit/integration tests for untested code
- Fixing or improving existing test files
- Want to focus on covering untested methods
- User asks to "write tests" or "improve coverage"

## Instructions

1. Call the `rp_test` MCP tool:

```
rp_test(
    task_description="Write tests for login functionality",
    file_paths=["auth/login.py"],  # optional
    max_tokens=100000,
    test_framework="pytest"  # optional: "pytest", "jest", "vitest"
)
```

## What It Does

- Finds all source files and their corresponding test files
- Extracts functions/methods/classes dynamically
- Maps tested code to test functions
- Identifies missing coverage with priority ranking (HIGH/MEDIUM/LOW)
- Auto-detects testing frameworks (pytest, jest, vitest)
- Formats analysis into an AI agent-ready plan
""",
    },
}


def _build_skill_md(skill_key: str) -> str:
    """Tao noi dung file SKILL.md tu template.

    Args:
        skill_key: Key trong SKILL_TEMPLATES (vd: "rp_build").

    Returns:
        Noi dung SKILL.md hoan chinh voi YAML frontmatter.
    """
    template = SKILL_TEMPLATES[skill_key]
    # YAML frontmatter + body markdown
    content = (
        f"---\n"
        f"name: {template['name']}\n"
        f"description: >-\n"
        f"  {template['description']}\n"
        f"---\n\n"
        f"{template['body']}"
    )
    return content


def _resolve_skills_dir(target_name: str, workspace_path: str | None = None) -> Path:
    """Xac dinh duong dan tuyet doi den thu muc skills cua IDE.

    Args:
        target_name: Ten IDE (vd: "Claude Code", "Cursor").
        workspace_path: Duong dan workspace (can thiet cho VS Code/Copilot).

    Returns:
        Path tuyet doi den thu muc skills.

    Raises:
        ValueError: Neu target khong duoc ho tro hoac workspace_path thieu.
    """
    if target_name not in SKILL_TARGETS:
        raise ValueError(
            f"IDE '{target_name}' khong duoc ho tro. "
            f"Cac target hop le: {list(SKILL_TARGETS.keys())}"
        )

    target = SKILL_TARGETS[target_name]
    skills_dir_str: str = target["skills_dir"]
    is_global: bool = target["is_global"]

    if is_global:
        # Thu muc global: expand ~ thanh home dir
        return Path(os.path.expanduser(skills_dir_str))

    # Thu muc project-level: can workspace_path
    if not workspace_path:
        raise ValueError(
            f"IDE '{target_name}' yeu cau workspace_path "
            "vi skills duoc luu o cap project."
        )
    return Path(workspace_path) / skills_dir_str


def install_skills_for_target(
    target_name: str, workspace_path: str | None = None
) -> tuple[bool, str]:
    """Cai dat 5 Synapse skills vao thu muc skills cua IDE.

    Tao 5 folder (rp_build, rp_review, rp_refactor, rp_investigate, rp_test)
    trong thu muc skills tuong ung, moi folder chua 1 file SKILL.md.

    Args:
        target_name: Ten IDE target (vd: "Claude Code", "Cursor").
        workspace_path: Duong dan workspace (chi can cho VS Code/Copilot).

    Returns:
        Tuple (success: bool, message: str).
    """
    try:
        skills_dir = _resolve_skills_dir(target_name, workspace_path)
    except ValueError as e:
        logger.warning("Khong the xac dinh thu muc skills: %s", e)
        return False, str(e)

    installed_count = 0
    errors: list[str] = []

    for skill_key in SKILL_TEMPLATES:
        skill_folder = skills_dir / skill_key
        skill_file = skill_folder / "SKILL.md"

        try:
            # Tao folder neu chua co
            skill_folder.mkdir(parents=True, exist_ok=True)

            # Ghi file SKILL.md (overwrite neu da ton tai)
            content = _build_skill_md(skill_key)
            skill_file.write_text(content, encoding="utf-8")

            installed_count += 1
            logger.info("Da cai dat skill '%s' tai %s", skill_key, skill_file)

        except OSError as e:
            error_msg = f"Loi khi cai dat skill '{skill_key}': {e}"
            logger.error(error_msg)
            errors.append(error_msg)

    if errors:
        return False, f"Cai dat {installed_count}/5 skills. Loi: {'; '.join(errors)}"

    return True, f"Da cai dat {installed_count} Synapse skills vao {skills_dir}"


def check_skills_installed(target_name: str, workspace_path: str | None = None) -> bool:
    """Kiem tra xem tat ca 5 Synapse skills da duoc cai dat chua.

    Args:
        target_name: Ten IDE target.
        workspace_path: Duong dan workspace (chi can cho VS Code/Copilot).

    Returns:
        True neu tat ca 5 skills deu co file SKILL.md.
    """
    try:
        skills_dir = _resolve_skills_dir(target_name, workspace_path)
    except ValueError:
        return False

    for skill_key in SKILL_TEMPLATES:
        skill_file = skills_dir / skill_key / "SKILL.md"
        if not skill_file.is_file():
            return False

    return True
