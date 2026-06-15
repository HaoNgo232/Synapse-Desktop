from domain.ports.registry import DomainRegistry
from domain.ports.directory_scanner import IDirectoryScanner
from domain.workflow.interfaces.git_port import IGitService
from domain.workflow.interfaces.ast_parser_port import IAstParser
from domain.config.app_settings import AppSettings
from domain.smart_context.tree_item import TreeItem
from pathlib import Path
from typing import Any, Optional, List


class DummyDirectoryScanner(IDirectoryScanner):
    def scan_directory(self, root_path: Path) -> TreeItem:
        return TreeItem(label="root", path=str(root_path), is_dir=True)

    def scan_directory_shallow(
        self,
        root_path: Path,
        ignore_engine: Any,
        depth: int = 1,
        excluded_patterns: Optional[List[str]] = None,
    ) -> TreeItem:
        return TreeItem(label="root", path=str(root_path), is_dir=True)

    def load_folder_children(
        self,
        node: TreeItem,
        ignore_engine: Any,
        excluded_patterns: Optional[List[str]] = None,
        use_gitignore: bool = True,
        workspace_root: Optional[Path] = None,
    ) -> None:
        pass


class DummyGitService(IGitService):
    def get_diffs(self, root_path, base_ref=None):
        return None

    def get_logs(self, root_path, max_commits=10):
        return None

    def get_diff_only(
        self, root_path, num_commits=0, include_staged=True, include_unstaged=True
    ):
        from shared.types.git_types import DiffOnlyResult

        return DiffOnlyResult(
            diff_content="",
            files_changed=0,
            insertions=0,
            deletions=0,
            commits_included=0,
        )

    def filter_diff_by_files(self, diff_content, files):
        return ""

    def extract_changed_files_from_diff(self, diff_content):
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
    def parse_file(self, file_path):
        return {"symbols": []}

    def generate_repo_map(self, file_paths, workspace_root=None, max_files=500):
        return ""


def test_registry_new_ports():
    # 1. Directory scanner
    scanner = DummyDirectoryScanner()
    DomainRegistry.register_directory_scanner(scanner)
    assert DomainRegistry.directory_scanner() == scanner

    # 2. Git service
    git = DummyGitService()
    DomainRegistry.register_git_service(git)
    assert DomainRegistry.git_service() == git

    # 3. AST parser
    parser = DummyAstParser()
    DomainRegistry.register_ast_parser(parser)
    assert DomainRegistry.ast_parser() == parser

    # 4. Settings Provider
    DomainRegistry.register_settings_provider(
        lambda: AppSettings(output_language="Japanese")
    )
    assert DomainRegistry.settings().output_language == "Japanese"
