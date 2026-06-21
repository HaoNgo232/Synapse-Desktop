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
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                args_str = self._format_python_args(node.args)
                items.append(f"{prefix} {node.name}({args_str})")
            elif isinstance(node, ast.ClassDef):
                bases = ", ".join(self._format_python_expr(b) for b in node.bases)
                class_sig = f"class {node.name}({bases})" if bases else f"class {node.name}"
                items.append(f"{class_sig}:")
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
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
