"""
Tests cho ProjectMetadataService.
Viet tests truoc, implement sau (TDD).
"""

from pathlib import Path

from domain.relationships.graph import RelationshipGraph
from domain.relationships.types import Edge, EdgeKind
from application.services.project_metadata_service import ProjectMetadataService


def _make_graph_linear() -> RelationshipGraph:
    """Graph tuyen tinh: a -> b -> c -> d"""
    g = RelationshipGraph()
    g.add_edges(
        [
            Edge("a.py", "b.py", EdgeKind.IMPORTS),
            Edge("b.py", "c.py", EdgeKind.CALLS),
            Edge("c.py", "d.py", EdgeKind.CALLS),
        ]
    )
    return g


def _make_graph_star() -> RelationshipGraph:
    """Graph ngoi sao: nhieu file tro vao hub.py"""
    g = RelationshipGraph()
    g.add_edges(
        [
            Edge("x.py", "hub.py", EdgeKind.IMPORTS),
            Edge("y.py", "hub.py", EdgeKind.IMPORTS),
            Edge("z.py", "hub.py", EdgeKind.IMPORTS),
            Edge("hub.py", "util.py", EdgeKind.CALLS),
        ]
    )
    return g


class TestProjectMetadataServiceTopFiles:
    def setup_method(self):
        self.service = ProjectMetadataService()

    def test_top_files_empty_graph(self):
        """Graph rong -> top_files rong."""
        g = RelationshipGraph()
        result = self.service.compute(g, workspace_root=Path("/ws"))
        assert result.top_files == []

    def test_top_files_sorted_by_score_desc(self):
        """File co in_edges cao hon phai dung truoc."""
        g = _make_graph_star()
        result = self.service.compute(g, workspace_root=Path("/ws"))
        # hub.py co in_edges=3, out_edges=1 -> score = 3*2+1 = 7
        assert result.top_files[0].path == "hub.py"
        assert result.top_files[0].in_edges == 3
        assert result.top_files[0].out_edges == 1
        assert result.top_files[0].score == 7

    def test_top_files_limit(self):
        """Khong tra ve qua limit file."""
        # Build graph 20 nodes
        g = RelationshipGraph()
        for i in range(20):
            g.add_edge(Edge(f"file{i}.py", "core.py", EdgeKind.IMPORTS))
        result = self.service.compute(g, workspace_root=Path("/ws"), top_n=5)
        assert len(result.top_files) <= 5

    def test_score_formula(self):
        """score = in_edges * 2 + out_edges."""
        g = _make_graph_linear()
        result = self.service.compute(g, workspace_root=Path("/ws"))
        # b.py: in=1 (a->b), out=1 (b->c) -> score = 3
        b = next(f for f in result.top_files if f.path.endswith("b.py"))
        assert b.in_edges == 1
        assert b.out_edges == 1
        assert b.score == 3


class TestProjectMetadataServiceModules:
    def setup_method(self):
        self.service = ProjectMetadataService()

    def test_modules_empty_graph(self):
        """Graph rong -> modules rong."""
        g = RelationshipGraph()
        result = self.service.compute(g, workspace_root=Path("/ws"))
        assert result.modules == []

    def test_modules_grouped_by_directory(self):
        """Files cung directory duoc nhom lai thanh 1 module."""
        g = RelationshipGraph()
        g.add_edges(
            [
                Edge("domain/auth/login.py", "domain/auth/jwt.py", EdgeKind.IMPORTS),
                Edge("domain/auth/jwt.py", "domain/auth/keys.py", EdgeKind.CALLS),
                Edge("presentation/view.py", "domain/auth/login.py", EdgeKind.IMPORTS),
            ]
        )
        result = self.service.compute(g, workspace_root=Path("/ws"))
        module_roots = [m.root for m in result.modules]
        # domain/auth/ phai la 1 module (co 3 files noi bo va 2 internal edges)
        assert any("domain/auth" in r for r in module_roots)

    def test_modules_sorted_by_internal_edges_desc(self):
        """Module co nhieu internal edges hon phai dung truoc."""
        g = RelationshipGraph()
        # Module A co 3 internal edges
        g.add_edges(
            [
                Edge("modA/f1.py", "modA/f2.py", EdgeKind.IMPORTS),
                Edge("modA/f2.py", "modA/f3.py", EdgeKind.IMPORTS),
                Edge("modA/f3.py", "modA/f1.py", EdgeKind.IMPORTS),
            ]
        )
        # Module B chi co 1 internal edge
        g.add_edge(Edge("modB/g1.py", "modB/g2.py", EdgeKind.IMPORTS))
        result = self.service.compute(g, workspace_root=Path("/ws"))
        assert result.modules[0].internal_edges >= result.modules[-1].internal_edges


class TestProjectMetadataServiceFlows:
    def setup_method(self):
        self.service = ProjectMetadataService()

    def test_flows_empty_graph(self):
        """Graph rong -> sample_flows rong."""
        g = RelationshipGraph()
        result = self.service.compute(g, workspace_root=Path("/ws"))
        assert result.sample_flows == []

    def test_flows_contain_arrows(self):
        """Sample flows phai chua '->' separator."""
        g = _make_graph_linear()
        result = self.service.compute(g, workspace_root=Path("/ws"))
        if result.sample_flows:
            assert "->" in result.sample_flows[0]

    def test_flows_start_from_entry_points(self):
        """Flows phai bat dau tu file khong co in_edges (entry point)."""
        g = _make_graph_linear()
        # a.py la entry point (khong ai import a.py)
        result = self.service.compute(g, workspace_root=Path("/ws"))
        if result.sample_flows:
            first_flow = result.sample_flows[0]
            assert first_flow.startswith("a.py")

    def test_flows_limited(self):
        """Khong tra ve qua so luong flows cho phep."""
        g = RelationshipGraph()
        # Tao nhieu entry points
        for i in range(20):
            g.add_edge(Edge(f"entry{i}.py", "sink.py", EdgeKind.CALLS))
        result = self.service.compute(g, workspace_root=Path("/ws"), max_flows=3)
        assert len(result.sample_flows) <= 3


class TestProjectMetadataServiceFingerprint:
    def setup_method(self):
        self.service = ProjectMetadataService()

    def test_same_graph_same_fingerprint(self):
        """Cung cau truc graph -> cung fingerprint."""
        g1 = _make_graph_linear()
        g2 = _make_graph_linear()
        r1 = self.service.compute(g1, workspace_root=Path("/ws"))
        r2 = self.service.compute(g2, workspace_root=Path("/ws"))
        assert r1.graph_fingerprint == r2.graph_fingerprint

    def test_different_graph_different_fingerprint(self):
        """Graph khac nhau -> fingerprint khac nhau."""
        g1 = _make_graph_linear()
        g2 = _make_graph_star()
        r1 = self.service.compute(g1, workspace_root=Path("/ws"))
        r2 = self.service.compute(g2, workspace_root=Path("/ws"))
        assert r1.graph_fingerprint != r2.graph_fingerprint

    def test_fingerprint_is_string(self):
        """Fingerprint phai la string."""
        g = _make_graph_linear()
        result = self.service.compute(g, workspace_root=Path("/ws"))
        assert isinstance(result.graph_fingerprint, str)
        assert len(result.graph_fingerprint) > 0
