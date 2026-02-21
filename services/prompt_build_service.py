"""
PromptBuildService - Concrete implementation cua IPromptBuilder.

Tach logic prompt building ra khoi CopyActionsMixin thanh service doc lap.
Delegate den core.prompt_generator cho logic thuc su,
nhung wrap lai trong mot API don gian va testable.

Note: build_prompt() la high-level API nhan file_paths va settings,
noi bo se goi cac functions cu the tu core.prompt_generator theo
dung signatures cua chung.
"""

import logging
from pathlib import Path
from typing import List, Optional, Set, Tuple

from core.prompt_generator import (
    generate_file_map,
    generate_file_contents_xml,
    generate_file_contents_json,
    generate_file_contents_plain,
    generate_prompt,
    generate_smart_context,
    build_smart_prompt,
    OutputStyle,
)
from core.utils.file_utils import TreeItem
from core.utils.git_utils import get_git_diffs, get_git_logs
from services.encoder_registry import get_tokenization_service


# Mapping output_format string -> OutputStyle enum
_FORMAT_TO_STYLE = {
    "xml": OutputStyle.XML,
    "json": OutputStyle.JSON,
    "plain": OutputStyle.PLAIN,
}

# Mapping output_format string -> content generator function
_FORMAT_TO_GENERATOR = {
    "xml": generate_file_contents_xml,
    "json": generate_file_contents_json,
    "plain": generate_file_contents_plain,
}


class PromptBuildService:
    """
    Build prompt tu file paths va settings.

    Khong co state internal - moi call doc lap.
    Thread-safe vi khong mutate state.
    """

    def build_prompt(
        self,
        file_paths: List[Path],
        workspace: Path,
        instructions: str,
        output_format: str,
        include_git_changes: bool,
        use_relative_paths: bool,
        tree_item: Optional[TreeItem] = None,
        selected_paths: Optional[Set[str]] = None,
        include_xml_formatting: bool = False,
    ) -> Tuple[str, int]:
        """
        Generate prompt theo output format.

        Args:
            file_paths: Danh sach file paths da resolve
            workspace: Workspace root path
            instructions: User instructions text
            output_format: "xml", "json", "plain", hoac "smart"
            include_git_changes: Co include git diff khong
            use_relative_paths: Co dung relative paths khong
            tree_item: Root TreeItem cho file map (optional)
            selected_paths: Set paths da chon cho file map (optional)

        Returns:
            Tuple (prompt_text, token_count)
        """
        if output_format == "smart":
            prompt = self._build_smart(
                file_paths,
                workspace,
                instructions,
                include_git_changes,
                use_relative_paths,
                tree_item,
                selected_paths,
            )
        else:
            # 0. Fetch git data neu can
            git_diffs = None
            git_logs = None
            if include_git_changes:
                git_diffs = get_git_diffs(workspace)
                git_logs = get_git_logs(workspace, max_commits=5)

            # 1. Generate file map (with all paths including rules)
            file_map = ""
            if tree_item and selected_paths:
                file_map = generate_file_map(
                    tree_item,
                    selected_paths,
                    workspace_root=workspace,
                    use_relative_paths=use_relative_paths,
                )

            # 2. Extract Project Rules
            from services.settings_manager import load_app_settings

            app_settings = load_app_settings()
            rule_filenames = app_settings.get_rule_filenames_set()

            project_rules_contents = []
            normal_paths = set()
            path_strs = {str(p) for p in file_paths}

            for path_str in path_strs:
                p = Path(path_str)
                if p.name.lower() in rule_filenames:
                    try:
                        content = p.read_text(encoding="utf-8", errors="replace")
                        project_rules_contents.append(
                            f"--- Rule File: {p.name} ---\n{content}\n"
                        )
                    except Exception as e:
                        logger.warning("Failed to read rule file %s: %s", p.name, e)
                else:
                    normal_paths.add(path_str)

            project_rules = "\n".join(project_rules_contents)

            # 3. Generate file contents using only normal_paths
            content_gen = _FORMAT_TO_GENERATOR.get(
                output_format, generate_file_contents_xml
            )
            file_contents = content_gen(
                selected_paths=normal_paths,
                workspace_root=workspace,
                use_relative_paths=use_relative_paths,
            )

            # 3. Assemble prompt voi git data va xml formatting
            output_style = _FORMAT_TO_STYLE.get(output_format, OutputStyle.XML)
            prompt = generate_prompt(
                file_map=file_map,
                file_contents=file_contents,
                user_instructions=instructions,
                output_style=output_style,
                include_xml_formatting=include_xml_formatting,
                git_diffs=git_diffs,
                git_logs=git_logs,
                project_rules=project_rules,
            )

        tokenizer = get_tokenization_service()
        token_count = tokenizer.count_tokens(prompt)
        return prompt, token_count

    def count_tokens(self, text: str) -> int:
        """Dem so luong tokens trong text.

        Delegate sang TokenizationService singleton de dam bao
        cung tokenizer instance duoc su dung cho tat ca operations.

        Args:
            text: Noi dung can dem tokens

        Returns:
            So luong tokens
        """
        return get_tokenization_service().count_tokens(text)

    def build_file_map(
        self,
        tree_item: TreeItem,
        selected_paths: Set[str],
        workspace: Optional[Path] = None,
        use_relative_paths: bool = False,
    ) -> str:
        """
        Generate file map tu TreeItem va selected paths.

        Args:
            tree_item: Root TreeItem
            selected_paths: Set paths da chon
            workspace: Workspace root (optional)
            use_relative_paths: Co dung relative paths khong

        Returns:
            File map string (tree format)
        """
        return generate_file_map(
            tree_item,
            selected_paths,
            workspace_root=workspace,
            use_relative_paths=use_relative_paths,
        )

    def _build_smart(
        self,
        file_paths: List[Path],
        workspace: Path,
        instructions: str,
        include_git_changes: bool,
        use_relative_paths: bool,
        tree_item: Optional[TreeItem] = None,
        selected_paths: Optional[Set[str]] = None,
    ) -> str:
        """
        Build smart context prompt voi code maps va relationships.

        Args:
            file_paths: Danh sach file paths
            workspace: Workspace root
            instructions: User instructions
            include_git_changes: Co include git khong
            use_relative_paths: Co dung relative paths khong
            tree_item: Root TreeItem cho file map
            selected_paths: Set paths da chon
        """
        # Convert paths to string set cho generate_smart_context
        path_strs = {str(p) for p in file_paths}

        # Extract Project Rules
        from services.settings_manager import load_app_settings

        app_settings = load_app_settings()
        rule_filenames = app_settings.get_rule_filenames_set()

        project_rules_contents = []
        normal_paths = set()

        for path_str in path_strs:
            p = Path(path_str)
            if p.name.lower() in rule_filenames:
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    project_rules_contents.append(
                        f"--- Rule File: {p.name} ---\n{content}\n"
                    )
                except Exception as e:
                    logger.warning("Failed to read rule file %s: %s", p.name, e)
            else:
                normal_paths.add(path_str)

        project_rules = "\n".join(project_rules_contents)

        smart_contents = generate_smart_context(
            selected_paths=normal_paths,
            include_relationships=True,  # Giu nguyen behavior truoc refactor
            workspace_root=workspace,
            use_relative_paths=use_relative_paths,
        )

        # Generate file map
        file_map = ""
        if tree_item and selected_paths:
            file_map = generate_file_map(
                tree_item,
                selected_paths,
                workspace_root=workspace,
                use_relative_paths=use_relative_paths,
            )

        # Fetch git data neu can
        git_diffs = None
        git_logs = None
        if include_git_changes:
            git_diffs = get_git_diffs(workspace)
            git_logs = get_git_logs(workspace, max_commits=5)

        return build_smart_prompt(
            smart_contents=smart_contents,
            file_map=file_map,
            user_instructions=instructions,
            git_diffs=git_diffs,
            git_logs=git_logs,
            project_rules=project_rules,
        )


logger = logging.getLogger(__name__)


class QtClipboardService:
    """
    Clipboard service su dung Qt QApplication.clipboard().

    Phu thuoc Qt runtime nen chi dung trong app context.
    """

    def copy_to_clipboard(self, text: str) -> tuple[bool, str]:
        """
        Copy text ra system clipboard qua Qt.

        Returns:
            (success, error_message): (True, "") if success, (False, error_msg) if failed
        """
        try:
            from PySide6.QtWidgets import QApplication

            clipboard = QApplication.clipboard()
            if clipboard is None:
                msg = "QApplication.clipboard() returned None"
                logger.warning(msg)
                return False, msg

            clipboard.setText(text)
            return True, ""
        except Exception as e:
            msg = f"Clipboard error: {e}"
            logger.warning("Failed to copy to clipboard: %s", e)
            return False, msg
