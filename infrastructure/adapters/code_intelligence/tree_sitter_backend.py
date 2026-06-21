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
