import unittest
from pathlib import Path
from infrastructure.adapters.code_intelligence.regex_fallback_backend import RegexFallbackBackend

class TestRegexFallbackBackend(unittest.TestCase):
    def test_supported_extensions(self):
        backend = RegexFallbackBackend()
        self.assertIn("js", backend.get_supported_extensions())
        self.assertIn("go", backend.get_supported_extensions())

    def test_parse_typescript(self):
        backend = RegexFallbackBackend()
        content = "export class HelloService {\n  doWork() {}\n}\n"
        result = backend.parse_file(Path("hello.ts"), content)
        self.assertIsNotNone(result)
        if result:
            self.assertEqual(result.language, "ts")
            self.assertIn("export class HelloService", result.outline)
