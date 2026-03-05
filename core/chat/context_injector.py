"""
Context Injector - Build context cho moi chat turn.

Module nay chiu trach nhiem tao ChatContext tu trang thai hien tai cua workspace:
- File map (ASCII tree)
- Noi dung cac files duoc chon
- Git diffs (neu enabled)
- Project rules (AGENTS.md, .cursorrules, v.v.)
- Memory tu cac phien truoc

Reuse PromptBuildService de generate context, dam bao nhat quan
voi luong Copy context hien co.
"""

import logging
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from core.chat.message_types import ChatContext

if TYPE_CHECKING:
    from services.prompt_build_service import PromptBuildService

logger = logging.getLogger(__name__)


class ContextInjector:
    """
    Tao ChatContext tu trang thai workspace hien tai.

    Inject context vao system message de LLM co du thong tin
    de tro loi chinh xac.

    Attributes:
        _prompt_builder: Service de build context tu files
    """

    def __init__(self, prompt_builder: Optional["PromptBuildService"] = None) -> None:
        """
        Khoi tao ContextInjector.

        Args:
            prompt_builder: PromptBuildService instance de generate context.
                            Neu None, se khoi tao instance moi.
        """
        if prompt_builder is None:
            from services.prompt_build_service import PromptBuildService

            prompt_builder = PromptBuildService()
        self._prompt_builder = prompt_builder

    def build_context(
        self,
        workspace: Optional[Path],
        selected_paths: List[str],
        include_git_changes: bool = True,
        max_tokens: int = 50000,
    ) -> ChatContext:
        """
        Tao ChatContext tu workspace va selection hien tai.

        Args:
            workspace: Duong dan workspace root
            selected_paths: Danh sach paths cac files duoc chon
            include_git_changes: Co include git diffs hay khong
            max_tokens: Token budget toi da cho context

        Returns:
            ChatContext da duoc populate voi thong tin workspace
        """
        context = ChatContext(
            workspace_path=str(workspace) if workspace else None,
            selected_file_paths=list(selected_paths),
        )

        if not workspace or not workspace.exists():
            return context

        try:
            # Generate file map (ASCII tree)
            context.file_map = self._build_file_map(workspace)
        except Exception as e:
            logger.warning("Could not generate file map: %s", e)

        if selected_paths:
            try:
                # Generate file contents cho cac files duoc chon
                context.selected_files_content = self._build_file_contents(
                    workspace, selected_paths
                )
            except Exception as e:
                logger.warning("Could not generate file contents: %s", e)

        if include_git_changes:
            try:
                context.git_diffs = self._build_git_diffs(workspace)
            except Exception as e:
                logger.warning("Could not get git diffs: %s", e)

        try:
            context.project_rules = self._build_project_rules(workspace)
        except Exception as e:
            logger.warning("Could not get project rules: %s", e)

        try:
            context.memory = self._load_memory(workspace)
        except Exception as e:
            logger.warning("Could not load memory: %s", e)

        return context

    def _build_file_map(self, workspace: Path) -> str:
        """Generate ASCII tree cho workspace."""
        try:
            from core.prompt_generator import generate_file_map

            return generate_file_map(workspace) or ""
        except Exception as e:
            logger.debug("File map generation failed: %s", e)
            return ""

    def _build_file_contents(
        self,
        workspace: Path,
        selected_paths: List[str],
    ) -> str:
        """Generate noi dung cac files duoc chon (XML format)."""
        try:
            from core.prompting.file_collector import collect_files
            from core.prompt_generator import generate_file_contents_xml

            file_paths = [
                workspace / p if not Path(p).is_absolute() else Path(p)
                for p in selected_paths
            ]
            file_paths = [p for p in file_paths if p.exists()]

            if not file_paths:
                return ""

            file_data = collect_files(file_paths, workspace, use_relative_paths=True)
            return generate_file_contents_xml(file_data) or ""
        except Exception as e:
            logger.debug("File contents generation failed: %s", e)
            return ""

    def _build_git_diffs(self, workspace: Path) -> str:
        """Lay git diffs hien tai."""
        try:
            from core.utils.git_utils import get_git_diffs

            diffs = get_git_diffs(workspace)
            return diffs or ""
        except Exception as e:
            logger.debug("Git diffs failed: %s", e)
            return ""

    def _build_project_rules(self, workspace: Path) -> str:
        """Lay noi dung cac rule files (AGENTS.md, .cursorrules, v.v.)."""
        try:
            from services.workspace_rules import get_rule_file_contents

            rules = get_rule_file_contents(workspace)
            return rules or ""
        except Exception as e:
            logger.debug("Project rules failed: %s", e)
            return ""

    def _load_memory(self, workspace: Path) -> str:
        """Load continuous memory tu .synapse/memory.xml neu co."""
        try:
            memory_file = workspace / ".synapse" / "memory.xml"
            if memory_file.exists():
                return memory_file.read_text(encoding="utf-8")
            return ""
        except Exception as e:
            logger.debug("Memory load failed: %s", e)
            return ""
