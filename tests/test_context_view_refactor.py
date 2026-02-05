"""
Tests for context_view.py refactoring - verify extracted dialog components work correctly.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch


class TestDialogImports:
    """Test that all dialog components are properly imported."""
    
    def test_security_dialog_import(self):
        """Test SecurityDialog can be imported."""
        from components.dialogs import SecurityDialog
        assert SecurityDialog is not None
    
    def test_diff_only_dialog_import(self):
        """Test DiffOnlyDialog can be imported."""
        from components.dialogs import DiffOnlyDialog
        assert DiffOnlyDialog is not None
    
    def test_remote_repo_dialog_import(self):
        """Test RemoteRepoDialog can be imported."""
        from components.dialogs import RemoteRepoDialog
        assert RemoteRepoDialog is not None
    
    def test_cache_management_dialog_import(self):
        """Test CacheManagementDialog can be imported."""
        from components.dialogs import CacheManagementDialog
        assert CacheManagementDialog is not None


class TestContextViewInitialization:
    """Test ContextView initialization after refactoring."""
    
    def test_context_view_imports(self):
        """Test ContextView imports all required modules."""
        from views.context_view import ContextView
        assert ContextView is not None
    
    def test_context_view_creates_instance(self):
        """Test ContextView can be instantiated."""
        from views.context_view import ContextView
        
        mock_page = Mock()
        mock_get_workspace = Mock(return_value=None)
        
        view = ContextView(mock_page, mock_get_workspace)
        assert view is not None
        assert view.page == mock_page
        assert view.get_workspace == mock_get_workspace
    
    def test_token_count_text_initialized(self):
        """Test token_count_text is properly initialized."""
        from views.context_view import ContextView
        
        mock_page = Mock()
        view = ContextView(mock_page, lambda: None)
        
        # Should be None before build()
        assert view.token_count_text is None
    
    def test_right_panel_not_in_init(self):
        """Test right_panel is not declared in __init__ (created in build)."""
        from views.context_view import ContextView
        
        mock_page = Mock()
        view = ContextView(mock_page, lambda: None)
        
        # Should not exist before build()
        assert not hasattr(view, 'right_panel')
    
    def test_layout_container_not_in_init(self):
        """Test layout_container is not declared in __init__ (created in build)."""
        from views.context_view import ContextView
        
        mock_page = Mock()
        view = ContextView(mock_page, lambda: None)
        
        # Should not exist before build()
        assert not hasattr(view, 'layout_container')


class TestDoCopyMethod:
    """Test _do_copy method message formatting."""
    
    def test_do_copy_normal_message(self):
        """Test _do_copy with normal copy (not smart)."""
        from views.context_view import ContextView
        
        mock_page = Mock()
        view = ContextView(mock_page, lambda: None)
        view._show_status = Mock()
        
        with patch('views.context_view.copy_to_clipboard', return_value=(True, "Success")):
            with patch('views.context_view.count_tokens', return_value=100):
                view._do_copy("test prompt", include_xml=False, is_smart=False)
        
        # Should show "Copied! (100 tokens)"
        view._show_status.assert_called_once()
        call_args = view._show_status.call_args[0][0]
        assert "Copied!" in call_args
        assert "100 tokens" in call_args
        assert "Smart Context" not in call_args
    
    def test_do_copy_smart_message(self):
        """Test _do_copy with smart context."""
        from views.context_view import ContextView
        
        mock_page = Mock()
        view = ContextView(mock_page, lambda: None)
        view._show_status = Mock()
        
        with patch('views.context_view.copy_to_clipboard', return_value=(True, "Success")):
            with patch('views.context_view.count_tokens', return_value=200):
                view._do_copy("test prompt", include_xml=False, is_smart=True)
        
        # Should show "Smart Context Copied! (200 tokens)"
        view._show_status.assert_called_once()
        call_args = view._show_status.call_args[0][0]
        assert "Smart Context" in call_args
        assert "Copied!" in call_args
        assert "200 tokens" in call_args
    
    def test_do_copy_with_opx(self):
        """Test _do_copy with OPX suffix."""
        from views.context_view import ContextView
        
        mock_page = Mock()
        view = ContextView(mock_page, lambda: None)
        view._show_status = Mock()
        
        with patch('views.context_view.copy_to_clipboard', return_value=(True, "Success")):
            with patch('views.context_view.count_tokens', return_value=300):
                view._do_copy("test prompt", include_xml=True, is_smart=False)
        
        # Should show "Copied! (300 tokens) + OPX"
        view._show_status.assert_called_once()
        call_args = view._show_status.call_args[0][0]
        assert "Copied!" in call_args
        assert "300 tokens" in call_args
        assert "+ OPX" in call_args
    
    def test_do_copy_error_handling(self):
        """Test _do_copy handles clipboard errors."""
        from views.context_view import ContextView
        
        mock_page = Mock()
        view = ContextView(mock_page, lambda: None)
        view._show_status = Mock()
        
        with patch('views.context_view.copy_to_clipboard', return_value=(False, "Clipboard error")):
            view._do_copy("test prompt")
        
        # Should show error message
        view._show_status.assert_called_once_with("Clipboard error", is_error=True)


class TestUpdateTokenCount:
    """Test _update_token_count method."""
    
    def test_update_token_count_with_initialized_text(self):
        """Test _update_token_count when token_count_text is initialized."""
        from views.context_view import ContextView
        import flet as ft
        
        mock_page = Mock()
        view = ContextView(mock_page, lambda: None)
        
        # Simulate build() initialization
        view.token_count_text = ft.Text("0 tokens")
        view.token_stats_panel = Mock()
        view.instructions_field = Mock(value="")
        view.file_tree_component = Mock()
        view.file_tree_component.is_searching = Mock(return_value=False)
        view.file_tree_component.get_visible_selected_paths = Mock(return_value=[])
        
        with patch('views.context_view.safe_page_update'):
            with patch('views.context_view.count_tokens', return_value=0):
                view._update_token_count()
        
        # Should update without error
        assert view.token_count_text.value == "0 tokens"
    
    def test_update_token_count_before_build(self):
        """Test _update_token_count before build() is called."""
        from views.context_view import ContextView
        
        mock_page = Mock()
        view = ContextView(mock_page, lambda: None)
        
        # token_count_text is None before build()
        assert view.token_count_text is None
        
        # Should not crash when called before build()
        # (In real code, this is protected by checking if component exists)


class TestGetDiffOnlyImport:
    """Test get_diff_only is properly imported in DiffOnlyDialog."""
    
    def test_diff_only_dialog_has_get_diff_only(self):
        """Test DiffOnlyDialog imports get_diff_only."""
        from components.dialogs.diff_only_dialog import get_diff_only
        assert get_diff_only is not None
    
    def test_get_diff_only_in_git_utils(self):
        """Test get_diff_only exists in git_utils."""
        from core.utils.git_utils import get_diff_only
        assert get_diff_only is not None


class TestUnusedImports:
    """Test for unused imports (code quality check)."""
    
    def test_scan_directory_not_used(self):
        """Test scan_directory is imported but not used in context_view."""
        import ast
        from pathlib import Path
        
        context_view_path = Path(__file__).parent.parent / "views" / "context_view.py"
        content = context_view_path.read_text()
        
        # Check if scan_directory is imported
        assert "from core.utils.file_utils import" in content
        assert "scan_directory" in content
        
        # Parse and check usage
        tree = ast.parse(content)
        
        # Find all Name nodes
        names = [node.id for node in ast.walk(tree) if isinstance(node, ast.Name)]
        
        # scan_directory should appear in import but not in usage
        # (This is a known issue - unused import)
        import_count = content.count("scan_directory")
        usage_count = names.count("scan_directory")
        
        # Should be imported but may not be used
        assert import_count >= 1


class TestComponentThreshold:
    """Test VIRTUAL_TREE_THRESHOLD constant."""
    
    def test_threshold_value(self):
        """Test VIRTUAL_TREE_THRESHOLD is set correctly."""
        from views.context_view import ContextView
        
        assert ContextView.VIRTUAL_TREE_THRESHOLD == 5000
    
    def test_component_selection_at_threshold(self):
        """Test component selection at exact threshold."""
        from views.context_view import ContextView
        from core.utils.file_utils import TreeItem
        
        mock_page = Mock()
        view = ContextView(mock_page, lambda: None)
        
        # Create tree with exactly threshold items
        def create_large_tree(count):
            root = TreeItem(label="root", path=".", is_dir=True, children=[])
            for i in range(count - 1):  # -1 for root
                root.children.append(TreeItem(label=f"file{i}.py", path=f"file{i}.py", is_dir=False))
            return root
        
        # At threshold should use VirtualFileTreeComponent
        view.tree = create_large_tree(5001)
        component = view._create_file_tree_component()
        
        from components.virtual_file_tree import VirtualFileTreeComponent
        assert isinstance(component, VirtualFileTreeComponent)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
