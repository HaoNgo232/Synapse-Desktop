from dataclasses import dataclass
from enum import Enum
import warnings
from typing import Dict, Any
from presentation.config.output_format import OutputStyle

class CopyMode(Enum):
    FULL = "full"
    SMART = "smart"
    APPLY = "apply"

    @property
    def display_name(self) -> str:
        if self == CopyMode.FULL:
            return "Full Context"
        elif self == CopyMode.SMART:
            return "Smart Context"
        elif self == CopyMode.APPLY:
            return "Apply (Search/Replace)"
        raise ValueError(f"Unknown mode: {self}")

    @property
    def description(self) -> str:
        if self == CopyMode.FULL:
            return "Sao chép toàn bộ nội dung file đã chọn"
        elif self == CopyMode.SMART:
            return "Chỉ sao chép cấu trúc code (AST signatures & docstrings)"
        elif self == CopyMode.APPLY:
            return "Sao chép kèm theo chỉ dẫn Search/Replace (Aider-style)"
        raise ValueError(f"Unknown mode: {self}")

@dataclass
class CopyConfig:
    mode: CopyMode
    include_git_diff: bool = False
    tree_map_only: bool = False
    output_style: OutputStyle = OutputStyle.XML

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "include_git_diff": self.include_git_diff,
            "tree_map_only": self.tree_map_only,
            "output_style": self.output_style.value
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CopyConfig":
        raw_mode = data.get("mode", "full")
        style_val = data.get("output_style", "xml")
        try:
            output_style = OutputStyle(style_val)
        except ValueError:
            output_style = OutputStyle.XML

        if raw_mode == "compress":
            warnings.warn(
                "Legacy mode 'compress' is deprecated. Use 'smart' instead.",
                DeprecationWarning,
                stacklevel=2
            )
            mode = CopyMode.SMART
        elif raw_mode == "copy_context":
            mode = CopyMode.FULL
        elif raw_mode == "search_replace":
            mode = CopyMode.APPLY
        else:
            try:
                mode = CopyMode(raw_mode)
            except ValueError:
                raise ValueError(f"Invalid mode string: {raw_mode}")

        return cls(
            mode=mode,
            include_git_diff=data.get("include_git_diff", False),
            tree_map_only=data.get("tree_map_only", False),
            output_style=output_style
        )
