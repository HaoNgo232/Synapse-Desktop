"""
Template Manager - Quan ly va load cac task-specific prompt templates.

Cung cap:
- list_templates(): Liet ke tat ca template kha dung
- load_template(template_id): Doc noi dung cua 1 template theo ID
- get_template_info(template_id): Lay metadata cua 1 template

Templates la cac file .md nam trong thu muc core/prompting/templates/.
Noi dung cua chung duoc inject vao user_instructions khi nguoi dung
chon mot task type cu the, giup AI hoat dong chinh xac hon.
"""

from dataclasses import dataclass
from pathlib import Path


# Thu muc chua cac file template .md
_TEMPLATES_DIR = Path(__file__).parent / "templates"


@dataclass(frozen=True)
class TemplateInfo:
    """Metadata cua mot prompt template."""

    # ID duy nhat, trung voi ten file (khong co extension)
    template_id: str
    # Tieu de hien thi cho nguoi dung
    display_name: str
    # Mo ta ngan gon muc dich cua template
    description: str


# Bang dang ky cac template co san, map template_id -> TemplateInfo
_TEMPLATE_REGISTRY: dict[str, TemplateInfo] = {
    "bug_hunter": TemplateInfo(
        template_id="bug_hunter",
        display_name="Bug Hunter",
        description="Find logic bugs, race conditions, edge cases, and unhandled exceptions",
    ),
    "security_auditor": TemplateInfo(
        template_id="security_auditor",
        display_name="Security Auditor",
        description="Perform OWASP Top 10 security audits to detect vulnerabilities and hardcoded secrets",
    ),
    "refactoring_expert": TemplateInfo(
        template_id="refactoring_expert",
        display_name="Refactoring Expert",
        description="Suggest code improvements based on SOLID, DRY, Clean Code, and reduce complexity",
    ),
    "doc_generator": TemplateInfo(
        template_id="doc_generator",
        display_name="Documentation Generator",
        description="Generate README, architecture documentation, and API references from the codebase",
    ),
    "performance_optimizer": TemplateInfo(
        template_id="performance_optimizer",
        display_name="Performance Optimizer",
        description="Analyze Big O, memory leaks, blocking operations, and suggest optimizations",
    ),
}


def list_templates() -> list[TemplateInfo]:
    """
    Liet ke tat ca prompt templates kha dung.

    Chi tra ve cac template co ca metadata trong registry
    VA file .md ton tai tren disk.

    Returns:
        List TemplateInfo cua cac template hop le
    """
    available: list[TemplateInfo] = []
    for template_id, info in _TEMPLATE_REGISTRY.items():
        template_path = _TEMPLATES_DIR / f"{template_id}.md"
        if template_path.exists():
            available.append(info)
    return available


def load_template(template_id: str) -> str:
    """
    Doc noi dung cua mot template theo ID.

    Args:
        template_id: ID cua template (trung voi ten file, VD: "bug_hunter")

    Returns:
        Noi dung text cua template

    Raises:
        FileNotFoundError: Khi template_id khong ton tai
        KeyError: Khi template_id khong co trong registry
    """
    if template_id not in _TEMPLATE_REGISTRY:
        raise KeyError(
            f"Template '{template_id}' khong ton tai. "
            f"Cac template hop le: {list(_TEMPLATE_REGISTRY.keys())}"
        )

    template_path = _TEMPLATES_DIR / f"{template_id}.md"
    if not template_path.exists():
        raise FileNotFoundError(
            f"File template '{template_path}' khong ton tai tren disk."
        )

    return template_path.read_text(encoding="utf-8").strip()


def get_template_info(template_id: str) -> TemplateInfo:
    """
    Lay thong tin metadata cua mot template.

    Args:
        template_id: ID cua template

    Returns:
        TemplateInfo chua display_name va description

    Raises:
        KeyError: Khi template_id khong co trong registry
    """
    if template_id not in _TEMPLATE_REGISTRY:
        raise KeyError(
            f"Template '{template_id}' khong ton tai. "
            f"Cac template hop le: {list(_TEMPLATE_REGISTRY.keys())}"
        )
    return _TEMPLATE_REGISTRY[template_id]
