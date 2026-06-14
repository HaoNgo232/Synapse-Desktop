# tests/domain/prompt/test_template_registry.py

import pytest
from domain.prompt.template_manager import (
    list_templates,
    load_template,
)

def test_list_returns_exactly_7_builtin():
    # Built-in templates should have only 7.
    builtin = [t for t in list_templates() if not t.is_custom]
    assert len(builtin) == 7
    expected_ids = {
        "bug_hunter",
        "security_auditor",
        "architecture_reviewer",
        "code_explainer",
        "test_writer",
        "performance_optimizer",
        "doc_generator",
    }
    assert {t.template_id for t in builtin} == expected_ids

def test_load_template_no_longer_needs_tier():
    # Gọi với tier hay không tier đều trả về cùng 1 nội dung
    content_default = load_template("bug_hunter")
    content_lite = load_template("bug_hunter", tier="lite")
    content_pro = load_template("bug_hunter", tier="pro")
    assert content_default == content_lite
    assert content_default == content_pro

def test_custom_templates_unaffected(tmp_path, monkeypatch):
    import domain.prompt.template_manager as tm
    monkeypatch.setattr(tm, "CUSTOM_TEMPLATES_DIR", tmp_path)
    from domain.prompt.template_manager import LocalCustomTemplateProvider
    
    custom_file = tmp_path / "custom_test.md"
    custom_file.write_text("Custom Content", encoding="utf-8")
    
    provider = LocalCustomTemplateProvider()
    assert provider.handles("custom_test")
    assert provider.load_template("custom_test") == "Custom Content"

def test_removed_template_ids_raise_key_error():
    # Ví dụ template "refactoring_expert" đã bị xóa khỏi registry
    with pytest.raises(KeyError):
        load_template("refactoring_expert")

def test_lite_dir_not_loaded():
    import domain.prompt.template_manager as tm
    # Đảm bảo không load từ thư mục lite
    lite_file = tm._TEMPLATES_DIR / "lite" / "bug_hunter.md"
    if lite_file.exists():
        content_lite_file = lite_file.read_text(encoding="utf-8").strip()
        content_loaded = load_template("bug_hunter")
        # Bản Pro và Lite có nội dung khác nhau, bản Pro chứa "Senior QA"
        assert content_loaded != content_lite_file

def test_all_7_templates_have_content():
    expected_ids = [
        "bug_hunter",
        "security_auditor",
        "architecture_reviewer",
        "code_explainer",
        "test_writer",
        "performance_optimizer",
        "doc_generator",
    ]
    for tid in expected_ids:
        content = load_template(tid)
        assert len(content) > 0
