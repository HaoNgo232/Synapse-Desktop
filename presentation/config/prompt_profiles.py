"""
Prompt Profiles - Backward compatibility shim.

File này đã được chuyển sang application/config/prompt_profiles.py.
Import từ application/config/prompt_profiles để tuân theo Clean Architecture.
"""

from application.config.prompt_profiles import (
    PromptProfile,
    BUILTIN_PROFILES,
    get_profile,
    list_profiles,
)

__all__ = [
    "PromptProfile",
    "BUILTIN_PROFILES",
    "get_profile",
    "list_profiles",
]
