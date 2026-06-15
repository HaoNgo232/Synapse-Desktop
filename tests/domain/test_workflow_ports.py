from pathlib import Path
from typing import Dict, Any, Optional
from domain.workflow.interfaces.git_port import IGitService
from domain.workflow.interfaces.ast_parser_port import IAstParser
from shared.types.git_types import GitDiffResult, GitLogResult

class DummyGitService(IGitService):
    def get_diffs(self, root_path: Path, base_ref: Optional[str] = None) -> Optional[GitDiffResult]:
        return GitDiffResult(work_tree_diff="dummy diff", staged_diff="")
    def get_logs(self, root_path: Path, max_commits: int = 10) -> Optional[GitLogResult]:
        return GitLogResult(log_content="dummy log")

class DummyAstParser(IAstParser):
    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        return {"symbols": []}

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
