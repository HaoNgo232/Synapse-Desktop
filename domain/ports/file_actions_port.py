from typing import Protocol, Optional, List, Union, Literal, runtime_checkable
from pathlib import Path
from domain.prompt.opx_parser import FileAction
from domain.ports.action_result import ActionResult


@runtime_checkable
class IFileActionsService(Protocol):
    def apply_file_actions(
        self,
        file_actions: List[FileAction],
        workspace_roots: Optional[List[Path]] = None,
        dry_run: bool = False,
    ) -> List[ActionResult]: ...

    def apply_search_replace_to_content(
        self,
        content: str,
        search: str,
        replace: str,
        occurrence: Optional[Union[Literal["first", "last"], int]],
    ) -> tuple[bool, str, str]: ...

    def normalize_eol(self, text: str, eol: str) -> str: ...

    def rollback_apply_session(
        self,
        session: Optional[Union[object, str]] = None,
        workspace_roots: Optional[List[Path]] = None,
    ) -> object: ...

    def get_last_apply_session(self) -> Optional[object]: ...
