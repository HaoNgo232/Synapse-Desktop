"""
Language Configuration Registry

Định nghĩa LanguageConfig dataclass và LANGUAGE_CONFIGS registry.
Cung cấp lookup functions để tìm config theo extension hoặc language name.
"""

from dataclasses import dataclass
from typing import Callable, Optional, Dict
from tree_sitter import Language  # type: ignore

# Import tree-sitter language modules
import tree_sitter_python as tspython  # type: ignore
import tree_sitter_javascript as tsjavascript  # type: ignore
import tree_sitter_typescript as tstypescript  # type: ignore
import tree_sitter_rust as tsrust  # type: ignore
import tree_sitter_go as tsgo  # type: ignore
import tree_sitter_java as tsjava  # type: ignore
import tree_sitter_c_sharp as tscsharp  # type: ignore
import tree_sitter_c as tsc  # type: ignore
import tree_sitter_cpp as tscpp  # type: ignore

# Phase 4
import tree_sitter_ruby as tsruby  # type: ignore
import tree_sitter_php as tsphp  # type: ignore
import tree_sitter_swift as tsswift  # type: ignore

# Phase 5
import tree_sitter_css as tscss  # type: ignore
import tree_sitter_solidity as tssolidity  # type: ignore

# Import queries
from core.smart_context.queries import (
    QUERY_PYTHON,
    QUERY_JAVASCRIPT,
    QUERY_TYPESCRIPT,
    QUERY_RUST,
    QUERY_GO,
    QUERY_JAVA,
    QUERY_CSHARP,
    QUERY_C,
    QUERY_CPP,
    # Phase 4
    QUERY_RUBY,
    QUERY_PHP,
    QUERY_SWIFT,
    # Phase 5
    QUERY_CSS,
    QUERY_SOLIDITY,
)


@dataclass
class LanguageConfig:
    """
    Cấu hình cho một ngôn ngữ lập trình.

    Attributes:
        name: Tên ngôn ngữ (unique identifier)
        extensions: Danh sách file extensions (không có dấu chấm)
        query: Tree-sitter query string để extract structure
        loader: Function để load Tree-sitter Language object
    """

    name: str
    extensions: list[str]
    query: str
    loader: Callable[[], Language]


# Registry tất cả language configurations
LANGUAGE_CONFIGS: list[LanguageConfig] = [
    LanguageConfig(
        name="python",
        extensions=["py", "pyw"],
        query=QUERY_PYTHON,
        loader=lambda: Language(tspython.language()),
    ),
    LanguageConfig(
        name="javascript",
        extensions=["js", "jsx", "mjs", "cjs", "mjsx"],
        query=QUERY_JAVASCRIPT,
        loader=lambda: Language(tsjavascript.language()),
    ),
    LanguageConfig(
        name="typescript",
        extensions=["ts", "tsx", "mts", "mtsx", "cts"],
        query=QUERY_TYPESCRIPT,
        loader=lambda: Language(tstypescript.language_typescript()),
    ),
    LanguageConfig(
        name="rust",
        extensions=["rs"],
        query=QUERY_RUST,
        loader=lambda: Language(tsrust.language()),
    ),
    LanguageConfig(
        name="go",
        extensions=["go"],
        query=QUERY_GO,
        loader=lambda: Language(tsgo.language()),
    ),
    LanguageConfig(
        name="java",
        extensions=["java"],
        query=QUERY_JAVA,
        loader=lambda: Language(tsjava.language()),
    ),
    LanguageConfig(
        name="c_sharp",
        extensions=["cs"],
        query=QUERY_CSHARP,
        loader=lambda: Language(tscsharp.language()),
    ),
    LanguageConfig(
        name="c",
        extensions=["c", "h"],
        query=QUERY_C,
        loader=lambda: Language(tsc.language()),
    ),
    LanguageConfig(
        name="cpp",
        extensions=["cpp", "hpp", "cc", "hh", "cxx", "hxx"],
        query=QUERY_CPP,
        loader=lambda: Language(tscpp.language()),
    ),
    # Phase 4: Web & Scripting
    LanguageConfig(
        name="ruby",
        extensions=["rb", "rake", "gemspec"],
        query=QUERY_RUBY,
        loader=lambda: Language(tsruby.language()),
    ),
    LanguageConfig(
        name="php",
        extensions=["php", "phtml", "php3", "php4", "php5"],
        query=QUERY_PHP,
        loader=lambda: Language(tsphp.language_php()),
    ),
    LanguageConfig(
        name="swift",
        extensions=["swift"],
        query=QUERY_SWIFT,
        loader=lambda: Language(tsswift.language()),
    ),
    # Phase 5: Special
    LanguageConfig(
        name="css",
        extensions=["css", "scss", "less"],
        query=QUERY_CSS,
        loader=lambda: Language(tscss.language()),
    ),
    LanguageConfig(
        name="solidity",
        extensions=["sol"],
        query=QUERY_SOLIDITY,
        loader=lambda: Language(tssolidity.language()),
    ),
]


# Lookup maps (lazy initialized)
_extension_to_config: Optional[Dict[str, LanguageConfig]] = None
_name_to_config: Optional[Dict[str, LanguageConfig]] = None


def _build_lookup_maps() -> tuple[Dict[str, LanguageConfig], Dict[str, LanguageConfig]]:
    """Build lookup maps from LANGUAGE_CONFIGS với validation."""
    ext_map: Dict[str, LanguageConfig] = {}
    name_map: Dict[str, LanguageConfig] = {}

    for config in LANGUAGE_CONFIGS:
        # Map each extension to config
        for ext in config.extensions:
            if ext in ext_map:
                raise ValueError(
                    f"Duplicate extension '{ext}' claimed by both "
                    f"'{ext_map[ext].name}' and '{config.name}'"
                )
            ext_map[ext] = config

        # Map name to config
        name_map[config.name] = config

    return ext_map, name_map


def _get_lookup_maps() -> tuple[Dict[str, LanguageConfig], Dict[str, LanguageConfig]]:
    """Get or initialize lookup maps (lazy initialization)."""
    global _extension_to_config, _name_to_config

    if _extension_to_config is None or _name_to_config is None:
        _extension_to_config, _name_to_config = _build_lookup_maps()

    return _extension_to_config, _name_to_config


def get_config_by_extension(extension: str) -> Optional[LanguageConfig]:
    """
    Lấy language config theo file extension.

    Args:
        extension: File extension không có dấu chấm (e.g., 'py', 'ts')

    Returns:
        LanguageConfig hoặc None nếu không hỗ trợ
    """
    ext_map, _ = _get_lookup_maps()
    return ext_map.get(extension.lower())


def get_config_by_name(name: str) -> Optional[LanguageConfig]:
    """
    Lấy language config theo tên ngôn ngữ.

    Args:
        name: Tên ngôn ngữ (e.g., 'python', 'typescript')

    Returns:
        LanguageConfig hoặc None nếu không tìm thấy
    """
    _, name_map = _get_lookup_maps()
    return name_map.get(name)


def get_supported_extensions() -> list[str]:
    """Lấy danh sách tất cả extensions được hỗ trợ."""
    ext_map, _ = _get_lookup_maps()
    return list(ext_map.keys())


def is_supported(extension: str) -> bool:
    """Kiểm tra extension có được hỗ trợ không."""
    return get_config_by_extension(extension) is not None
