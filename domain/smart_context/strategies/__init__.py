# Strategies package cho Smart Context
# Moi ngon ngu co 1 ParseStrategy rieng

from domain.smart_context.strategies.base import BaseParseStrategy
from domain.smart_context.strategies.python import PythonParseStrategy
from domain.smart_context.strategies.typescript import TypeScriptParseStrategy
from domain.smart_context.strategies.go import GoParseStrategy
from domain.smart_context.strategies.css import CssParseStrategy
from domain.smart_context.strategies.vue import VueParseStrategy
from domain.smart_context.strategies.default import DefaultParseStrategy

__all__ = [
    "BaseParseStrategy",
    "PythonParseStrategy",
    "TypeScriptParseStrategy",
    "GoParseStrategy",
    "CssParseStrategy",
    "VueParseStrategy",
    "DefaultParseStrategy",
    "get_strategy",
]


# Strategy registry - map language name to strategy class
_STRATEGY_MAP = {
    "python": PythonParseStrategy,
    "typescript": TypeScriptParseStrategy,
    "javascript": TypeScriptParseStrategy,
    "go": GoParseStrategy,
    "css": CssParseStrategy,
    # Vue not typically parsed by tree-sitter in synapse, but available
}


def get_strategy(language_name: str) -> BaseParseStrategy:
    """
    Lay strategy instance cho ngon ngu.

    Args:
        language_name: Ten ngon ngu (e.g., 'python', 'typescript')

    Returns:
        Strategy instance cho ngon ngu, hoac DefaultParseStrategy
    """
    strategy_class = _STRATEGY_MAP.get(language_name, DefaultParseStrategy)
    return strategy_class()
