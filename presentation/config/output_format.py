"""
Output Format Configuration - Backward compatibility shim.

File này đã được chuyển sang domain/prompt/output_format.py.
OutputStyle là domain concept, không phải UI concern.
Import từ domain/prompt/output_format để tuân theo Clean Architecture.
"""

from domain.prompt.output_format import (
    OutputStyle,
    OutputFormatConfig,
    OUTPUT_FORMATS,
    DEFAULT_OUTPUT_STYLE,
    get_format_config,
    get_format_tooltip,
    get_all_format_options,
    get_style_by_id,
)

__all__ = [
    "OutputStyle",
    "OutputFormatConfig",
    "OUTPUT_FORMATS",
    "DEFAULT_OUTPUT_STYLE",
    "get_format_config",
    "get_format_tooltip",
    "get_all_format_options",
    "get_style_by_id",
]
