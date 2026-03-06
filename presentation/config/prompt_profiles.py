"""
Prompt Profiles - Registry cac preset cau hinh cho build_prompt.

Moi profile la mot ten goi nho (review, bugfix, refactor, doc) mapping
sang bo params noi bo xac dinh san. Giup AI client khong can nho va
truyen nhieu params rieng le.

Nguyen tac uu tien: explicit param > profile default > global default.

De them profile moi chi can append vao BUILTIN_PROFILES dict
hoac load tu file JSON trong .synapse/ (Open/Closed principle).
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True, slots=True)
class PromptProfile:
    """
    Dinh nghia mot prompt profile preset.

    Moi field tuong ung voi mot param cua build_prompt.
    None co nghia la "khong override, dung global default".

    Attributes:
        name: Ten dinh danh cua profile (unique key)
        output_format: Dinh dang output (xml, json, plain, smart)
        include_git_changes: Co bao gom git diffs/logs khong
        instruction_prefix: Text tu dong prepend vao user instructions
        max_tokens: Gioi han token cho prompt output (Feature 2)
        auto_expand_dependencies: Tu dong mo rong dependency files (Feature 3)
    """

    name: str
    output_format: Optional[str] = None
    include_git_changes: Optional[bool] = None
    instruction_prefix: Optional[str] = None
    max_tokens: Optional[int] = None
    auto_expand_dependencies: Optional[bool] = None


# ============================================================
# Registry cac built-in profiles
# ============================================================

BUILTIN_PROFILES: Dict[str, PromptProfile] = {
    "review": PromptProfile(
        name="review",
        output_format="xml",
        include_git_changes=True,
        instruction_prefix=(
            "You are reviewing this code. Focus on:\n"
            "- Bugs and logic errors\n"
            "- Security vulnerabilities\n"
            "- Performance issues\n"
            "- Code style and best practices\n"
            "Provide specific, actionable feedback with line references.\n"
        ),
        max_tokens=100_000,
        auto_expand_dependencies=False,
    ),
    "bugfix": PromptProfile(
        name="bugfix",
        output_format="xml",
        include_git_changes=True,
        instruction_prefix=(
            "You are debugging this code. Focus on:\n"
            "- Identifying the root cause of the bug\n"
            "- Tracing data flow and side effects\n"
            "- Checking edge cases and error handling\n"
            "- Suggesting minimal, targeted fixes\n"
        ),
        max_tokens=80_000,
        auto_expand_dependencies=True,
    ),
    "refactor": PromptProfile(
        name="refactor",
        output_format="smart",
        include_git_changes=False,
        instruction_prefix=(
            "You are refactoring this code. Focus on:\n"
            "- Improving code structure and readability\n"
            "- Reducing duplication (DRY principle)\n"
            "- Applying SOLID principles\n"
            "- Maintaining backward compatibility\n"
        ),
        max_tokens=60_000,
        auto_expand_dependencies=False,
    ),
    "doc": PromptProfile(
        name="doc",
        output_format="smart",
        include_git_changes=False,
        instruction_prefix=(
            "You are writing documentation for this code. Focus on:\n"
            "- Clear function/class descriptions\n"
            "- Parameter and return value documentation\n"
            "- Usage examples\n"
            "- Architecture overview where applicable\n"
        ),
        max_tokens=40_000,
        auto_expand_dependencies=False,
    ),
}


def get_profile(name: str) -> Optional[PromptProfile]:
    """
    Lay profile theo ten tu registry.

    Tim trong BUILTIN_PROFILES truoc. Neu khong thay, tra None.
    Trong tuong lai co the mo rong de load tu file .synapse/profiles.json.

    Args:
        name: Ten cua profile can tim

    Returns:
        PromptProfile neu tim thay, None neu khong ton tai
    """
    return BUILTIN_PROFILES.get(name)


def list_profiles() -> list[str]:
    """
    Tra ve danh sach cac ten profile co san.

    Returns:
        List ten cac profiles (sorted alphabetically)
    """
    return sorted(BUILTIN_PROFILES.keys())
