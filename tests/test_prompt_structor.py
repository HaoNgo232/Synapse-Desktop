"""
Unit tests cho Prompt Structor format (XML o cap do project va Plain text structured).
Theo yeu cau:
- XML: <project><metadata><structure><files>
- Plain: ===== FILE: ... ===== LAYER: ... ROLE: ... DEPENDS ON: ... <code>
"""

import pytest
from pathlib import Path
from domain.prompt.formatters.xml import format_files_xml
from domain.prompt.formatters.plain import format_files_plain
from domain.prompt.assembler import assemble_prompt
from shared.types.prompt_types import FileEntry
from presentation.config.output_format import OutputStyle


def _make_entry(
    path="application/services/test.py",
    content="print('hello')",
    layer="application",
    role="Service",
    deps=["domain.test"],
):
    return FileEntry(
        path=Path(path),
        display_path=path,
        content=content,
        error=None,
        language="python",
        layer=layer,
        role=role,
        dependencies=deps,
    )


class TestPromptStructorXml:
    def test_xml_project_structure(self):
        """XML format phai co <file> voi metadata (layer, role, deps) va CDATA content."""
        entries = [_make_entry()]

        result = format_files_xml(entries)

        assert '<file path="application/services/test.py">' in result
        assert "<layer>application</layer>" in result
        assert "<role>Service</role>" in result
        assert "<dependencies>" in result
        assert "<import>domain.test</import>" in result
        assert "<content><![CDATA[" in result
        assert "print('hello')" in result

    def test_xml_full_project_assembly(self, tmp_path):
        """Assemble XML project structure hoàn chỉnh với <project> và <metadata>."""
        result = assemble_prompt(
            file_map='<structure><file path="test.py"/></structure>',
            file_contents='<files><file path="test.py"><code>print(1)</code></file></files>',
            workspace_root=tmp_path,
            output_style=OutputStyle.XML,
        )

        assert "<project>" in result
        assert "<metadata>" in result
        assert "<name>" in result
        assert "unknown-project" not in result  # Check that name is not default
        assert tmp_path.name in result  # Check that it's the actual name
        assert "<generated_at>" in result
        assert "</project>" in result
        assert "<structure>" in result
        assert "<files>" in result


class TestPromptStructorPlain:
    def test_plain_structured_format(self):
        """Plain format phai co delimiter consistent va metadata o dau."""
        entries = [
            _make_entry(
                path="application/services/prompt_build_service.py",
                role="ApplicationService",
            )
        ]

        result = format_files_plain(entries)

        # 1. Delimiter consistency
        assert (
            "===== FILE: application/services/prompt_build_service.py =====" in result
        )

        # 2. Metadata before code
        lines = result.splitlines()
        # Header o lines[0]
        assert (
            lines[0] == "===== FILE: application/services/prompt_build_service.py ====="
        )
        assert "LAYER: application" in result
        assert "ROLE: ApplicationService" in result
        assert "DEPENDS ON: domain.test" in result
        assert "print('hello')" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
