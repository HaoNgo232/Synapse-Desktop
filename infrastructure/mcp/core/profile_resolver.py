"""
Profile Resolver - Resolve profile parameters cho build_prompt.

Module nay xu ly logic merge giua explicit params, profile defaults,
va global defaults theo nguyen tac uu tien:
explicit param > profile default > global default.
"""

from typing import Optional


def resolve_profile_params(
    profile_name: Optional[str],
    output_format: str,
    include_git_changes: bool,
    instructions: str,
    max_tokens: Optional[int],
    auto_expand_dependencies: bool,
) -> tuple[str, bool, str, Optional[int], bool, Optional[str]]:
    """Merge profile defaults vao params, explicit params luon thang.

    Tra ve tuple (output_format, include_git_changes, instructions,
    max_tokens, auto_expand_dependencies, resolved_profile_name).

    Args:
        profile_name: Ten profile (None = khong dung profile).
        output_format: Output format tu caller.
        include_git_changes: Git changes flag tu caller.
        instructions: User instructions tu caller.
        max_tokens: Token limit tu caller.
        auto_expand_dependencies: Dependency expansion flag tu caller.

    Returns:
        Tuple cac params da resolve, profile_name da validate.

    Raises:
        ValueError: Khi profile_name khong ton tai trong registry.
    """
    if not profile_name:
        return (
            output_format,
            include_git_changes,
            instructions,
            max_tokens,
            auto_expand_dependencies,
            None,
        )

    from presentation.config.prompt_profiles import get_profile, list_profiles

    prof = get_profile(profile_name)
    if prof is None:
        available = ", ".join(list_profiles())
        raise ValueError(f"Unknown profile '{profile_name}'. Available: {available}")

    # Merge: chi ap dung profile default khi caller KHONG truyen explicit
    # Output format: "xml" la default global -> chi override khi caller giu default
    resolved_format = output_format
    if output_format == "xml" and prof.output_format is not None:
        resolved_format = prof.output_format

    # include_git_changes: False la default global -> chi override khi False
    resolved_git = include_git_changes
    if not include_git_changes and prof.include_git_changes is not None:
        resolved_git = prof.include_git_changes

    # Instructions: prepend profile instruction_prefix
    resolved_instructions = instructions
    if prof.instruction_prefix:
        if instructions:
            resolved_instructions = prof.instruction_prefix + "\n" + instructions
        else:
            resolved_instructions = prof.instruction_prefix

    # max_tokens: None la default global
    resolved_max_tokens = max_tokens
    if max_tokens is None and prof.max_tokens is not None:
        resolved_max_tokens = prof.max_tokens

    # auto_expand_dependencies: False la default global
    resolved_expand = auto_expand_dependencies
    if not auto_expand_dependencies and prof.auto_expand_dependencies is not None:
        resolved_expand = prof.auto_expand_dependencies

    return (
        resolved_format,
        resolved_git,
        resolved_instructions,
        resolved_max_tokens,
        resolved_expand,
        prof.name,
    )
