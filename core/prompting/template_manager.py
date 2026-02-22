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

from config.paths import APP_DIR

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
            ),
            "security_auditor": TemplateInfo(
                template_id="security_auditor",
                display_name="Security Auditor",
                description="Kiểm tra lỗ hổng bảo mật theo OWASP Top 10, phát hiện secrets và hardcoded credentials",
                is_custom=False,
            ),
            "refactoring_expert": TemplateInfo(
                template_id="refactoring_expert",
                display_name="Refactoring Expert",
                description="Đề xuất cải thiện code theo SOLID, DRY, Clean Code và giảm độ phức tạp",
                is_custom=False,
            ),
            "doc_generator": TemplateInfo(
                template_id="doc_generator",
                display_name="Documentation Generator",
                description="Tạo hoặc cập nhật README, tài liệu kiến trúc từ codebase (chế độ cập nhật thông minh)",
                is_custom=False,
            ),
            "performance_optimizer": TemplateInfo(
                template_id="performance_optimizer",
                display_name="Performance Optimizer",
                description="Phân tích Big O, memory leaks, blocking operations và đề xuất tối ưu hóa",
                is_custom=False,
            ),
            "ui_ux_reviewer": TemplateInfo(
                template_id="ui_ux_reviewer",
                display_name="UI/UX Reviewer",
                description="Review giao diện, accessibility, tính nhất quán, màu sắc, animations và trải nghiệm người dùng",
                is_custom=False,
            ),
            "test_writer": TemplateInfo(
                template_id="test_writer",
                display_name="Test Writer",
                description="Tạo Unit Tests, Integration Tests theo AAA pattern và nguyên tắc TDD",
                is_custom=False,
            ),
            "api_reviewer": TemplateInfo(
                template_id="api_reviewer",
                display_name="API Reviewer",
                description="Review thiết kế API (REST, GraphQL, gRPC, component APIs) về contract, consistency, performance và security",
                is_custom=False,
            ),
            "flow_checker": TemplateInfo(
                template_id="flow_checker",
                display_name="Flow Checker",
                description="Phân tích execution flow, data flow, control flow và phát hiện vấn đề về luồng xử lý",
                is_custom=False,
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
        template_path = _TEMPLATES_DIR / f"{template_id}.md"
        if not template_path.exists():
            raise FileNotFoundError(
                f"File template '{template_path}' khong ton tai tren disk."
            )
        return template_path.read_text(encoding="utf-8").strip()

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
                # Thử parse name vả desc
                # Regex match format: `name: Foo, desc: Bar`
                name_match = re.search(r"name:\s*([^,]+)", inner_text, re.IGNORECASE)
                desc_match = re.search(r"desc:\s*(.+)", inner_text, re.IGNORECASE)

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
            if file_path.is_file():
                info = self._parse_metadata(file_path)
                available.append(info)
        return available

    def load_template(self, template_id: str) -> str:
        self._ensure_dir()
        template_path = self.directory / f"{template_id}.md"
        if not template_path.exists() or not template_path.is_file():
            raise FileNotFoundError(
                f"Custom template '{template_path}' khong ton tai tren disk."
            )
        return template_path.read_text(encoding="utf-8").strip()

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


def list_templates() -> list[TemplateInfo]:
    """Liet ke tat ca prompt templates kha dung tu tat ca providers."""
    available: list[TemplateInfo] = []
    for provider in _PROVIDERS:
        available.extend(provider.list_templates())
    return available


def load_template(template_id: str) -> str:
    """Doc noi dung cua mot template theo ID."""
    for provider in _PROVIDERS:
        if provider.handles(template_id):
            return provider.load_template(template_id)

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
