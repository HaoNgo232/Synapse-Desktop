"""
Tests cho ProjectMetadata domain model.
"""

from domain.metadata.project_metadata import (
    FileScore,
    ModuleInfo,
    ProjectMetadata,
)


class TestFileScore:
    def test_has_required_fields(self):
        """FileScore phai co path, score, in_edges, out_edges."""
        fs = FileScore(path="foo.py", score=10, in_edges=4, out_edges=2)
        assert fs.path == "foo.py"
        assert fs.score == 10
        assert fs.in_edges == 4
        assert fs.out_edges == 2


class TestModuleInfo:
    def test_has_required_fields(self):
        """ModuleInfo phai co root, file_count, internal_edges."""
        mi = ModuleInfo(root="domain/relationships/", file_count=5, internal_edges=12)
        assert mi.root == "domain/relationships/"
        assert mi.file_count == 5
        assert mi.internal_edges == 12


class TestProjectMetadata:
    def test_can_construct_empty(self):
        """ProjectMetadata co the tao voi lists rong (project moi)."""
        pm = ProjectMetadata(
            graph_fingerprint="abc123",
            file_count=0,
            edge_count=0,
            top_files=[],
            modules=[],
            sample_flows=[],
        )
        assert pm.graph_fingerprint == "abc123"
        assert pm.file_count == 0
        assert pm.top_files == []
        assert pm.modules == []
        assert pm.sample_flows == []

    def test_can_construct_full(self):
        """ProjectMetadata chua day du thong tin cau truc."""
        fs = FileScore(path="main.py", score=20, in_edges=8, out_edges=4)
        mi = ModuleInfo(root="domain/", file_count=10, internal_edges=25)
        pm = ProjectMetadata(
            graph_fingerprint="sha256:xyz",
            file_count=50,
            edge_count=120,
            top_files=[fs],
            modules=[mi],
            sample_flows=["a.py -> b.py -> c.py"],
        )
        assert len(pm.top_files) == 1
        assert len(pm.modules) == 1
        assert pm.sample_flows[0] == "a.py -> b.py -> c.py"
