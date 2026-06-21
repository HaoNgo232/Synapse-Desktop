import unittest
from pathlib import Path
from infrastructure.adapters.code_intelligence.router_adapter import CodeIntelligenceRouterAdapter
from infrastructure.adapters.code_intelligence.python_ast_backend import PythonAstBackend
from infrastructure.adapters.code_intelligence.regex_fallback_backend import RegexFallbackBackend

class TestRouterAdapter(unittest.TestCase):
    def test_fallback_flow(self):
        backends = [PythonAstBackend(), RegexFallbackBackend()]
        adapter = CodeIntelligenceRouterAdapter(backends)

        # Test python routing
        res_py = adapter.parse_file(Path("test.py"), "def sample():\n    pass")
        self.assertEqual(res_py.language, "py")

        # Test typescript routing (falls back to Regex)
        res_ts = adapter.parse_file(Path("test.ts"), "export class Item {}")
        self.assertEqual(res_ts.language, "ts")
