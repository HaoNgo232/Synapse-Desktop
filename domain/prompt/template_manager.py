"""
Template Manager - Quản lý và load các task-specific prompt templates.

Cung cấp:
- list_templates(): Liệt kê tất cả template khả dụng
- load_template(template_id): Đọc nội dung của 1 template theo ID
- get_template_info(template_id): Lấy metadata của 1 template

Kiến trúc áp dụng **Provider Pattern** (SOLID):
- `BuiltInTemplateProvider`: Load các templates mặc định từ core.
- `LocalCustomTemplateProvider`: Load custom templates từ thư mục của người dùng.
"""

import abc
import re
from dataclasses import dataclass
from pathlib import Path

from presentation.config.paths import APP_DIR

# Thư mục chứa các file template .md mặc định
_TEMPLATES_DIR = Path(__file__).parent / "templates"
# Thư mục lưu custom templates của người dùng
CUSTOM_TEMPLATES_DIR = APP_DIR / "templates"


@dataclass(frozen=True)
class TemplateInfo:
    """Metadata của một prompt template."""

    # ID duy nhất, trùng với tên file (không có extension)
    template_id: str
    # Tiêu đề hiển thị cho người dùng
    display_name: str
    # Mô tả ngắn gọn mục đích của template
    description: str
    # True nếu là template do người dùng tạo, False nếu là built-in
    is_custom: bool = False
    # True neu template co lite variant trong built-in tier system
    has_lite: bool = False


# ============================================================================
# Provider Interface
# ============================================================================
class TemplateProvider(abc.ABC):
    """Abstract interface cho tất cả Template Providers."""

    @abc.abstractmethod
    def list_templates(self) -> list[TemplateInfo]:
        """Liệt kê các template do provider này quản lý."""
        pass

    @abc.abstractmethod
    def load_template(self, template_id: str) -> str:
        """Load nội dung của template. Ném FileNotFoundError nếu không tìm thấy."""
        pass

    @abc.abstractmethod
    def get_template_info(self, template_id: str) -> TemplateInfo:
        """Lấy metadata. Ném KeyError nếu không tìm thấy."""
        pass

    @abc.abstractmethod
    def handles(self, template_id: str) -> bool:
        """Kiểm tra provider này có quản lý template_id này không."""
        pass

    @abc.abstractmethod
    def delete_template(self, template_id: str) -> bool:
        """Xóa template do provider này quản lý. Trả về True nếu xóa thành công, False nếu không tìm thấy hoặc không thể xóa."""
        pass


# ============================================================================
# Built-in Provider
# ============================================================================
class BuiltInTemplateProvider(TemplateProvider):
    def __init__(self) -> None:
        self._registry: dict[str, TemplateInfo] = {
            "bug_hunter": TemplateInfo(
                template_id="bug_hunter",
                display_name="Bug Hunter",
                description="Tìm lỗi logic, race conditions, edge cases và exceptions chưa xử lý",
                is_custom=False,
                has_lite=True,
            ),
            "security_auditor": TemplateInfo(
                template_id="security_auditor",
                display_name="Security Auditor",
                description="Kiểm tra lỗ hổng bảo mật theo OWASP Top 10, phát hiện secrets và hardcoded credentials",
                is_custom=False,
                has_lite=True,
            ),
            "refactoring_expert": TemplateInfo(
                template_id="refactoring_expert",
                display_name="Refactoring Expert",
                description="Đề xuất cải thiện code theo SOLID, DRY, Clean Code và giảm độ phức tạp",
                is_custom=False,
                has_lite=True,
            ),
            "doc_generator": TemplateInfo(
                template_id="doc_generator",
                display_name="Documentation Generator",
                description="Tạo hoặc cập nhật README, tài liệu kiến trúc từ codebase (chế độ cập nhật thông minh)",
                is_custom=False,
                has_lite=True,
            ),
            "performance_optimizer": TemplateInfo(
                template_id="performance_optimizer",
                display_name="Performance Optimizer",
                description="Phân tích Big O, memory leaks, blocking operations và đề xuất tối ưu hóa",
                is_custom=False,
                has_lite=True,
            ),
            "ui_ux_reviewer": TemplateInfo(
                template_id="ui_ux_reviewer",
                display_name="UI/UX Reviewer",
                description="Review giao diện, accessibility, tính nhất quán, màu sắc, animations và trải nghiệm người dùng",
                is_custom=False,
                has_lite=True,
            ),
            "test_writer": TemplateInfo(
                template_id="test_writer",
                display_name="Test Writer",
                description="Tạo Unit Tests, Integration Tests theo AAA pattern và nguyên tắc TDD",
                is_custom=False,
                has_lite=True,
            ),
            "api_reviewer": TemplateInfo(
                template_id="api_reviewer",
                display_name="API Reviewer",
                description="Review thiết kế API (REST, GraphQL, gRPC, component APIs) về contract, consistency, performance và security",
                is_custom=False,
                has_lite=True,
            ),
            "flow_checker": TemplateInfo(
                template_id="flow_checker",
                display_name="Flow Checker",
                description="Phân tích execution flow, data flow, control flow và phát hiện vấn đề về luồng xử lý",
                is_custom=False,
                has_lite=True,
            ),
            "architecture_reviewer": TemplateInfo(
                template_id="architecture_reviewer",
                display_name="Architecture Reviewer",
                description="Review kiến trúc tổng thể, SOLID compliance, design patterns và long-term maintainability",
                is_custom=False,
                has_lite=True,
            ),
            "code_review_gate": TemplateInfo(
                template_id="code_review_gate",
                display_name="Code Review Gate",
                description="Pre-merge quality gate với SOLID/Clean Code checklist và severity-based recommendations",
                is_custom=False,
                has_lite=True,
            ),
            "tech_debt_analyzer": TemplateInfo(
                template_id="tech_debt_analyzer",
                display_name="Tech Debt Analyzer",
                description="Phát hiện, đo lường và prioritize technical debt với debt scoring và repayment roadmap",
                is_custom=False,
                has_lite=True,
            ),
            "code_explainer": TemplateInfo(
                template_id="code_explainer",
                display_name="Code Explainer",
                description="Giải thích kiến trúc, components và execution flows để onboard nhanh vào codebase mới",
                is_custom=False,
                has_lite=True,
            ),
            "pull_request_generator": TemplateInfo(
                template_id="pull_request_generator",
                display_name="PR Generator",
                description="Tạo tiêu đề và mô tả Pull Request chuẩn Conventional Commits từ git diff",
                is_custom=False,
                has_lite=True,
            ),
            # "dependency_auditor": TemplateInfo(
            #     template_id="dependency_auditor",
            #     display_name="Dependency Auditor",
            #     description="Kiểm tra dependencies về security vulnerabilities, licenses, và outdated packages",
            #     is_custom=False,
            #     has_lite=True,
            # ),
            "devops_reviewer": TemplateInfo(
                template_id="devops_reviewer",
                display_name="DevOps Reviewer",
                description="Review Docker, K8s, CI/CD pipelines và infrastructure configs về security và performance",
                is_custom=False,
                has_lite=True,
            ),
            "database_optimizer": TemplateInfo(
                template_id="database_optimizer",
                display_name="Database Optimizer",
                description="Tối ưu database queries, indexes, schema design và caching strategy",
                is_custom=False,
                has_lite=True,
            ),
            "logic_portability": TemplateInfo(
                template_id="logic_portability",
                display_name="Logic Portability Extractor",
                description="Trích xuất và đóng gói logic đã hoàn thiện thành module tái sử dụng được cho các project khác",
                is_custom=False,
                has_lite=True,
            ),
            "malware_forensics": TemplateInfo(
                template_id="malware_forensics",
                display_name="Malware Forensics Analyzer",
                description="Phân tích pháp y mã độc theo Zero-Trust: phát hiện backdoor, exfiltration, obfuscation, và supply-chain poisoning",
                is_custom=False,
                has_lite=True,
            ),
            "feature_roi_evaluator": TemplateInfo(
                template_id="feature_roi_evaluator",
                display_name="Feature ROI Evaluator",
                description="Đánh giá tính hữu ích, rào cản adoption, và ROI của các tính năng từ góc nhìn người dùng — so sánh với thị trường",
                is_custom=False,
                has_lite=True,
            ),
        }

    def list_templates(self) -> list[TemplateInfo]:
        available: list[TemplateInfo] = []
        for template_id, info in self._registry.items():
            template_path = _TEMPLATES_DIR / f"{template_id}.md"
            if template_path.exists():
                available.append(info)
        return available

    def load_template(self, template_id: str) -> str:
        if not self.handles(template_id):
            raise FileNotFoundError(
                f"Template '{template_id}' khong thuoc BuiltIn provider."
            )

        tier = _get_template_tier()
        if tier == "lite":
            lite_path = _TEMPLATES_DIR / "lite" / f"{template_id}.md"
            if lite_path.exists():
                return lite_path.read_text(encoding="utf-8").strip()

        pro_path = _TEMPLATES_DIR / f"{template_id}.md"
        if not pro_path.exists():
            raise FileNotFoundError(
                f"File template '{pro_path}' khong ton tai tren disk."
            )
        return pro_path.read_text(encoding="utf-8").strip()

    def get_template_info(self, template_id: str) -> TemplateInfo:
        if not self.handles(template_id):
            raise KeyError(f"Template '{template_id}' khong thuoc BuiltIn provider.")
        return self._registry[template_id]

    def handles(self, template_id: str) -> bool:
        return template_id in self._registry

    def delete_template(self, template_id: str) -> bool:
        # Built-in templates cannot be deleted by user
        return False


# ============================================================================
# Local Custom Provider
# ============================================================================
class LocalCustomTemplateProvider(TemplateProvider):
    """
    Load custom templates từ thư mục cấu hình của user (vd: ~/.config/synapse/templates/).
    Tên file là ID. Metadata được parse từ HTML comment ở header, vd: <!-- name: My UI, desc: ABC -->
    Nếu không có sẽ dùng fallback tên file.
    """

    def __init__(self) -> None:
        self.directory = CUSTOM_TEMPLATES_DIR
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)

    def _parse_metadata(self, file_path: Path) -> TemplateInfo:
        template_id = file_path.stem
        display_name = f"Custom: {template_id.replace('_', ' ').title()}"
        description = "User custom template"

        try:
            content = file_path.read_text(encoding="utf-8")
            # Parse `<!-- name: XYZ, desc: ABC -->` if present
            # Rất thô sơ, parse dòng đầu tiên
            first_line = content.split("\n")[0]
            if first_line.startswith("<!--") and first_line.endswith("-->"):
                inner_text = first_line[4:-3].strip()
                # Thử parse name và desc
                # Regex match format: `name: Foo, desc: Bar`
                name_match = re.search(r"name:\s*([^,]+)", inner_text, re.IGNORECASE)
                desc_match = re.search(r"desc:\s*([^,\-]+)", inner_text, re.IGNORECASE)

                if name_match:
                    display_name = name_match.group(1).strip()
                if desc_match:
                    description = desc_match.group(1).strip()
        except Exception:
            pass  # Ignore read errors, fallback to default properties

        return TemplateInfo(
            template_id=template_id,
            display_name=display_name,
            description=description,
            is_custom=True,
        )

    def list_templates(self) -> list[TemplateInfo]:
        self._ensure_dir()
        available: list[TemplateInfo] = []
        for file_path in self.directory.glob("*.md"):
            if file_path.is_file() and not file_path.name.startswith("_"):
                info = self._parse_metadata(file_path)
                available.append(info)
        return available

    _MAX_TEMPLATE_SIZE = 50 * 1024  # 50KB
    _FORBIDDEN_TEMPLATE_KEYWORDS = ["IGNORE ALL PREVIOUS", "SYSTEM:", "ADMIN MODE"]

    def load_template(self, template_id: str) -> str:
        self._ensure_dir()
        template_path = self.directory / f"{template_id}.md"
        if not template_path.exists() or not template_path.is_file():
            raise FileNotFoundError(
                f"Custom template '{template_path}' khong ton tai tren disk."
            )

        # Validate kich thuoc truoc khi doc
        file_size = template_path.stat().st_size
        if file_size > self._MAX_TEMPLATE_SIZE:
            raise ValueError(
                f"Template '{template_id}' qua lon: {file_size} bytes (toi da {self._MAX_TEMPLATE_SIZE} bytes)."
            )

        content = template_path.read_text(encoding="utf-8").strip()

        # Kiem tra forbidden keywords de ngan prompt injection
        upper_content = content.upper()
        for keyword in self._FORBIDDEN_TEMPLATE_KEYWORDS:
            if keyword in upper_content:
                raise ValueError(
                    f"Template '{template_id}' chua noi dung khong hop le: '{keyword}'."
                )

        # Strip frontmatter if present
        lines = content.split("\n")
        if lines and lines[0].startswith("<!--") and lines[0].endswith("-->"):
            content = "\n".join(lines[1:]).strip()

        return content

    def get_template_info(self, template_id: str) -> TemplateInfo:
        self._ensure_dir()
        template_path = self.directory / f"{template_id}.md"
        if not template_path.exists() or not template_path.is_file():
            raise KeyError(
                f"Custom template '{template_id}' khong ton tai tu LocalCustom."
            )
        return self._parse_metadata(template_path)

    def handles(self, template_id: str) -> bool:
        self._ensure_dir()
        template_path = self.directory / f"{template_id}.md"
        return template_path.exists() and template_path.is_file()

    def delete_template(self, template_id: str) -> bool:
        self._ensure_dir()
        template_path = self.directory / f"{template_id}.md"
        if template_path.exists() and template_path.is_file():
            try:
                template_path.unlink()
                return True
            except OSError:
                pass
        return False


# ============================================================================
# Manager API (Backward Compatible)
# ============================================================================
_PROVIDERS: list[TemplateProvider] = [
    BuiltInTemplateProvider(),
    LocalCustomTemplateProvider(),
]

_OUTPUT_FORMAT_PATH = _TEMPLATES_DIR / "_output_format.md"
_LITE_OUTPUT_FORMAT_PATH = _TEMPLATES_DIR / "lite" / "_output_format.md"


def _get_output_language() -> str:
    """Doc output_language tu settings, fallback ve Vietnamese."""
    try:
        from infrastructure.persistence.settings_manager import load_app_settings

        return load_app_settings().output_language
    except Exception:
        return "Vietnamese (tiếng Việt có dấu)"


def _get_template_tier() -> str:
    """Doc template tier tu settings, fallback ve 'lite'."""
    try:
        from infrastructure.persistence.settings_manager import load_app_settings

        tier = str(load_app_settings().template_tier).strip().lower()
        if tier in {"lite", "pro"}:
            return tier
    except Exception:
        pass
    return "lite"


def _append_output_format(content: str) -> str:
    """
    Strip phan '## Output format' cu (neu co) va append shared output format.

    Args:
        content: Noi dung template goc

    Returns:
        Template content + shared output format da inject output_language
    """
    # Strip phan output format cu de backward compat
    idx = content.find("\n## Output format")
    if idx != -1:
        content = content[:idx]

    # Chon shared output format theo tier (lite/pro)
    tier = _get_template_tier()
    fmt_path = _OUTPUT_FORMAT_PATH
    if tier == "lite":
        fmt_path = _LITE_OUTPUT_FORMAT_PATH
        if not fmt_path.exists():
            fmt_path = _OUTPUT_FORMAT_PATH

    # Doc shared output format
    try:
        fmt = fmt_path.read_text(encoding="utf-8")
    except OSError:
        return content.strip()

    # Inject output_language
    language = _get_output_language()
    fmt = fmt.replace("{{output_language}}", language)

    return content.strip() + "\n\n" + fmt.strip()


def list_templates() -> list[TemplateInfo]:
    """Liet ke tat ca prompt templates kha dung tu tat ca providers."""
    available: list[TemplateInfo] = []
    for provider in _PROVIDERS:
        available.extend(provider.list_templates())
    return available


def load_template(template_id: str) -> str:
    """
    Doc noi dung cua mot template theo ID, kem theo shared output format.

    Neu template da co section '## Output format', phan do se bi strip truoc
    khi append shared format (backward compatibility trong qua trinh migration).
    """
    for provider in _PROVIDERS:
        if provider.handles(template_id):
            content = provider.load_template(template_id)
            return _append_output_format(content)

    raise KeyError(f"Template '{template_id}' khong ton tai trong bat ky provider nao.")


def get_template_info(template_id: str) -> TemplateInfo:
    """Lay thong tin metadata cua mot template."""
    for provider in _PROVIDERS:
        if provider.handles(template_id):
            return provider.get_template_info(template_id)

    raise KeyError(f"Template '{template_id}' khong ton tai trong bat ky provider nao.")


def delete_template(template_id: str) -> bool:
    """Xoa template (chi ap dung voi custom templates)."""
    for provider in _PROVIDERS:
        if provider.handles(template_id):
            return provider.delete_template(template_id)
    return False
