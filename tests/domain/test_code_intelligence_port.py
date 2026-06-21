import unittest
from pathlib import Path
from domain.ports.code_intelligence_port import ParsedCodeInfo, ICodeIntelligencePort

class TestCodeIntelligencePort(unittest.TestCase):
    def test_dto_instantiation(self):
        dto = ParsedCodeInfo(
            file_path=Path("test.py"),
            language="python",
            symbols=[],
            relationships=[],
            imports=["import os"],
            outline=["def test():"]
        )
        self.assertEqual(dto.language, "python")
        self.assertEqual(dto.imports, ["import os"])

    def test_abstract_class(self):
        with self.assertRaises(TypeError):
            ICodeIntelligencePort()  # type: ignore
