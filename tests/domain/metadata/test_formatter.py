"""
Tests cho format_project_structure() formatter.
Output phai la string XML-style de inject vao prompt.
"""

from domain.metadata.project_metadata import FileScore, ModuleInfo, ProjectMetadata
from domain.metadata.formatter import format_project_structure


def _make_metadata(top_files=None, modules=None, sample_flows=None) -> ProjectMetadata:
    return ProjectMetadata(
        graph_fingerprint="abc123",
        file_count=10,
        edge_count=20,
        top_files=top_files or [],
        modules=modules or [],
        sample_flows=sample_flows or [],
    )


class TestFormatProjectStructure:
    def test_returns_string(self):
        """format_project_structure phai tra ve string."""
        result = format_project_structure(_make_metadata())
        assert isinstance(result, str)

    def test_empty_metadata_returns_empty_string(self):
        """Metadata rong -> string rong (khong chen section thua vao prompt)."""
        result = format_project_structure(_make_metadata())
        assert result.strip() == ""

    def test_contains_semantic_index_tag(self):
        """Output phai chua tag <semantic_index> de phan biet voi phan khac."""
        fs = FileScore(path="core.py", score=10, in_edges=4, out_edges=2)
        result = format_project_structure(_make_metadata(top_files=[fs]))
        assert "<semantic_index>" in result
        assert "</semantic_index>" in result

    def test_top_files_included(self):
        """Top files phai hien thi trong output voi path va score."""
        files = [
            FileScore(path="service/auth.py", score=20, in_edges=8, out_edges=4),
            FileScore(path="domain/graph.py", score=15, in_edges=6, out_edges=3),
        ]
        result = format_project_structure(_make_metadata(top_files=files))
        assert "service/auth.py" in result
        assert "domain/graph.py" in result

    def test_modules_included(self):
        """Modules phai hien thi trong output."""
        modules = [
            ModuleInfo(root="domain/relationships/", file_count=5, internal_edges=12),
            ModuleInfo(root="infrastructure/ai/", file_count=3, internal_edges=4),
        ]
        result = format_project_structure(_make_metadata(modules=modules))
        assert "domain/relationships/" in result
        assert "infrastructure/ai/" in result

    def test_flows_included(self):
        """Sample flows phai hien thi trong output."""
        flows = ["view.py -> controller.py -> service.py"]
        result = format_project_structure(_make_metadata(sample_flows=flows))
        assert "view.py -> controller.py -> service.py" in result

    def test_output_is_compact(self):
        """Output khong qua dai (toi da ~30 dong de tiet kiem tokens)."""
        files = [
            FileScore(path=f"file{i}.py", score=10 - i, in_edges=i, out_edges=1)
            for i in range(5)
        ]
        modules = [
            ModuleInfo(root=f"mod{i}/", file_count=3, internal_edges=2 - i)
            for i in range(3)
        ]
        flows = [f"a{i}.py -> b{i}.py" for i in range(3)]
        result = format_project_structure(
            _make_metadata(top_files=files, modules=modules, sample_flows=flows)
        )
        line_count = len(result.strip().splitlines())
        assert line_count <= 40, f"Output qua dai: {line_count} dong"
