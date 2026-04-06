from enum import Enum


class OutputStyle(Enum):
    """
    Enum các định dạng đầu ra được hỗ trợ (Domain level).
    """

    MARKDOWN = "markdown"
    XML = "xml"
    JSON = "json"
    PLAIN = "plain"
