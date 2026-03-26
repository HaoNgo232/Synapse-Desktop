"""
Output Format Configuration - Registry cho các định dạng đầu ra

Thiết kế extensible: Thêm format mới chỉ cần thêm entry vào OUTPUT_FORMATS dict.
Mỗi format có tooltip mô tả lợi ích để user dễ lựa chọn.

Tham khảo kiến trúc: Repomix (src/config/configSchema.ts)
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict


class OutputStyle(Enum):
    """
    Enum các định dạng đầu ra được hỗ trợ.

    Extensible: Thêm format mới bằng cách thêm value vào đây
    và entry tương ứng vào OUTPUT_FORMATS dict.
    """

    MARKDOWN = "markdown"
    XML = "xml"
    JSON = "json"
    PLAIN = "plain"


@dataclass(frozen=True)
class OutputFormatConfig:
    """
    Cấu hình cho một output format.

    Attributes:
        id: ID duy nhất (trùng với enum value)
        name: Tên hiển thị trên UI
        description: Mô tả ngắn 1 dòng
        benefits: Danh sách lợi ích (hiển thị trong tooltip)
        file_extension: Extension file khi export
    """

    id: str
    name: str
    description: str
    benefits: List[str]
    file_extension: str


# ============================================================================
# OUTPUT FORMAT REGISTRY
# Thêm format mới: Thêm entry vào dict này + thêm enum value ở trên
# ============================================================================

OUTPUT_FORMATS: Dict[OutputStyle, OutputFormatConfig] = {
    OutputStyle.MARKDOWN: OutputFormatConfig(
        id="markdown",
        name="Markdown",
        description="Code blocks với syntax highlighting",
        benefits=[
            "Dễ đọc cho người dùng",
            "Tương thích mọi LLM",
            "Hiển thị đẹp trong chat",
        ],
        file_extension=".md",
    ),
    OutputStyle.XML: OutputFormatConfig(
        id="xml",
        name="XML",
        description="Structured XML theo chuẩn Repomix",
        benefits=[
            "LLM hiểu cấu trúc code tốt hơn",
            "Giảm hallucination về file paths",
            "Tối ưu cho Claude & GPT",
        ],
        file_extension=".xml",
    ),
    OutputStyle.JSON: OutputFormatConfig(
        id="json",
        name="JSON",
        description="Dữ liệu dạng JSON thuần túy",
        benefits=[
            "Dễ dàng xử lý bằng code (Automation)",
            "Tối ưu cho các model có JSON Mode",
            "Cấu trúc chặt chẽ nhất",
        ],
        file_extension=".json",
    ),
    OutputStyle.PLAIN: OutputFormatConfig(
        id="plain",
        name="Plain Text",
        description="Văn bản thô, tối thiểu định dạng",
        benefits=[
            "Tiết kiệm token nhất",
            "Không có tag hay markdown thừa",
            "Dành cho model context nhỏ",
        ],
        file_extension=".txt",
    ),
}

# Default style
DEFAULT_OUTPUT_STYLE = OutputStyle.XML


def get_format_config(style: OutputStyle) -> OutputFormatConfig:
    """
    Lấy config của một output format.

    Args:
        style: OutputStyle enum value

    Returns:
        OutputFormatConfig cho style đó

    Raises:
        KeyError: Nếu style không tồn tại trong registry
    """
    return OUTPUT_FORMATS[style]


def get_format_tooltip(style: OutputStyle) -> str:
    """
    Tạo tooltip string từ config để hiển thị khi hover.

    Args:
        style: OutputStyle enum value

    Returns:
        Tooltip string với description và danh sách benefits
    """
    config = OUTPUT_FORMATS[style]
    benefits_text = "\n".join(f"• {b}" for b in config.benefits)
    return f"{config.description}\n\n{benefits_text}"


def get_all_format_options() -> List[tuple]:
    """
    Lấy danh sách options cho dropdown UI.

    Returns:
        List of (id, name) tuples cho dropdown options
    """
    return [(cfg.id, cfg.name) for cfg in OUTPUT_FORMATS.values()]


def get_style_by_id(style_id: str) -> OutputStyle:
    """
    Tìm OutputStyle từ string id.

    Args:
        style_id: ID string (VD: "markdown", "xml")

    Returns:
        OutputStyle enum value

    Raises:
        ValueError: Nếu style_id không hợp lệ
    """
    for style, config in OUTPUT_FORMATS.items():
        if config.id == style_id:
            return style
    raise ValueError(f"Unknown output style: {style_id}")
