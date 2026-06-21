# Code Intelligence Port Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize the source code parsing, symbol extraction, and relationship tracing logic under a single `ICodeIntelligencePort` interface, removing duplication and isolating external dependencies (like Tree-sitter) from the core domain.

**Architecture:** Introduce `ICodeIntelligencePort` returning a unified DTO `ParsedCodeInfo`. Implement a router adapter in infrastructure coordinating TreeSitter, Python AST, and Regex Fallback backends, and registering it in `DomainRegistry`.

**Tech Stack:** Python 3.10+, Tree-sitter (SCM queries), Python Standard `ast` module, regular expressions, Pytest.

## Global Constraints

- Never commit changes automatically without user approval (prepare git stage/commit commands only).
- Keep all type annotations strictly compliant with Pyright strict mode.
- Use absolute imports throughout all new files.

---

### Task 1: Create ICodeIntelligencePort and DTO
**Files:**
- Create: `domain/ports/code_intelligence_port.py`
- Test: `tests/domain/test_code_intelligence_port.py`

**Interfaces:**
- Produces: `ParsedCodeInfo` (dataclass) and `ICodeIntelligencePort` (interface)

- [ ] **Step 1: Write the failing test**
  Create `tests/domain/test_code_intelligence_port.py`:
  ```python
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
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/domain/test_code_intelligence_port.py -v`
  Expected: ModuleNotFoundError or ImportError.

- [ ] **Step 3: Write minimal implementation**
  Create `domain/ports/code_intelligence_port.py`:
  ```python
  import abc
  from dataclasses import dataclass, field
  from pathlib import Path
  from typing import List, Optional
  from domain.codemap.types import Symbol, Relationship

  @dataclass
  class ParsedCodeInfo:
      file_path: Path
      language: str
      symbols: List[Symbol] = field(default_factory=list)
      relationships: List[Relationship] = field(default_factory=list)
      imports: List[str] = field(default_factory=list)
      outline: List[str] = field(default_factory=list)

  class ICodeIntelligencePort(abc.ABC):
      @abc.abstractmethod
      def parse_file(self, file_path: Path, content: str) -> ParsedCodeInfo:
          pass

      @abc.abstractmethod
      def generate_repo_map(
          self,
          file_paths: List[str],
          workspace_root: Optional[Path] = None,
          max_files: int = 500,
      ) -> str:
          pass
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/domain/test_code_intelligence_port.py -v`
  Expected: PASS

- [ ] **Step 5: Stage files**
  Prepare staging commands:
  `git add domain/ports/code_intelligence_port.py tests/domain/test_code_intelligence_port.py`

---

### Task 2: Create Base Backend Class
**Files:**
- Create: `infrastructure/adapters/code_intelligence/base_backend.py`
- Test: `tests/infrastructure/code_intelligence/test_base_backend.py`

**Interfaces:**
- Consumes: `ParsedCodeInfo`
- Produces: `CodeIntelligenceBackend` (interface)

- [ ] **Step 1: Write the failing test**
  Create `tests/infrastructure/code_intelligence/test_base_backend.py`:
  ```python
  import unittest
  from infrastructure.adapters.code_intelligence.base_backend import CodeIntelligenceBackend

  class TestBaseBackend(unittest.TestCase):
      def test_abstract_instantiation(self):
          with self.assertRaises(TypeError):
              CodeIntelligenceBackend()  # type: ignore
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/infrastructure/code_intelligence/test_base_backend.py -v`
  Expected: ModuleNotFoundError or ImportError.

- [ ] **Step 3: Write minimal implementation**
  Create `infrastructure/adapters/code_intelligence/base_backend.py`:
  ```python
  import abc
  from pathlib import Path
  from typing import Optional, List
  from domain.ports.code_intelligence_port import ParsedCodeInfo

  class CodeIntelligenceBackend(abc.ABC):
      @abc.abstractmethod
      def get_supported_extensions(self) -> List[str]:
          pass

      @abc.abstractmethod
      def parse_file(self, file_path: Path, content: str) -> Optional[ParsedCodeInfo]:
          pass
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/infrastructure/code_intelligence/test_base_backend.py -v`
  Expected: PASS

- [ ] **Step 5: Stage files**
  Prepare staging commands:
  `git add infrastructure/adapters/code_intelligence/base_backend.py tests/infrastructure/code_intelligence/test_base_backend.py`

---

### Task 3: Implement Python AST Backend
**Files:**
- Create: `infrastructure/adapters/code_intelligence/python_ast_backend.py`
- Test: `tests/infrastructure/code_intelligence/test_python_ast_backend.py`

**Interfaces:**
- Consumes: `CodeIntelligenceBackend`
- Produces: `PythonAstBackend` class

- [ ] **Step 1: Write the failing test**
  Create `tests/infrastructure/code_intelligence/test_python_ast_backend.py`:
  ```python
  import unittest
  from pathlib import Path
  from infrastructure.adapters.code_intelligence.python_ast_backend import PythonAstBackend

  class TestPythonAstBackend(unittest.TestCase):
      def test_supported_extensions(self):
          backend = PythonAstBackend()
          self.assertIn("py", backend.get_supported_extensions())

      def test_parse_python_file(self):
          backend = PythonAstBackend()
          content = "def test_func(x, y):\n    return x + y\n"
          result = backend.parse_file(Path("hello.py"), content)
          self.assertIsNotNone(result)
          if result:
              self.assertEqual(result.language, "py")
              self.assertIn("def test_func(x, y)", result.outline)
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/infrastructure/code_intelligence/test_python_ast_backend.py -v`
  Expected: FAIL (ImportError).

- [ ] **Step 3: Write implementation**
  Create `infrastructure/adapters/code_intelligence/python_ast_backend.py` (Port AST parsing logic from the old `ast_parser.py`):
  ```python
  import ast
  import logging
  from pathlib import Path
  from typing import List, Optional
  from domain.ports.code_intelligence_port import ParsedCodeInfo
  from infrastructure.adapters.code_intelligence.base_backend import CodeIntelligenceBackend

  logger = logging.getLogger(__name__)

  class PythonAstBackend(CodeIntelligenceBackend):
      def get_supported_extensions(self) -> List[str]:
          return ["py", "pyw"]

      def parse_file(self, file_path: Path, content: str) -> Optional[ParsedCodeInfo]:
          try:
              tree = ast.parse(content, filename=str(file_path))
          except SyntaxError:
              logger.debug(f"Syntax error parsing Python file: {file_path}")
              return None

          items: List[str] = []
          for node in ast.iter_child_nodes(tree):
              if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                  prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                  args_str = self._format_python_args(node.args)
                  items.append(f"{prefix} {node.name}({args_str})")
              elif isinstance(node, ast.ClassDef):
                  bases = ", ".join(self._format_python_expr(b) for b in node.bases)
                  class_sig = f"class {node.name}({bases})" if bases else f"class {node.name}"
                  items.append(f"{class_sig}:")
                  for child in ast.iter_child_nodes(node):
                      if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                          prefix = "async def" if isinstance(child, ast.AsyncFunctionDef) else "def"
                          args_str = self._format_python_args(child.args)
                          items.append(f"  {prefix} {child.name}({args_str})")

          return ParsedCodeInfo(
              file_path=file_path,
              language="py",
              symbols=[],
              relationships=[],
              imports=[],
              outline=items
          )

      def _format_python_args(self, args: ast.arguments) -> str:
          parts: List[str] = []
          for arg in args.args:
              parts.append(arg.arg)
          if args.vararg:
              parts.append(f"*{args.vararg.arg}")
          if args.kwarg:
              parts.append(f"**{args.kwarg.arg}")
          return ", ".join(parts)

      def _format_python_expr(self, node: ast.expr) -> str:
          if isinstance(node, ast.Name):
              return node.id
          if isinstance(node, ast.Attribute):
              return f"{self._format_python_expr(node.value)}.{node.attr}"
          if isinstance(node, ast.Constant):
              return repr(node.value)
          return "..."
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/infrastructure/code_intelligence/test_python_ast_backend.py -v`
  Expected: PASS

- [ ] **Step 5: Stage files**
  Prepare staging commands:
  `git add infrastructure/adapters/code_intelligence/python_ast_backend.py tests/infrastructure/code_intelligence/test_python_ast_backend.py`

---

### Task 4: Implement Regex Fallback Backend
**Files:**
- Create: `infrastructure/adapters/code_intelligence/regex_fallback_backend.py`
- Test: `tests/infrastructure/code_intelligence/test_regex_fallback_backend.py`

**Interfaces:**
- Consumes: `CodeIntelligenceBackend`
- Produces: `RegexFallbackBackend` class

- [ ] **Step 1: Write the failing test**
  Create `tests/infrastructure/code_intelligence/test_regex_fallback_backend.py`:
  ```python
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
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/infrastructure/code_intelligence/test_regex_fallback_backend.py -v`
  Expected: FAIL (ImportError).

- [ ] **Step 3: Write implementation**
  Create `infrastructure/adapters/code_intelligence/regex_fallback_backend.py` (Port regex heuristic logic from old `ast_parser.py`):
  ```python
  import re
  from pathlib import Path
  from typing import List, Optional, Dict
  from domain.ports.code_intelligence_port import ParsedCodeInfo
  from infrastructure.adapters.code_intelligence.base_backend import CodeIntelligenceBackend

  class RegexFallbackBackend(CodeIntelligenceBackend):
      _JS_TS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
      _GO_EXTENSIONS = {".go"}
      _RUST_EXTENSIONS = {".rs"}
      _JAVA_EXTENSIONS = {".java"}
      _CSHARP_EXTENSIONS = {".cs"}
      _C_CPP_EXTENSIONS = {".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx"}
      _RUBY_EXTENSIONS = {".rb"}
      _PHP_EXTENSIONS = {".php"}
      _KOTLIN_EXTENSIONS = {".kt", ".kts"}
      _SWIFT_EXTENSIONS = {".swift"}
      _PYTHON_EXTENSIONS = {".py", ".pyw"}

      _REGEX_PATTERNS: Dict[str, List[re.Pattern[str]]] = {
          "js_ts": [
              re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)\s*\(", re.MULTILINE),
              re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(", re.MULTILINE),
              re.compile(r"^\s*(?:export\s+)?interface\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*(?:export\s+)?(?:const\s+)?enum\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*(?:export\s+)?type\s+(\w+)\s*=", re.MULTILINE),
          ],
          "go": [
              re.compile(r"^\s*type\s+(\w+)\s+struct\s*\{", re.MULTILINE),
              re.compile(r"^\s*type\s+(\w+)\s+interface\s*\{", re.MULTILINE),
              re.compile(r"^\s*func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(", re.MULTILINE),
          ],
          "rust": [
              re.compile(r"^\s*(?:pub\s+)?struct\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*(?:pub\s+)?enum\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*(?:pub\s+)?trait\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*impl(?:\s*<.*?>)?\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", re.MULTILINE),
          ],
          "java_csharp": [
              re.compile(r"^\s*(?:public|private|protected|internal)?\s*(?:static\s+)?(?:abstract\s+)?class\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*(?:public|private|protected)?\s*interface\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*(?:public|private|protected)?\s*enum\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*(?:public|private|protected|internal)?\s*(?:static\s+)?(?:async\s+)?(?:virtual\s+)?(?:override\s+)?\w+(?:<.*?>)?\s+(\w+)\s*\(", re.MULTILINE),
          ],
          "c_cpp": [
              re.compile(r"^\s*(?:class|struct)\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*(?:enum)\s+(?:class\s+)?(\w+)", re.MULTILINE),
              re.compile(r"^\s*(?:static\s+)?(?:inline\s+)?(?:virtual\s+)?(?:const\s+)?\w+[\w\s\*&:<>]*\s+(\w+)\s*\(", re.MULTILINE),
          ],
          "ruby": [
              re.compile(r"^\s*class\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*module\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*def\s+(\w+)", re.MULTILINE),
          ],
          "php": [
              re.compile(r"^\s*(?:abstract\s+)?class\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*interface\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*(?:public|private|protected)?\s*function\s+(\w+)", re.MULTILINE),
          ],
          "kotlin": [
              re.compile(r"^\s*(?:data\s+)?class\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*interface\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*(?:fun|suspend\s+fun)\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*object\s+(\w+)", re.MULTILINE),
          ],
          "swift": [
              re.compile(r"^\s*(?:public\s+|private\s+|open\s+)?class\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*(?:public\s+)?struct\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*(?:public\s+)?protocol\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*(?:public\s+|private\s+)?func\s+(\w+)", re.MULTILINE),
              re.compile(r"^\s*(?:public\s+)?enum\s+(\w+)", re.MULTILINE),
          ],
      }

      def __init__(self) -> None:
          self._ext_to_group: Dict[str, str] = {}
          for ext in self._JS_TS_EXTENSIONS: self._ext_to_group[ext] = "js_ts"
          for ext in self._GO_EXTENSIONS: self._ext_to_group[ext] = "go"
          for ext in self._RUST_EXTENSIONS: self._ext_to_group[ext] = "rust"
          for ext in self._JAVA_EXTENSIONS: self._ext_to_group[ext] = "java_csharp"
          for ext in self._CSHARP_EXTENSIONS: self._ext_to_group[ext] = "java_csharp"
          for ext in self._C_CPP_EXTENSIONS: self._ext_to_group[ext] = "c_cpp"
          for ext in self._RUBY_EXTENSIONS: self._ext_to_group[ext] = "ruby"
          for ext in self._PHP_EXTENSIONS: self._ext_to_group[ext] = "php"
          for ext in self._KOTLIN_EXTENSIONS: self._ext_to_group[ext] = "kotlin"
          for ext in self._SWIFT_EXTENSIONS: self._ext_to_group[ext] = "swift"
          for ext in self._PYTHON_EXTENSIONS: self._ext_to_group[ext] = "ruby"

      def get_supported_extensions(self) -> List[str]:
          return [ext.lstrip(".") for ext in (
              self._JS_TS_EXTENSIONS | self._GO_EXTENSIONS | self._RUST_EXTENSIONS |
              self._JAVA_EXTENSIONS | self._CSHARP_EXTENSIONS | self._C_CPP_EXTENSIONS |
              self._RUBY_EXTENSIONS | self._PHP_EXTENSIONS | self._KOTLIN_EXTENSIONS |
              self._SWIFT_EXTENSIONS | self._PYTHON_EXTENSIONS
          )]

      def parse_file(self, file_path: Path, content: str) -> Optional[ParsedCodeInfo]:
          suffix = file_path.suffix.lower()
          group = self._ext_to_group.get(suffix)
          if not group:
              return None

          patterns = self._REGEX_PATTERNS.get(group, [])
          seen: set[str] = set()
          outline: List[str] = []

          for pattern in patterns:
              for match in pattern.finditer(content):
                  name = match.group(1)
                  if name and name not in seen:
                      seen.add(name)
                      line = match.group(0).strip().rstrip("{").strip()
                      outline.append(line)

          return ParsedCodeInfo(
              file_path=file_path,
              language=suffix.lstrip("."),
              symbols=[],
              relationships=[],
              imports=[],
              outline=outline
          )
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/infrastructure/code_intelligence/test_regex_fallback_backend.py -v`
  Expected: PASS

- [ ] **Step 5: Stage files**
  Prepare staging commands:
  `git add infrastructure/adapters/code_intelligence/regex_fallback_backend.py tests/infrastructure/code_intelligence/test_regex_fallback_backend.py`

---

### Task 5: Implement Tree-Sitter Backend
**Files:**
- Create: `infrastructure/adapters/code_intelligence/tree_sitter_backend.py`
- Test: `tests/infrastructure/code_intelligence/test_tree_sitter_backend.py`

**Interfaces:**
- Consumes: `CodeIntelligenceBackend`
- Produces: `TreeSitterBackend` class

- [ ] **Step 1: Write the failing test**
  Create `tests/infrastructure/code_intelligence/test_tree_sitter_backend.py`:
  ```python
  import unittest
  from pathlib import Path
  from infrastructure.adapters.code_intelligence.tree_sitter_backend import TreeSitterBackend

  class TestTreeSitterBackend(unittest.TestCase):
      def test_supported_extensions(self):
          backend = TreeSitterBackend()
          self.assertIn("py", backend.get_supported_extensions())

      def test_parse_tree_sitter_python(self):
          backend = TreeSitterBackend()
          content = "def sample():\n    pass\n"
          result = backend.parse_file(Path("sample.py"), content)
          self.assertIsNotNone(result)
          if result:
              self.assertEqual(result.language, "py")
              self.assertTrue(len(result.symbols) > 0)
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/infrastructure/code_intelligence/test_tree_sitter_backend.py -v`
  Expected: FAIL (ImportError).

- [ ] **Step 3: Write implementation**
  Create `infrastructure/adapters/code_intelligence/tree_sitter_backend.py` (migrating Tree-sitter extraction logic):
  ```python
  import logging
  from pathlib import Path
  from typing import List, Optional
  from tree_sitter import Parser
  from domain.ports.code_intelligence_port import ParsedCodeInfo
  from domain.smart_context.loader import get_language
  from domain.codemap.symbol_extractor import extract_symbols
  from domain.codemap.relationship_extractor import extract_relationships
  from domain.smart_context.parser import _extract_import_texts
  from infrastructure.adapters.code_intelligence.base_backend import CodeIntelligenceBackend

  logger = logging.getLogger(__name__)

  class TreeSitterBackend(CodeIntelligenceBackend):
      def get_supported_extensions(self) -> List[str]:
          return ["py", "ts", "tsx", "js", "go", "rs", "rb", "cpp", "c", "cs", "java"]

      def parse_file(self, file_path: Path, content: str) -> Optional[ParsedCodeInfo]:
          ext = file_path.suffix.lstrip(".").lower()
          language = get_language(ext)
          if not language:
              return None

          try:
              parser = Parser(language)
              tree = parser.parse(bytes(content, "utf-8"))
              if not tree or not tree.root_node:
                  return None

              # Extract symbols, relations and imports using existing algorithms
              symbols = extract_symbols(str(file_path), content, tree=tree, language=language)
              relationships = extract_relationships(str(file_path), content, tree=tree, language=language)
              imports = _extract_import_texts(tree, content)

              # Generate outline list from symbols
              outline: List[str] = []
              for s in symbols:
                  if s.name == "[ENTRY POINT]":
                      continue
                  indent = "  " if s.parent else ""
                  sig = s.signature if s.signature else s.name
                  for line_text in sig.split("\n"):
                      outline.append(indent + line_text)

              return ParsedCodeInfo(
                  file_path=file_path,
                  language=ext,
                  symbols=symbols,
                  relationships=relationships,
                  imports=imports,
                  outline=outline
              )
          except Exception as e:
              logger.debug(f"Tree-sitter parse failed for {file_path}: {e}")
              return None
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/infrastructure/code_intelligence/test_tree_sitter_backend.py -v`
  Expected: PASS

- [ ] **Step 5: Stage files**
  Prepare staging commands:
  `git add infrastructure/adapters/code_intelligence/tree_sitter_backend.py tests/infrastructure/code_intelligence/test_tree_sitter_backend.py`

---

### Task 6: Implement Router Adapter
**Files:**
- Create: `infrastructure/adapters/code_intelligence/router_adapter.py`
- Test: `tests/infrastructure/code_intelligence/test_router_adapter.py`

**Interfaces:**
- Consumes: `ICodeIntelligencePort`, `CodeIntelligenceBackend`
- Produces: `CodeIntelligenceRouterAdapter` class

- [ ] **Step 1: Write the failing test**
  Create `tests/infrastructure/code_intelligence/test_router_adapter.py`:
  ```python
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
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/infrastructure/code_intelligence/test_router_adapter.py -v`
  Expected: FAIL (ImportError).

- [ ] **Step 3: Write implementation**
  Create `infrastructure/adapters/code_intelligence/router_adapter.py`:
  Write the router class exactly as defined in **Section 3** of the Design Specification.

- [ ] **Step 4: Run test to verify it passes**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/infrastructure/code_intelligence/test_router_adapter.py -v`
  Expected: PASS

- [ ] **Step 5: Stage files**
  Prepare staging commands:
  `git add infrastructure/adapters/code_intelligence/router_adapter.py tests/infrastructure/code_intelligence/test_router_adapter.py`

---

### Task 7: Update Registry and Container Setup
**Files:**
- Modify: `domain/ports/registry.py`
- Modify: `presentation/service_container.py`
- Delete: `domain/ports/ast_parser_port.py`
- Delete: `infrastructure/adapters/ast_parser.py`
- Test: `tests/domain/test_registry.py`

**Interfaces:**
- Consumes: `ICodeIntelligencePort`
- Produces: Updated `DomainRegistry`

- [ ] **Step 1: Write the failing test**
  Modify `tests/domain/test_registry.py` to change references to `IAstParser` to `ICodeIntelligencePort`:
  Replace all `register_ast_parser` and `ast_parser` references with `register_code_intelligence` and `code_intelligence`.
  Run the test: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/domain/test_registry.py -v`
  Expected: FAIL (AttributeError).

- [ ] **Step 2: Update DomainRegistry**
  Modify `domain/ports/registry.py` to add `code_intelligence` ports and clean up `ast_parser`:
  ```python
  # In domain/ports/registry.py
  # Remove ast_parser_port import, replace with code_intelligence_port:
  from domain.ports.code_intelligence_port import ICodeIntelligencePort

  # Inside DomainRegistry class:
  _code_intelligence: Optional[ICodeIntelligencePort] = None

  @classmethod
  def register_code_intelligence(cls, ci: ICodeIntelligencePort) -> None:
      cls._code_intelligence = ci

  @classmethod
  def code_intelligence(cls) -> ICodeIntelligencePort:
      if cls._code_intelligence is None:
          raise RuntimeError("ICodeIntelligencePort is not registered in DomainRegistry")
      return cls._code_intelligence
  ```

- [ ] **Step 3: Update Service Container**
  Modify `presentation/service_container.py` to instantiate and register the adapter:
  Remove `from infrastructure.adapters.ast_parser import AstParser` and `DomainRegistry.register_ast_parser(...)`.
  Add setup code:
  ```python
  from infrastructure.adapters.code_intelligence.tree_sitter_backend import TreeSitterBackend
  from infrastructure.adapters.code_intelligence.python_ast_backend import PythonAstBackend
  from infrastructure.adapters.code_intelligence.regex_fallback_backend import RegexFallbackBackend
  from infrastructure.adapters.code_intelligence.router_adapter import CodeIntelligenceRouterAdapter

  backends = [
      TreeSitterBackend(),
      PythonAstBackend(),
      RegexFallbackBackend()
  ]
  DomainRegistry.register_code_intelligence(CodeIntelligenceRouterAdapter(backends))
  ```

- [ ] **Step 4: Clean up old files and run tests**
  Remove the files from workspace:
  - `domain/ports/ast_parser_port.py`
  - `infrastructure/adapters/ast_parser.py`

  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/domain/test_registry.py -v`
  Expected: PASS

- [ ] **Step 5: Stage files**
  Prepare staging commands:
  `git rm domain/ports/ast_parser_port.py`
  `git rm infrastructure/adapters/ast_parser.py`
  `git add domain/ports/registry.py presentation/service_container.py tests/domain/test_registry.py`

---

### Task 8: Update Consumers and Integrations
**Files:**
- Modify: `domain/smart_context/parser.py`
- Modify: `domain/codemap/canonical_structure.py`
- Test: `tests/domain/smart_context/test_parser_hybrid.py`

- [ ] **Step 1: Write the failing test**
  Run existing hybrid tests: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/domain/smart_context/test_parser_hybrid.py -v`
  Expected: PASS (but we want to rewrite it to use the new port underneath).

- [ ] **Step 2: Update smart_parse**
  In `domain/smart_context/parser.py`, modify `smart_parse` to extract information via the registry port:
  ```python
  def smart_parse(
      file_path: str,
      content: str,
      include_relationships: bool = False,
      workspace_root: Optional[str] = None,
      all_files_content: Optional[dict[str, str]] = None,
      resolver: Optional[Any] = None,
  ) -> Optional[str]:
      from domain.ports.registry import DomainRegistry
      from domain.smart_context.config import is_supported
      from domain.codemap.dependency_graph_generator import DependencyGraphGenerator

      _, ext = os.path.splitext(file_path)
      ext = ext.lstrip(".")

      if not is_supported(ext):
          return None

      try:
          # Extract via the centralized port DTO
          info = DomainRegistry.code_intelligence().parse_file(Path(file_path), content)

          # Format compressed content
          compressed_content = ""
          last_line = -1

          if info.imports:
              compressed_content += "\n".join(info.imports)
              last_line = -1

          if info.symbols:
              for s in info.symbols:
                  if s.name == "[ENTRY POINT]":
                      if compressed_content:
                          compressed_content += f"\n{CHUNK_SEPARATOR}\n"
                      compressed_content += f"// {s.signature}"
                      last_line = s.line_end
                      continue

                  if last_line != -1 and s.line_start > last_line + 1:
                      if not compressed_content.endswith(f"{CHUNK_SEPARATOR}\n"):
                          compressed_content += f"\n{CHUNK_SEPARATOR}\n"
                  elif compressed_content and not compressed_content.endswith("\n"):
                      compressed_content += "\n"

                  indent = "  " if s.parent else ""
                  sig = s.signature if s.signature else s.name
                  indented_sig = "\n".join([indent + line_text for line_text in sig.split("\n")])
                  compressed_content += indented_sig
                  last_line = s.line_end

          if include_relationships and info.relationships:
              # Simple format relationship section
              calls = [r for r in info.relationships if r.kind.value == "calls"]
              inherits = [r for r in info.relationships if r.kind.value == "inherits"]
              imports_rel = [r for r in info.relationships if r.kind.value == "imports"]

              rel_lines = ["\n## Relationships"]
              if calls:
                  rel_lines.append("\n### Function Calls")
                  for rel in calls[:20]:
                      rel_lines.append(f"- `{rel.source}` calls `{rel.target}` (line {rel.source_line})")
              if inherits:
                  rel_lines.append("\n### Class Inheritance")
                  for rel in inherits:
                      rel_lines.append(f"- `{rel.source}` inherits from `{rel.target}` (line {rel.source_line})")
              if imports_rel:
                  rel_lines.append("\n### Imports")
                  for rel in imports_rel[:15]:
                      rel_lines.append(f"- Imports `{rel.target}` (line {rel.source_line})")
              compressed_content += "\n".join(rel_lines)

          # Part 1: Dependency Graph (Only if requested)
          if workspace_root and all_files_content:
              graph_gen = DependencyGraphGenerator(Path(workspace_root), resolver=resolver)
              graph_output = graph_gen.generate_graph(all_files_content)
              if graph_output:
                  return f"{graph_output}\n\n{SECTION_SEPARATOR}\n\n{compressed_content}"

          return compressed_content
      except Exception as e:
          logger.error("smart_parse failed for %s: %s", file_path, e, exc_info=True)
          return None
  ```

- [ ] **Step 3: Update canonical_structure**
  In `domain/codemap/canonical_structure.py`, update parameter and function references:
  Change references of `IAstParser` to `ICodeIntelligencePort`.
  Change `outline_res = ast_parser.parse_file(file_path)` to:
  `outline_res = code_intel.parse_file(file_path, file_path.read_text(encoding="utf-8", errors="replace"))`
  And extract outline list via `outline_res.outline`.

- [ ] **Step 4: Run test to verify it passes**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/domain/smart_context/test_parser_hybrid.py -v`
  Expected: PASS

- [ ] **Step 5: Stage files**
  Prepare staging commands:
  `git add domain/smart_context/parser.py domain/codemap/canonical_structure.py`

---

### Task 9: Clean Up Test suite mocks & Verify Everything
**Files:**
- Modify: `tests/conftest.py`
- Test: All test suite

- [ ] **Step 1: Update Test Mocks**
  In `tests/conftest.py`, replace `DummyAstParser` mock class with `DummyCodeIntelligence` implementing `ICodeIntelligencePort`.
  Register `DummyCodeIntelligence()` in the domain registry mock hooks.

- [ ] **Step 2: Run all tests to verify**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v`
  Expected: All tests pass.
