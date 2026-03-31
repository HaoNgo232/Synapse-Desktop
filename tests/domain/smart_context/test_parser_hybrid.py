import unittest
from domain.smart_context.parser import smart_parse


class TestParserHybrid(unittest.TestCase):
    def test_smart_parse_hybrid_python(self):
        content = """import os
from pathlib import Path
from domain.types import Symbol

@dataclass
class MyClass:
    \"\"\"A docstring.\"\"\"
    def my_method(self, name: str) -> None:
        print(f"Hello {name}")
        self._internal_call()

    def _internal_call(self):
        pass
"""
        file_path = "test.py"
        result = smart_parse(file_path, content)
        self.assertIsNotNone(result)
        if result:
            # Kiểm tra: Giữ lại imports
            self.assertIn("import os", result)
            self.assertIn("from pathlib import Path", result)
            self.assertIn("from domain.types import Symbol", result)

            # Kiểm tra: Có signatures của class và methods
            self.assertIn("class MyClass", result)
            self.assertIn("def my_method(self, name: str) -> None", result)

            # Kiểm tra: Có marker ⋮----
            self.assertIn("⋮----", result)

            # Kiểm tra: KHÔNG CÓ line numbers (L1-10)
            self.assertNotIn("(L", result)

            # Kiểm tra: KHÔNG CÓ call graph nội bộ (Internal relationships section)
            self.assertNotIn("## Relationships", result)
            self.assertNotIn("calls", result)

    def test_smart_parse_hybrid_ts(self):
        content = """import { Injectable } from '@nestjs/common';
import { Service } from './service';

@Injectable()
export class MyService {
  constructor(private readonly service: Service) {}

  async doSomething(id: string): Promise<void> {
    await this.service.call(id);
  }
}
"""
        file_path = "src/service.ts"
        result = smart_parse(file_path, content)
        self.assertIsNotNone(result)
        if result:
            # Kiểm tra imports
            self.assertIn("import { Injectable }", result)

            # Kiểm tra signatures
            self.assertIn("export class MyService", result)
            self.assertIn("async doSomething(id: string): Promise<void>", result)

            # Kiểm tra marker
            self.assertIn("⋮----", result)

    def test_smart_parse_hybrid_go(self):
        content = """package main

import (
	"fmt"
	"net/http"
)

// Main function
func main() {
	fmt.Println("Hello")
}
"""
        file_path = "main.go"
        result = smart_parse(file_path, content)
        self.assertIsNotNone(result)
        if result:
            # Kiểm tra imports (Go query) - raw import sau khi strip quote
            self.assertIn("fmt", result)
            self.assertIn("net/http", result)

            # Kiểm tra signatures
            self.assertIn("func main()", result)

            # Kiểm tra marker
            self.assertIn("⋮----", result)


if __name__ == "__main__":
    unittest.main()
