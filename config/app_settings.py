"""
AppSettings - Typed settings dataclass cho Synapse Desktop.

Thay the Dict[str, Any] bang dataclass co type hints, validation va default values.
Tat ca settings duoc truy cap qua typed fields thay vi string keys.

Modules:
- AppSettings: Dataclass chua toan bo application settings
- from_dict(): Tao AppSettings tu dict (backward compat voi settings.json)
- to_dict(): Chuyen doi AppSettings thanh dict de luu xuong file

Su dung:
    settings = load_app_settings()
    if settings.enable_security_check:
        ...
"""

from dataclasses import dataclass, field
from typing import Any


# === Default values cho settings ===
_DEFAULT_EXCLUDED_FOLDERS = (
    "node_modules\ndist\nbuild\n.next\n__pycache__\n"
    ".pytest_cache\npnpm-lock.yaml\npackage-lock.json\ncoverage"
)


@dataclass
class AppSettings:
    """
    Typed settings cho Synapse Desktop.

    Moi field tuong ung voi mot key trong settings.json.
    Default values duoc su dung khi settings.json chua co key tuong ung.
    """

    # --- File Tree Settings ---
    # Pattern cac file/folder bi loai khoi tree (separated by newline)
    excluded_folders: str = field(default=_DEFAULT_EXCLUDED_FOLDERS)
    # Co respect .gitignore hay khong
    use_gitignore: bool = True

    # --- AI Context Settings ---
    # Model ID dang su dung (vd: "claude-sonnet-4.5")
    model_id: str = "claude-sonnet-4.5"
    # Output format ID (vd: "xml", "markdown", "json", "plain")
    output_format: str = "xml"
    # Co include git diff/log trong AI context hay khong
    include_git_changes: bool = True
    # Co dung relative paths trong prompts hay khong (bao mat PII)
    use_relative_paths: bool = True

    # --- Security Settings ---
    # Co enable security scan truoc khi copy hay khong
    enable_security_check: bool = True

    # --- History Settings ---
    # Luu tru lich su cac instruction da su dung (toi da 20)
    instruction_history: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        """
        Tao AppSettings tu dict, chi lay cac keys trung voi field names.

        Bao gom type validation: neu value co type khong khop voi
        field declaration, se bo qua va dung default thay the.

        Args:
            data: Dict settings (thuong tu settings.json)

        Returns:
            AppSettings instance voi values tu dict, fallback ve defaults
        """
        # Map field name -> expected type tu dataclass definition
        field_types: dict[str, type] = {
            f.name: f.type for f in cls.__dataclass_fields__.values()
        }

        filtered: dict[str, Any] = {}
        for key, value in data.items():
            if key not in field_types:
                continue

            expected_type = field_types[key]

            # Xu ly truong hop type annotation la string (forward ref)
            if isinstance(expected_type, str):
                type_map = {"str": str, "bool": bool, "int": int, "float": float}
                expected_type = type_map.get(expected_type, str)

            # Strict type check: reject bool when expecting int
            # (isinstance(True, int) == True in Python, but we want strict validation)
            if expected_type is int and isinstance(value, bool):
                continue  # Use default instead

            import typing

            origin = typing.get_origin(expected_type)
            check_type = origin if origin is not None else expected_type

            # Validate type cua value
            if isinstance(value, check_type):
                filtered[key] = value
            # Khong raise loi, chi bo qua value sai type -> dung default

        return cls(**filtered)

    def to_dict(self) -> dict[str, Any]:
        """
        Chuyen doi AppSettings thanh dict de luu xuong file.

        Returns:
            Dict voi toan bo settings
        """
        return {
            "excluded_folders": self.excluded_folders,
            "use_gitignore": self.use_gitignore,
            "model_id": self.model_id,
            "output_format": self.output_format,
            "include_git_changes": self.include_git_changes,
            "use_relative_paths": self.use_relative_paths,
            "enable_security_check": self.enable_security_check,
            "instruction_history": self.instruction_history,
        }

    def get_excluded_patterns_list(self) -> list[str]:
        """
        Parse excluded_folders string thanh list cac patterns.

        Loai bo dong trong va comments (bat dau bang #).

        Returns:
            List patterns da normalize
        """
        return [
            line.strip()
            for line in self.excluded_folders.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
