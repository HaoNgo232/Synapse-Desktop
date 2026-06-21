import unittest
from infrastructure.adapters.code_intelligence.base_backend import CodeIntelligenceBackend

class TestBaseBackend(unittest.TestCase):
    def test_abstract_instantiation(self):
        with self.assertRaises(TypeError):
            CodeIntelligenceBackend()  # type: ignore
