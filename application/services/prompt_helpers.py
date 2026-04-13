"""
Prompt Helpers - Separates token counting logic and utilities from PromptBuildService.
"""

from pathlib import Path
from typing import List, Optional, Set, Dict, Any, Tuple
from shared.types.prompt_types_extra import FileTokenInfo
from domain.prompt.file_collector import collect_files
import logging

logger = logging.getLogger(__name__)


def count_per_file_tokens(
    file_paths: List[Path],
    workspace: Path,
    use_relative_paths: bool,
    dep_path_set: set[str],
    tokenization_service: Any,
    codemap_paths: Optional[Set[str]] = None,
) -> List[FileTokenInfo]:
    """
    Counts tokens for each file individually to provide detailed metadata.
    """
    entries = collect_files(
        selected_paths={str(p) for p in file_paths},
        workspace_root=workspace,
        use_relative_paths=use_relative_paths,
    )

    codemap_set = codemap_paths or set()

    result: list[FileTokenInfo] = []
    for entry in entries:
        entry_path_abs = str(entry.path)
        if not Path(entry_path_abs).is_absolute():
            entry_path_abs = str((workspace / entry_path_abs).resolve())

        is_codemap_file = entry_path_abs in codemap_set
        tokens = 0

        if is_codemap_file and entry.content:
            from domain.smart_context import smart_parse, is_supported

            ext = Path(str(entry.path)).suffix.lstrip(".")
            if is_supported(ext):
                smart = smart_parse(
                    str(entry.path), entry.content, include_relationships=False
                )
                if smart:
                    tokens = tokenization_service.count_tokens(smart)
                else:
                    tokens = tokenization_service.count_tokens(entry.content)
            else:
                tokens = tokenization_service.count_tokens(entry.content)
        elif entry.content:
            tokens = tokenization_service.count_tokens(entry.content)

        result.append(
            FileTokenInfo(
                path=entry.display_path,
                tokens=tokens,
                is_dependency=str(entry.path) in dep_path_set,
                was_trimmed=False,
                is_codemap=is_codemap_file,
            )
        )

    return result


def reconstruct_file_contents(
    trimmed_contents: Dict[str, str], output_format: str
) -> str:
    """
    Re-formats trimmed dictionary content into a string based on the output_format.
    """
    if not trimmed_contents:
        return ""

    parts = []
    if output_format == "xml":
        for path, content in trimmed_contents.items():
            parts.append(f'<file path="{path}">\n{content}\n</file>')
        return "\n\n".join(parts)
    elif output_format == "json":
        import json as _json

        arr = []
        for path, content in trimmed_contents.items():
            arr.append({"path": path, "content": content})
        return _json.dumps(arr, indent=2)
    else:
        # plain
        for path, content in trimmed_contents.items():
            parts.append(f"{path}\n" + "-" * len(path) + f"\n{content}")
        return "\n\n".join(parts)


def calculate_prompt_breakdown(
    instructions: str,
    file_map: str,
    project_rules: str,
    git_diffs: Optional[Any],
    git_logs: Optional[Any],
    file_contents: str,
    include_git_changes: bool,
    include_xml_formatting: bool,
    tokenization_service: Any,
    output_format: str,
    total_token_count: int,
) -> Dict[str, int]:
    """Calculates detailed token breakdown for the prompt."""
    breakdown = {
        "instruction_tokens": tokenization_service.count_tokens(instructions)
        if instructions
        else 0,
        "tree_tokens": tokenization_service.count_tokens(file_map) if file_map else 0,
        "rule_tokens": tokenization_service.count_tokens(project_rules)
        if project_rules
        else 0,
        "diff_tokens": (
            tokenization_service.count_tokens(
                (git_diffs.work_tree_diff + git_diffs.staged_diff) if git_diffs else ""
            )
            + tokenization_service.count_tokens(
                git_logs.log_content if git_logs else ""
            )
        )
        if include_git_changes
        else 0,
    }

    breakdown["content_tokens"] = tokenization_service.count_tokens(file_contents)
    opx_t = 0
    if include_xml_formatting:
        try:
            from domain.prompt.opx_instruction import XML_FORMATTING_INSTRUCTIONS

            opx_t = tokenization_service.count_tokens(XML_FORMATTING_INSTRUCTIONS)
        except ImportError:
            opx_t = 0
    breakdown["opx_tokens"] = opx_t

    # Calculate structure tokens (overhead from tags and assembly)
    sum_parts = sum(breakdown.values())
    breakdown["structure_tokens"] = max(0, total_token_count - sum_parts)
    return breakdown


def apply_context_trimming(
    max_tokens: int,
    all_file_paths: List[Path],
    workspace: Path,
    use_relative_paths: bool,
    dep_path_set: Set[str],
    instructions: str,
    project_rules: str,
    file_map: str,
    git_diffs: Optional[Any],
    git_logs: Optional[Any],
    breakdown: Dict[str, int],
    tokenization_service: Any,
    output_format: str,
    include_xml_formatting: bool,
    instructions_at_top: bool,
    semantic_index_text: str,
    output_style: Any,
) -> Tuple[str, List[str]]:
    """Performs context trimming when token limit is exceeded."""
    from domain.prompt.context_trimmer import ContextTrimmer, PromptComponents
    from domain.prompt.file_collector import collect_files
    from domain.prompt.generator import generate_prompt

    # Collect per-file contents for the trimmer to process
    file_content_dict: Dict[str, str] = {}
    dep_display_paths: Set[str] = set()
    entries = collect_files(
        selected_paths={str(p) for p in all_file_paths},
        workspace_root=workspace,
        use_relative_paths=use_relative_paths,
    )
    protected_display_paths: Set[str] = set()
    for entry in entries:
        if entry.content is not None:
            file_content_dict[entry.display_path] = entry.content
            if str(entry.path) in dep_path_set:
                dep_display_paths.add(entry.display_path)
            else:
                protected_display_paths.add(entry.display_path)

    git_diffs_text = ""
    git_logs_text = ""
    if git_diffs:
        git_diffs_text = (git_diffs.work_tree_diff or "") + (
            git_diffs.staged_diff or ""
        )
    if git_logs:
        git_logs_text = git_logs.log_content or ""

    components = PromptComponents(
        instructions=instructions,
        project_rules=project_rules,
        file_map=file_map,
        file_contents=file_content_dict,
        git_diffs_text=git_diffs_text,
        git_logs_text=git_logs_text,
        structure_overhead=breakdown.get("structure_tokens", 0)
        + breakdown.get("opx_tokens", 0),
        dependency_paths=dep_display_paths,
        protected_paths=protected_display_paths,
    )

    trimmer = ContextTrimmer(tokenization_service, max_tokens)
    trim_result = trimmer.trim(components)

    if trim_result.levels_applied > 0:
        trimmed_comp = trim_result.components
        file_contents_trimmed = reconstruct_file_contents(
            trimmed_comp.file_contents, output_format
        )
        prompt = generate_prompt(
            file_map=trimmed_comp.file_map,
            file_contents=file_contents_trimmed,
            user_instructions=trimmed_comp.instructions,
            output_style=output_style,
            include_xml_formatting=include_xml_formatting,
            git_diffs=git_diffs if trimmed_comp.git_diffs_text else None,
            git_logs=git_logs if trimmed_comp.git_logs_text else None,
            project_rules=trimmed_comp.project_rules,
            workspace_root=workspace,
            instructions_at_top=instructions_at_top,
            semantic_index=semantic_index_text,
        )

        # Append trimmed notes
        if trim_result.notes:
            notes_section = "\n<trimmed_context_notes>\n"
            for note in trim_result.notes:
                notes_section += f"- {note}\n"
            notes_section += "</trimmed_context_notes>\n"
            prompt += notes_section
        return prompt, trim_result.notes

    return "", []
