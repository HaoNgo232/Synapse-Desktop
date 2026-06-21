from domain.ports.registry import DomainRegistry
from domain.ports.directory_scanner import IDirectoryScanner
from domain.ports.git_port import IGitService
from domain.ports.code_intelligence_port import ICodeIntelligencePort, ParsedCodeInfo
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


class DummyCodeIntelligence(ICodeIntelligencePort):
    def parse_file(self, file_path: Path, content: str) -> ParsedCodeInfo:
        return ParsedCodeInfo(file_path=file_path, language="py")

    def generate_repo_map(self, file_paths: List[str], workspace_root: Optional[Path] = None, max_files: int = 500) -> str:
        return ""


def test_registry_new_ports():
    # Save old registry values to prevent test pollution
    old_scanner = None
    old_git = None
    old_ci = None
    old_settings = None
    try:
        old_scanner = DomainRegistry.directory_scanner()
    except RuntimeError:
        pass
    try:
        old_git = DomainRegistry.git_service()
    except RuntimeError:
        pass
    try:
        old_ci = DomainRegistry.code_intelligence()
    except RuntimeError:
        pass
    try:
        old_settings = DomainRegistry._settings_provider
    except AttributeError:
        pass

    try:
        # 1. Directory scanner
        scanner = DummyDirectoryScanner()
        DomainRegistry.register_directory_scanner(scanner)
        assert DomainRegistry.directory_scanner() == scanner

        # 2. Git service
        git = DummyGitService()
        DomainRegistry.register_git_service(git)
        assert DomainRegistry.git_service() == git

        # 3. Code intelligence
        ci = DummyCodeIntelligence()
        DomainRegistry.register_code_intelligence(ci)
        assert DomainRegistry.code_intelligence() == ci

        # 4. Settings Provider
        DomainRegistry.register_settings_provider(
            lambda: AppSettings(output_language="Japanese")
        )
        assert DomainRegistry.settings().output_language == "Japanese"
    finally:
        # Restore old registry values
        if old_scanner is not None:
            DomainRegistry.register_directory_scanner(old_scanner)
        if old_git is not None:
            DomainRegistry.register_git_service(old_git)
        if old_ci is not None:
            DomainRegistry.register_code_intelligence(old_ci)
        if old_settings is not None:
            DomainRegistry.register_settings_provider(old_settings)
