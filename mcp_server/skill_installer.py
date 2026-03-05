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
    "OpenCode": {
        "skills_dir": "~/.config/opencode/skills",
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
            "Implementation context builder workflow using Synapse MCP tools. "
            "Use when user wants to start a new feature, build implementation context, "
            "or prepare a handoff prompt for another agent."
        ),
        "body": """\
# Context Builder Workflow

Build optimized implementation context by exploring the codebase first,
then packaging the relevant files into a structured prompt.

## When to Use

- Starting a new feature implementation
- Need to understand code structure before making changes
- Want to hand off context to another AI agent
- User asks to "build context" or "prepare implementation"

## Step-by-Step Workflow

### Step 1: Understand the Project Shape
```python
# Lay tong quan project: file types, frameworks, so luong file
get_project_structure()

# Xem cay thu muc de hieu bo cuc
list_directories(max_depth=3)
```

### Step 2: Find Relevant Files
```python
# Tim file lien quan den task bang ten/pattern
list_files(extensions=[".py"])  # hoac .ts, .tsx, ...

# Doc ky nang cua module ma khong can doc full file (tiet kiem token)
get_codemap(file_paths=["src/auth/login.py", "src/api/routes.py"])

# Tim noi mot symbol duoc su dung trong project
find_references(symbol_name="UserService")
```

### Step 3: Trace Dependencies
```python
# Xem file nao import file nao
get_imports_graph(file_paths=["src/auth/login.py"], max_depth=2)

# Tim xem ai goi ham nay - de hieu blast radius
get_callers(symbol_name="validate_token")
```

### Step 4: Build the Context Prompt
Once you have identified the exact files (2-10 files), package them:
```python
build_prompt(
    file_paths=["src/auth/login.py", "src/api/routes.py", "src/models/user.py"],
    instructions="Implement rate limiting for login endpoint",
    output_format="xml",  # best for AI consumption
    auto_expand_dependencies=True,
    output_file="context.xml"  # optional: save for cross-agent handoff
)
```

## Key Principle
**YOU explore first, THEN package.** Never blindly select all files.
Pick only 2-10 files that are directly relevant to the task.
""",
    },
    "rp_review": {
        "name": "rp_review",
        "description": (
            "Code review workflow using Synapse MCP tools. "
            "Use when user wants to review code changes, check a PR, "
            "or understand impact of recent modifications."
        ),
        "body": """\
# Code Review Workflow

Perform deep code review by understanding git changes, finding impacted
callers and tests, then packaging everything for analysis.

## When to Use

- Before merging a PR or pushing changes
- Need to understand impact of recent changes
- Want to detect side effects and breaking changes
- User asks to "review code" or "check my changes"

## Step-by-Step Workflow

### Step 1: See What Changed
```python
# Tong quan nhanh: file nao duoc add/modify/delete
diff_summary(target="HEAD")
```

### Step 2: Understand the Changed Code
```python
# Doc structure cua cac file bi thay doi (khong can doc full)
get_codemap(file_paths=["src/changed_file.py"])

# Doc chi tiet 1 doan code cu the neu can
read_file_range(relative_path="src/changed_file.py", start_line=50, end_line=80)
```

### Step 3: Find Blast Radius
```python
# Tim xem ai goi cac ham da thay doi
get_callers(symbol_name="changed_function_name")

# Tim test files tuong ung
get_related_tests(file_paths=["src/changed_file.py"])
```

### Step 4: Package Review Context
```python
build_prompt(
    file_paths=["src/changed_file.py", "tests/test_changed.py"],
    instructions="Review these changes for correctness, security, and performance",
    include_git_changes=True,
    profile="review"
)
```

## Key Principle
**Understand the blast radius BEFORE reviewing.** A change to a utility
function used in 20 places needs deeper review than a leaf function.
""",
    },
    "rp_refactor": {
        "name": "rp_refactor",
        "description": (
            "Two-pass refactoring workflow using Synapse MCP tools. "
            "Use when user wants to refactor code safely with "
            "analysis-first approach."
        ),
        "body": """\
# Refactoring Workflow

Safe refactoring with analysis-first approach: discover dependencies
and risks before making any changes.

## When to Use

- Large refactoring that affects multiple files
- Need to ensure backward compatibility
- Want to understand risks before making changes
- User asks to "refactor" or "restructure" code

## Step-by-Step Workflow

### Phase 1: Discovery (DO NOT SKIP)

#### 1a. Locate the Target
```python
# Tim module/function can refactor
find_references(symbol_name="LegacyService")
get_codemap(file_paths=["src/legacy_service.py"])
```

#### 1b. Map Dependencies
```python
# Ai import file nay?
get_imports_graph(file_paths=["src/legacy_service.py"], max_depth=2)

# Ai goi cac ham trong file nay?
get_callers(symbol_name="LegacyService.process")

# Tim test hien tai
get_related_tests(file_paths=["src/legacy_service.py"])
```

#### 1c. Assess Risk
```python
# Doc chi tiet cac file bi anh huong
get_codemap(file_paths=[
    "src/legacy_service.py",
    "src/caller_a.py",
    "src/caller_b.py"
])
```

Document your findings: number of callers, test coverage, coupling points.

### Phase 2: Plan and Execute

```python
# Goi cac file can refactor + dependencies vao 1 prompt
build_prompt(
    file_paths=["src/legacy_service.py", "src/caller_a.py", "tests/test_legacy.py"],
    instructions="Refactor LegacyService: extract validation into separate module",
    auto_expand_dependencies=True,
    profile="refactor"
)
```

## Key Principle
**NEVER refactor without knowing the blast radius first.**
Always run Phase 1 discovery to find all callers and dependents.
""",
    },
    "rp_investigate": {
        "name": "rp_investigate",
        "description": (
            "Bug investigation workflow using Synapse MCP tools. "
            "Use when user reports a bug, has an error trace, "
            "or needs to trace execution path to find root cause."
        ),
        "body": """\
# Bug Investigation Workflow

Systematic bug investigation by tracing execution paths through the
codebase to find the root cause.

## When to Use

- Debugging complex issues spanning multiple files
- Have an error trace but don't know where to start
- Need to understand execution flow
- User reports a bug or error

## Step-by-Step Workflow

### Step 1: Parse the Error
If user gave an error trace, identify the file and line number
where the error originates. If no trace, search for the bug:
```python
# Tim function/class lien quan den bug
find_references(symbol_name="suspected_function")
```

### Step 2: Read Code at Error Points
```python
# Doc doan code xung quanh loi
read_file_range(
    relative_path="src/module.py",
    start_line=40,
    end_line=70
)

# Xem structure cua file
get_symbols(file_path="src/module.py")
```

### Step 3: Trace the Call Chain
```python
# Ai goi ham bi loi? Trace nguoc len
get_callers(symbol_name="broken_function")

# Xem dependency graph
get_imports_graph(file_paths=["src/module.py"], max_depth=2)
```

### Step 4: Package Investigation Context
```python
build_prompt(
    file_paths=["src/module.py", "src/caller.py", "tests/test_module.py"],
    instructions="Investigate: <bug description>. Root cause analysis needed.",
    auto_expand_dependencies=True,
    profile="bugfix"
)
```

## Key Principle
**Trace from the error outward.** Start at the crash point,
then follow the call chain upward to find where the data went wrong.
""",
    },
    "rp_test": {
        "name": "rp_test",
        "description": (
            "Test generation workflow using Synapse MCP tools. "
            "Use when user wants to write tests, find coverage gaps, "
            "or improve test coverage for existing code."
        ),
        "body": """\
# Test Generation Workflow

Find test coverage gaps and prepare context for writing high-quality tests.

## When to Use

- Building unit/integration tests for untested code
- Fixing or improving existing test files
- Want to focus on covering untested methods
- User asks to "write tests" or "improve coverage"

## Step-by-Step Workflow

### Step 1: Identify Source Files
```python
# Tim file can test
get_codemap(file_paths=["src/service.py"])
# -> Hien thi toan bo functions/classes can duoc test
```

### Step 2: Find Existing Tests
```python
# Tim test file tuong ung (neu co)
get_related_tests(file_paths=["src/service.py"])

# Doc test hien tai de hieu pattern dang dung
get_codemap(file_paths=["tests/test_service.py"])
```

### Step 3: Identify Coverage Gaps
So sanh danh sach functions trong source file voi danh sach
test functions. Nhung ham nao chua co test?

### Step 4: Package Test Context
```python
build_prompt(
    file_paths=["src/service.py", "tests/test_service.py"],
    instructions="Write tests for untested functions: func_a, func_b",
    auto_expand_dependencies=True
)
```

## Key Principle
**Read existing tests first to match the team's patterns.**
New tests should be consistent with the existing test style,
fixtures, and naming conventions.
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
