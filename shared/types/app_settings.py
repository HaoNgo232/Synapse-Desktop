"""
AppSettings - Typed settings dataclass cho Synapse Desktop.
Moved to shared/types to decouple presentation from storage logic.
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
    # Model ID dang su dung (vd: "gpt-5.1")
    model_id: str = "gpt-5.1"
    # Output format ID (vd: "xml", "markdown", "json", "plain")
    output_format: str = "xml"
    # Co include git diff/log trong AI context hay khong
    include_git_changes: bool = True
    # Co dung relative paths trong prompts hay khong (bao mat PII)
    use_relative_paths: bool = True

    # Có include full project tree map trong prompt hay không (tốn token nếu project lớn)
    include_full_tree: bool = False

    # Co enable semantic index (file relationships graph) hay khong (ton tai nguyen CPU/time)
    enable_semantic_index: bool = True

    # --- Security Settings ---
    # Co enable security scan truoc khi copy hay khong
    enable_security_check: bool = True

    # --- History Settings ---
    # Luu tru lich su cac instruction da su dung (toi da 30)
    instruction_history: list[str] = field(default_factory=list)

    # --- AI Context Builder Settings ---
    # API key cho LLM provider (luu plaintext, app ca nhan)
    ai_api_key: str = ""
    # Base URL cua OpenAI-compatible API (mac dinh: OpenAI chinh thuc)
    ai_base_url: str = "https://api.openai.com/v1"
    # Model ID dung cho Context Builder (VD: "gpt-4o", "deepseek-chat")
    ai_model_id: str = ""
    # Tu dong apply ket qua AI vao file tree (khong can nhan Apply thu cong)
    ai_auto_apply: bool = True
    # Bat tinh nang Continuous Memory: LLM tu tom tat phien lam viec,
    # Synapse luu lai va inject vao prompt lan sau (CHI ap dung OPX)
    enable_ai_memory: bool = True

    # --- Output Language Settings ---
    # Ngon ngu dau ra cho cac template reports (VD: "Vietnamese (tiếng Việt có dấu)", "English")
    output_language: str = "Vietnamese (tiếng Việt có dấu)"

    # --- Prompt Template Settings ---
    # Tier cua built-in prompt templates: "lite" (mac dinh) hoac "pro"
    template_tier: str = "lite"

    # --- Rule Settings ---
    # Danh sach cac ten file project rules de tu dong boc tach (VD: .cursorrules)
    rule_file_names: list[str] = field(
        default_factory=lambda: [
            ".cursorrules",
            ".windsurfrules",
            "AGENTS.md",
            "CLAUDE.md",
        ]
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        """
        Tao AppSettings tu dict, chi lay cac keys trung voi field names.
        """
        field_types: dict[str, type] = {
            f.name: f.type for f in cls.__dataclass_fields__.values()
        }

        filtered: dict[str, Any] = {}
        for key, value in data.items():
            if key not in field_types:
                continue

            expected_type = field_types[key]

            if isinstance(expected_type, str):
                type_map = {"str": str, "bool": bool, "int": int, "float": float}
                expected_type = type_map.get(expected_type, str)

            if expected_type is int and isinstance(value, bool):
                continue

            import typing

            origin = typing.get_origin(expected_type)
            check_type = origin if origin is not None else expected_type

            if isinstance(value, check_type):
                filtered[key] = value

        return cls(**filtered)

    def to_dict(self) -> dict[str, Any]:
        """
        Chuyen doi AppSettings thanh dict de luu xuong file.
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
            "ai_api_key": self.ai_api_key,
            "ai_base_url": self.ai_base_url,
            "ai_model_id": self.ai_model_id,
            "ai_auto_apply": self.ai_auto_apply,
            "enable_ai_memory": self.enable_ai_memory,
            "output_language": self.output_language,
            "template_tier": self.template_tier,
            "rule_file_names": self.rule_file_names,
            "include_full_tree": self.include_full_tree,
            "enable_semantic_index": self.enable_semantic_index,
        }

    def to_safe_dict(self) -> dict[str, Any]:
        """
        Export settings KHONG bao gom sensitive data.
        """
        d = self.to_dict()
        d.pop("ai_api_key", None)
        return d

    def get_excluded_patterns_list(self) -> list[str]:
        """
        Parse excluded_folders string thanh list cac patterns.
        """
        return [
            line.strip()
            for line in self.excluded_folders.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    def get_rule_filenames_set(self) -> set[str]:
        """
        Tra ve tap hop cac ten file duoc coi la project rules.
        """
        return {name.strip().lower() for name in self.rule_file_names if name.strip()}
