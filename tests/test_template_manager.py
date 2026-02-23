"""
Unit tests cho Template Manager module.

Test cac function:
- list_templates(): Liet ke templates kha dung
- load_template(): Doc noi dung template theo ID
from core.prompting.template_manager import LocalCustomTemplateProvider
import core.prompting.template_manager as tm
- get_template_info(): Lay metadata cua template
"""

import pytest

from core.prompting.template_manager import (
    list_templates,
    load_template,
    get_template_info,
    TemplateInfo,
    LocalCustomTemplateProvider,
)
import core.prompting.template_manager as tm


class TestListTemplates:
    """Test list_templates() function."""

    def test_returns_list(self):
        """list_templates tra ve list."""
        result = list_templates()
        assert isinstance(result, list)

    def test_all_templates_are_template_info(self):
        """Moi item la TemplateInfo."""
        result = list_templates()
        for item in result:
            assert isinstance(item, TemplateInfo)

    def test_has_expected_templates(self):
        """Co du 9 templates da dang ky (BuiltIn)."""
        result = list_templates()
        ids = {t.template_id for t in result}
        expected = {
            "bug_hunter",
            "security_auditor",
            "refactoring_expert",
            "doc_generator",
            "performance_optimizer",
            "ui_ux_reviewer",
            "test_writer",
            "api_reviewer",
            "flow_checker",
        }
        # Do file local có thể chứa custom template, assert is superset
        assert expected.issubset(ids)

    def test_each_has_display_name(self):
        """Moi template co display_name khong rong."""
        for t in list_templates():
            assert t.display_name, f"Template {t.template_id} thieu display_name"

    def test_each_has_description(self):
        """Moi template co description khong rong."""
        for t in list_templates():
            assert t.description, f"Template {t.template_id} thieu description"


class TestLoadTemplate:
    """Test load_template() function."""

    def test_load_bug_hunter(self):
        """Load bug_hunter thanh cong."""
        content = load_template("bug_hunter")
        assert "Senior QA" in content
        assert "<thinking>" in content

    def test_load_security_auditor(self):
        """Load security_auditor thanh cong."""
        content = load_template("security_auditor")
        assert "OWASP" in content
        assert "Security Audit Report" in content

    def test_load_refactoring_expert(self):
        """Load refactoring_expert thanh cong."""
        content = load_template("refactoring_expert")
        assert "SOLID" in content
        assert "Before/After" in content

    def test_load_doc_generator(self):
        """Load doc_generator thanh cong."""
        content = load_template("doc_generator")
        assert "README.md" in content
        assert "Technical Writer" in content

    def test_load_performance_optimizer(self):
        """Load performance_optimizer thanh cong."""
        content = load_template("performance_optimizer")
        assert "Big O" in content
        assert "memory" in content.lower()

    def test_load_nonexistent_raises_key_error(self):
        """Load template khong ton tai raise KeyError."""
        with pytest.raises(KeyError, match="khong ton tai"):
            load_template("nonexistent_template")

    def test_all_templates_not_empty(self):
        """Tat ca templates co noi dung khong rong."""
        for t in list_templates():
            if getattr(t, "is_custom", False):
                continue
            content = load_template(t.template_id)
            assert len(content) > 50, f"Template {t.template_id} qua ngan"


class TestGetTemplateInfo:
    """Test get_template_info() function."""

    def test_get_existing(self):
        """Lay info cua template ton tai."""
        info = get_template_info("bug_hunter")
        assert info.template_id == "bug_hunter"
        assert info.display_name == "Bug Hunter"

    def test_get_nonexistent_raises_key_error(self):
        """Lay info cua template khong ton tai raise KeyError."""
        with pytest.raises(KeyError, match="khong ton tai"):
            get_template_info("nonexistent_template")

    def test_frozen_dataclass(self):
        """TemplateInfo la frozen (immutable)."""
        info = get_template_info("bug_hunter")
        with pytest.raises(AttributeError):
            info.display_name = "Hacked"  # type: ignore[misc]


class TestLocalCustomTemplateProvider:
    """Test LocalCustomTemplateProvider logic."""

    @pytest.fixture
    def custom_provider(self, tmp_path, monkeypatch):
        monkeypatch.setattr(tm, "CUSTOM_TEMPLATES_DIR", tmp_path)
        return LocalCustomTemplateProvider()

    def test_list_and_parse_metadata(self, custom_provider, tmp_path):
        """Load metadata dung tu custom frontmatter HTML."""
        test_md = tmp_path / "my_custom.md"
        test_md.write_text(
            "<!-- name: Custom Name, desc: Custom Desc -->\nNoi dung", encoding="utf-8"
        )

        templates = custom_provider.list_templates()
        assert len(templates) == 1
        assert templates[0].template_id == "my_custom"
        assert templates[0].display_name == "Custom Name"
        assert templates[0].description == "Custom Desc"

    def test_fallback_metadata_if_no_header(self, custom_provider, tmp_path):
        """Neu khong co header HTML, dung default metadata."""
        test_md = tmp_path / "hello_world.md"
        test_md.write_text("Hello World Content", encoding="utf-8")

        templates = custom_provider.list_templates()
        assert len(templates) == 1
        assert templates[0].template_id == "hello_world"
        assert templates[0].display_name == "Custom: Hello World"
        assert templates[0].description == "User custom template"

    def test_load_template(self, custom_provider, tmp_path):
        """Doc duoc noi dung (da tu dong cat bo frontmatter)."""
        test_md = tmp_path / "my_custom.md"
        test_md.write_text("<!-- name: X -->\nContent", encoding="utf-8")
        assert custom_provider.load_template("my_custom") == "Content"

    def test_get_template_info(self, custom_provider, tmp_path):
        """Lay info cua isolated file."""
        test_md = tmp_path / "my_custom.md"
        test_md.write_text("<!-- name: X, desc: Y -->\nContent", encoding="utf-8")
        info = custom_provider.get_template_info("my_custom")
        assert info.display_name == "X"
        assert info.description == "Y"
