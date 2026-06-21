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
        all_exts = (
            self._JS_TS_EXTENSIONS | self._GO_EXTENSIONS | self._RUST_EXTENSIONS |
            self._JAVA_EXTENSIONS | self._CSHARP_EXTENSIONS | self._C_CPP_EXTENSIONS |
            self._RUBY_EXTENSIONS | self._PHP_EXTENSIONS | self._KOTLIN_EXTENSIONS |
            self._SWIFT_EXTENSIONS | self._PYTHON_EXTENSIONS
        )
        return [ext.lstrip(".") for ext in all_exts]

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
