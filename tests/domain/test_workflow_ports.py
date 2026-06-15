from pathlib import Path
from typing import Dict, Any, Optional
from domain.workflow.interfaces.git_port import IGitService
from domain.workflow.interfaces.ast_parser_port import IAstParser
from shared.types.git_types import GitDiffResult, GitLogResult


class DummyGitService(IGitService):
    def get_diffs(
        self, root_path: Path, base_ref: Optional[str] = None
    ) -> Optional[GitDiffResult]:
        return GitDiffResult(work_tree_diff="dummy diff", staged_diff="")

    def get_logs(
        self, root_path: Path, max_commits: int = 10
    ) -> Optional[GitLogResult]:
        return GitLogResult(log_content="dummy log")

    def get_diff_only(
        self,
        root_path: Path,
        num_commits: int = 0,
        include_staged: bool = True,
        include_unstaged: bool = True,
    ):
        from shared.types.git_types import DiffOnlyResult

        return DiffOnlyResult(
            diff_content="",
            files_changed=0,
            insertions=0,
            deletions=0,
            commits_included=0,
        )

    def filter_diff_by_files(self, diff_content: str, files: list[str]) -> str:
        return ""

    def extract_changed_files_from_diff(self, diff_content: str) -> list[str]:
        return []

    def build_diff_prompt(
        self,
        diff_result,
        instructions,
        include_changed_content,
        include_tree_structure,
        workspace_root=None,
        use_relative_paths=False,
        include_related_files=False,
        related_depth=1,
        related_max_files=20,
        output_format="xml",
    ) -> str:
        return ""


class DummyAstParser(IAstParser):
    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        return {"symbols": []}

    def generate_repo_map(
        self,
        file_paths: list[str],
        workspace_root: Optional[Path] = None,
        max_files: int = 500,
    ) -> str:
        return ""


def test_dummy_git():
    git = DummyGitService()
    diffs = git.get_diffs(Path("."))
    logs = git.get_logs(Path("."))
    assert diffs is not None
    assert diffs.work_tree_diff == "dummy diff"
    assert logs is not None
    assert logs.log_content == "dummy log"


def test_dummy_ast():
    parser = DummyAstParser()
    assert parser.parse_file(Path("test.py")) == {"symbols": []}
