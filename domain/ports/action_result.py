from dataclasses import dataclass
from typing import Optional


@dataclass
class ActionResult:
    """Result of a file action execution."""

    path: str
    action: str
    success: bool
    message: str
    new_path: Optional[str] = None
