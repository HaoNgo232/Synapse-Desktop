"""
Integration tests for auto-codemap feature in context_handler.

Tests the automatic codemap assignment for transitive dependencies (depth >= 2).
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from infrastructure.mcp.handlers.context_handler import register_tools


class TestAutoCodemapFeature:
    """Integration tests for auto-codemap with dependency depth >= 2."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP instance."""
        mcp = Mock()
        mcp.registered_tools = {}  # Track registered tools by name

        def tool_decorator(func):
            """Decorator that captures registered tools."""
            mcp.registered_tools[func.__name__] = func
            return func

        mcp.tool = Mock(side_effect=lambda: tool_decorator)
        return mcp

    @pytest.fixture
    def workspace(self, tmp_path):
        """Create test workspace."""
        (tmp_path / "main.py").write_text("import utils")
        (tmp_path / "utils.py").write_text("import helpers")
        (tmp_path / "helpers.py").write_text("# leaf")
        return tmp_path

    @pytest.mark.asyncio
    async def test_auto_codemap_depth_2_dependencies(self, mock_mcp, workspace):
        """Test that depth >= 2 dependencies are automatically added to codemap."""
        # Arrange
        register_tools(mock_mcp)
        build_prompt_func = mock_mcp.registered_tools["build_prompt"]

        with (
            patch(
                "infrastructure.mcp.handlers.context_handler.WorkspaceManager"
            ) as mock_ws,
            patch(
                "infrastructure.mcp.handlers.context_handler.resolve_profile_params"
            ) as mock_profile,
            # Patch at import location (inside build_prompt function)
            patch(
                "domain.codemap.dependency_resolver.DependencyResolver"
            ) as mock_resolver_cls,
            patch(
                "application.services.prompt_build_service.PromptBuildService"
            ) as mock_service_cls,
        ):
            # Mock workspace resolution
            mock_ws.resolve = AsyncMock(return_value=workspace)

            # Mock profile resolution
            mock_profile.return_value = ("xml", False, "", None, True, None)

            # Mock dependency resolver
            mock_resolver = Mock()
            mock_resolver_cls.return_value = mock_resolver

            # Mock get_related_files_with_depth to return depth info
            utils_file = workspace / "utils.py"
            helpers_file = workspace / "helpers.py"

            mock_resolver.get_related_files_with_depth.return_value = {
                utils_file: 1,  # Direct dependency
                helpers_file: 2,  # Transitive dependency (should be auto-codemap)
            }

            # Mock PromptBuildService
            mock_service = Mock()
            mock_service_cls.return_value = mock_service

            mock_result = Mock()
            mock_result.prompt_text = "test prompt"
            mock_result.total_tokens = 100
            mock_result.breakdown = {}
            mock_service.build_prompt_full.return_value = mock_result

            # Act
            await build_prompt_func(
                file_paths=["main.py"],
                workspace_path=str(workspace),
                auto_expand_dependencies=True,
                dependency_depth=2,
            )

            # Assert: helpers.py should be in codemap_paths
            call_kwargs = mock_service.build_prompt_full.call_args[1]
            codemap_set = call_kwargs["codemap_paths"]

            assert codemap_set is not None
            assert str(helpers_file) in codemap_set
            assert str(utils_file) not in codemap_set  # Depth 1 should not be codemap

    @pytest.mark.asyncio
    async def test_auto_codemap_depth_1_no_auto_codemap(self, mock_mcp, workspace):
        """Test that depth=1 does not trigger auto-codemap."""
        # Arrange
        register_tools(mock_mcp)
        build_prompt_func = mock_mcp.registered_tools["build_prompt"]

        with (
            patch(
                "infrastructure.mcp.handlers.context_handler.WorkspaceManager"
            ) as mock_ws,
            patch(
                "infrastructure.mcp.handlers.context_handler.resolve_profile_params"
            ) as mock_profile,
            patch(
                "domain.codemap.dependency_resolver.DependencyResolver"
            ) as mock_resolver_cls,
            patch(
                "application.services.prompt_build_service.PromptBuildService"
            ) as mock_service_cls,
        ):
            mock_ws.resolve = AsyncMock(return_value=workspace)
            mock_profile.return_value = ("xml", False, "", None, True, None)

            mock_resolver = Mock()
            mock_resolver_cls.return_value = mock_resolver

            # Only depth 1 dependencies
            mock_resolver.get_related_files.return_value = {workspace / "utils.py"}

            mock_service = Mock()
            mock_service_cls.return_value = mock_service

            mock_result = Mock()
            mock_result.prompt_text = "test"
            mock_result.total_tokens = 50
            mock_result.breakdown = {}
            mock_service.build_prompt_full.return_value = mock_result

            # Act
            await build_prompt_func(
                file_paths=["main.py"],
                workspace_path=str(workspace),
                auto_expand_dependencies=True,
                dependency_depth=1,
            )

            # Assert: codemap_paths should be None or empty
            call_kwargs = mock_service.build_prompt_full.call_args[1]
            codemap_set = call_kwargs.get("codemap_paths")

            assert codemap_set is None or len(codemap_set) == 0

    @pytest.mark.asyncio
    async def test_user_codemap_paths_merged_with_auto_codemap(
        self, mock_mcp, workspace
    ):
        """Test that user-specified codemap_paths are merged with auto-detected ones."""
        # Arrange
        register_tools(mock_mcp)
        build_prompt_func = mock_mcp.registered_tools["build_prompt"]

        with (
            patch(
                "infrastructure.mcp.handlers.context_handler.WorkspaceManager"
            ) as mock_ws,
            patch(
                "infrastructure.mcp.handlers.context_handler.resolve_profile_params"
            ) as mock_profile,
            patch(
                "domain.codemap.dependency_resolver.DependencyResolver"
            ) as mock_resolver_cls,
            patch(
                "application.services.prompt_build_service.PromptBuildService"
            ) as mock_service_cls,
        ):
            mock_ws.resolve = AsyncMock(return_value=workspace)
            mock_profile.return_value = ("xml", False, "", None, True, None)

            mock_resolver = Mock()
            mock_resolver_cls.return_value = mock_resolver

            # Depth 2 dependency
            helpers_file = workspace / "helpers.py"
            mock_resolver.get_related_files_with_depth.return_value = {
                workspace / "utils.py": 1,
                helpers_file: 2,
            }

            mock_service = Mock()
            mock_service_cls.return_value = mock_service

            mock_result = Mock()
            mock_result.prompt_text = "test"
            mock_result.total_tokens = 100
            mock_result.breakdown = {}
            mock_service.build_prompt_full.return_value = mock_result

            # Act: User specifies utils.py as codemap, auto should add helpers.py
            await build_prompt_func(
                file_paths=["main.py"],
                workspace_path=str(workspace),
                auto_expand_dependencies=True,
                dependency_depth=2,
                codemap_paths=["utils.py"],  # User-specified
            )

            # Assert: Both user-specified and auto-detected should be in codemap
            call_kwargs = mock_service.build_prompt_full.call_args[1]
            codemap_set = call_kwargs["codemap_paths"]

            assert str(workspace / "utils.py") in codemap_set  # User-specified
            assert str(helpers_file) in codemap_set  # Auto-detected

    @pytest.mark.asyncio
    async def test_auto_codemap_depth_3_includes_all_transitive(
        self, mock_mcp, workspace
    ):
        """Test that depth=3 auto-codemaps both depth 2 and depth 3 dependencies."""
        # Arrange
        register_tools(mock_mcp)
        build_prompt_func = mock_mcp.registered_tools["build_prompt"]

        (workspace / "db.py").write_text("# database")

        with (
            patch(
                "infrastructure.mcp.handlers.context_handler.WorkspaceManager"
            ) as mock_ws,
            patch(
                "infrastructure.mcp.handlers.context_handler.resolve_profile_params"
            ) as mock_profile,
            patch(
                "domain.codemap.dependency_resolver.DependencyResolver"
            ) as mock_resolver_cls,
            patch(
                "application.services.prompt_build_service.PromptBuildService"
            ) as mock_service_cls,
        ):
            mock_ws.resolve = AsyncMock(return_value=workspace)
            mock_profile.return_value = ("xml", False, "", None, True, None)

            mock_resolver = Mock()
            mock_resolver_cls.return_value = mock_resolver

            # Three levels of dependencies
            mock_resolver.get_related_files_with_depth.return_value = {
                workspace / "utils.py": 1,
                workspace / "helpers.py": 2,
                workspace / "db.py": 3,
            }

            mock_service = Mock()
            mock_service_cls.return_value = mock_service

            mock_result = Mock()
            mock_result.prompt_text = "test"
            mock_result.total_tokens = 150
            mock_result.breakdown = {}
            mock_service.build_prompt_full.return_value = mock_result

            # Act
            await build_prompt_func(
                file_paths=["main.py"],
                workspace_path=str(workspace),
                auto_expand_dependencies=True,
                dependency_depth=3,
            )

            # Assert: Both depth 2 and 3 should be codemap
            call_kwargs = mock_service.build_prompt_full.call_args[1]
            codemap_set = call_kwargs["codemap_paths"]

            assert str(workspace / "helpers.py") in codemap_set  # Depth 2
            assert str(workspace / "db.py") in codemap_set  # Depth 3
            assert str(workspace / "utils.py") not in codemap_set  # Depth 1
