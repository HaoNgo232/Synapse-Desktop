"""
Skill Installer - Tu dong cai dat Synapse Agent Skills vao cac IDE.

Agent Skills la open standard (agentskills.io) cho phep AI agents
su dung cac workflow chuyen biet. Module nay tao 5 skill folders
(rp_build, rp_review, rp_refactor, rp_investigate, rp_test)
trong thu muc skills tuong ung cua tung IDE.

Ho tro:
- Claude Code:       ~/.claude/skills/<name>/SKILL.md
- Cursor:            ~/.cursor/skills/<name>/SKILL.md
- Antigravity (Global):  ~/.gemini/antigravity/skills/<name>/SKILL.md
- Antigravity (Local):   <workspace>/.agent/skills/<name>/SKILL.md
- Kiro CLI:          ~/.kiro/skills/<name>/SKILL.md
- OpenCode:          ~/.config/opencode/skills/<name>/SKILL.md
- VS Code (Copilot): <workspace>/.github/skills/<name>/SKILL.md

Noi dung tung skill duoc doc tu file .md trong thu muc `skills/`
ke ben module nay, giup de quan ly va chinh sua ma khong can sua Python code.
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
        "skills_dir": "~/.gemini/antigravity/skills",
        "is_global": True,
    },
    "Antigravity (Workspace)": {
        "skills_dir": ".agent/skills",
        "is_global": False,
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
# Thu muc chua cac file .md cua tung skill
# Cau truc: mcp_server/skills/<skill_name>.md
# ---------------------------------------------------------------------------
_SKILLS_DIR = Path(__file__).parent / "skills"

# Danh sach 5 skills duoc ho tro - thu tu doc file .md tuong ung
SKILL_KEYS: list[str] = [
    "rp_build",
    "rp_review",
    "rp_refactor",
    "rp_investigate",
    "rp_test",
    "rp_export_context",
]


def _load_skill_file(skill_key: str) -> str:
    """Doc noi dung file SKILL.md tu disk.

    Args:
        skill_key: Ten skill (vd: "rp_build") tuong ung voi file
                   `mcp_server/skills/rp_build.md`.

    Returns:
        Noi dung day du cua file SKILL.md.

    Raises:
        FileNotFoundError: Neu file .md khong ton tai.
    """
    skill_file = _SKILLS_DIR / f"{skill_key}.md"
    return skill_file.read_text(encoding="utf-8")


def _load_all_skills() -> dict[str, str]:
    """Doc tat ca 5 skills tu disk va tra ve dict {skill_key: content}.

    Returns:
        Dict map tu skill_key sang noi dung SKILL.md hoan chinh.

    Raises:
        FileNotFoundError: Neu bat ky file skill nao khong ton tai.
    """
    return {key: _load_skill_file(key) for key in SKILL_KEYS}


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

    Doc noi dung tu cac file .md trong `mcp_server/skills/` va tao
    5 folder (rp_build, rp_review, rp_refactor, rp_investigate, rp_test)
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

    # Doc tat ca skill content tu disk
    try:
        skill_contents = _load_all_skills()
    except FileNotFoundError as e:
        logger.error("Khong the doc skill file: %s", e)
        return False, f"Khong the doc skill template: {e}"

    installed_count = 0
    errors: list[str] = []

    for skill_key, content in skill_contents.items():
        skill_folder = skills_dir / skill_key
        skill_file = skill_folder / "SKILL.md"

        try:
            # Tao folder neu chua co
            skill_folder.mkdir(parents=True, exist_ok=True)

            # Ghi file SKILL.md (overwrite neu da ton tai)
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

    for skill_key in SKILL_KEYS:
        skill_file = skills_dir / skill_key / "SKILL.md"
        if not skill_file.is_file():
            return False

    return True
