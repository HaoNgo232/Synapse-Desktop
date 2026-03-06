"""
Context Builder Prompts - System prompts va JSON schema cho AI Context Builder.

Module nay cung cap:
1. CONTEXT_BUILDER_SYSTEM_PROMPT: Huong dan LLM hieu nhiem vu "Context Engineer"
2. CONTEXT_SELECTION_SCHEMA: JSON Schema de ep buoc LLM tra ve danh sach file paths
3. build_context_builder_prompt(): Ghep system prompt + file tree + git diff + user query

LLM se nhan duoc:
- System prompt mo ta vai tro "Context Engineer Agent"
- File tree cua project (danh sach tat ca file paths)
- (Optional) Git diff cua nhung thay doi gan nhat
- User query mo ta cong viec muon lam

LLM phai tra ve:
- JSON object chua danh sach file paths can chon
"""

from typing import List, Optional

from core.ai.base_provider import LLMMessage
from core.utils.git_utils import GitDiffResult


# ===========================================================================
# System Prompt - Vai tro Context Engineer Agent
# ===========================================================================

CONTEXT_BUILDER_SYSTEM_PROMPT = """You are a Context Engineer Agent helping a developer select the most relevant files from their project's file tree based on their task description.

What you'll receive:
- A project file tree (list of all file paths)
- A Repo Map (optional): structural outline of code files showing class names, function signatures, and method signatures without full source code. Use this to understand where specific logic lives.
- Git diff (optional): recent uncommitted changes
- The developer's task description

Selection guidelines:
1. Only return files that actually exist in the provided file tree
2. The task description may contain long, detailed formatting rules or code snippets. Focus on the core intent of what needs to be changed/reviewed, ignoring the formatting instructions when selecting files.
3. For code changes/bug fixes: include the target files and their closely related files (imports, tests, configs)
4. For new features: include similar existing patterns/files to reference
5. For generic reviews (e.g. "review UI/UX", "audit security"): include a broad, representative set of relevant files (e.g. main specific UI components, core layout files) and their associated tests.
6. When uncertain about a file's relevance, include it. False positives are acceptable; false negatives are not.
7. Include config files (package.json, tsconfig, requirements.txt) only when relevant to the task
8. Use the Repo Map to identify files containing relevant classes/functions by their signatures

Response format:
Respond with a valid JSON object. No markdown, no explanation, no code blocks.
The JSON object should have this exact structure:
{
  "selected_paths": ["path/to/file1.py", "path/to/file2.py"],
  "reasoning": "Brief explanation of why these files were selected"
}

If you cannot determine relevant files, return:
{
  "selected_paths": [],
  "reasoning": "Could not determine relevant files because..."
}"""

# ===========================================================================
# JSON Schema - De ep buoc Structured Output (OpenAI json_schema mode)
# ===========================================================================

CONTEXT_SELECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "selected_paths": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of file paths from the project tree that are relevant to the user's task",
        },
        "reasoning": {
            "type": "string",
            "description": "Brief explanation of why these files were selected",
        },
    },
    "required": ["selected_paths", "reasoning"],
    "additionalProperties": False,
}


# ===========================================================================
# Prompt Builder - Ghep cac thanh phan thanh messages cho LLM
# ===========================================================================


def build_context_builder_messages(
    file_tree: str,
    user_query: str,
    git_diff: Optional[str] = None,
    repo_map: Optional[str] = None,
    chat_history: Optional[List[LLMMessage]] = None,
) -> List[LLMMessage]:
    """
    Ghep system prompt, file tree, repo map, git diff, va user query thanh
    danh sach messages san sang gui cho LLM.

    Thiet ke de toi uu token:
    - File tree chi chua ten file (khong gui noi dung)
    - Repo Map cung cap cau truc code (class/function signatures)
    - Git diff chi gui khi nguoi dung bat toggle
    - Chat history cho phep multi-turn conversation

    Args:
        file_tree: Cay thu muc project (output tu generate_file_map)
        user_query: Mo ta cong viec tu nguoi dung
        git_diff: Optional diff cua uncommitted changes
        repo_map: Optional Repo Map (AST outline cua code files)
        chat_history: Optional lich su hoi thoai truoc do (multi-turn)

    Returns:
        List[LLMMessage] san sang truyen vao provider.generate_structured()
    """
    messages: List[LLMMessage] = []

    # 1. System prompt (vai tro Context Engineer)
    messages.append(LLMMessage(role="system", content=CONTEXT_BUILDER_SYSTEM_PROMPT))

    # 2. Neu co lich su hoi thoai cu thi them vao
    if chat_history:
        messages.extend(chat_history)

    # 3. Xay dung user message voi context (file tree + repo map + git diff + query)
    user_content_parts: List[str] = []

    # File tree - luon co
    user_content_parts.append(f"<project_file_tree>\n{file_tree}\n</project_file_tree>")

    # Repo Map - cung cap cau truc code (class/function signatures)
    if repo_map and repo_map.strip():
        user_content_parts.append(f"<repo_map>\n{repo_map}\n</repo_map>")

    # Git diff - chi them khi nguoi dung bat toggle
    if git_diff and git_diff.strip():
        user_content_parts.append(
            f"<recent_git_changes>\n{git_diff}\n</recent_git_changes>"
        )

    # User query - luon o cuoi cung (recency bias)
    user_content_parts.append(f"<task_description>\n{user_query}\n</task_description>")

    messages.append(LLMMessage(role="user", content="\n\n".join(user_content_parts)))

    return messages


def build_full_tree_string(
    file_tree_map: str,
    git_diffs: Optional[GitDiffResult] = None,
    include_git: bool = False,
) -> tuple[str, Optional[str]]:
    """
    Chuan bi du lieu dau vao cho Context Builder.

    Tach rieng file tree va git diff de caller co the truyen
    rieng biet vao build_context_builder_messages().

    Args:
        file_tree_map: Output tu generate_file_map() (ASCII tree)
        git_diffs: Optional git diffs (work tree & staged)
        include_git: Co gom git diff vao khong

    Returns:
        Tuple (file_tree_string, git_diff_string_or_none)
    """
    git_diff_str: Optional[str] = None

    if include_git and git_diffs:
        parts: List[str] = []
        if git_diffs.work_tree_diff:
            parts.append(f"--- Work Tree Changes ---\n{git_diffs.work_tree_diff}")
        if git_diffs.staged_diff:
            parts.append(f"--- Staged Changes ---\n{git_diffs.staged_diff}")
        if parts:
            git_diff_str = "\n\n".join(parts)

    return file_tree_map, git_diff_str
