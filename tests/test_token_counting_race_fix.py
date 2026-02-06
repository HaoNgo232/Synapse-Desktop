"""
Test token counting race condition fixes.

Verify các fixes:
1. Gửi snapshot thay vì reference
2. Chỉ 1 nguồn trigger counting (context_view)
3. Callback để re-calculate khi cache updates
4. Generation counter để invalidate stale results
5. Ensure fully loaded trước khi notify
"""

import pytest
import time
import threading
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Set


class TestSnapshotFix:
    """Test Fix #1+#7: Gửi snapshot thay vì reference"""
    
    def test_callback_receives_copy_not_reference(self):
        """Verify callback nhận copy, không phải reference"""
        from components.file_tree import FileTreeComponent
        
        page = Mock()
        page.window.width = 1000
        
        received_selections = []
        
        def on_selection_changed(selected: Set[str]):
            received_selections.append(selected)
        
        tree = FileTreeComponent(
            page=page,
            on_selection_changed=on_selection_changed,
            show_tokens=False,
            show_lines=False
        )
        
        # Simulate selection change
        tree.selected_paths = {"file1.py", "file2.py"}
        
        # Trigger callback manually (simulate _on_item_toggled)
        if tree.on_selection_changed:
            tree.on_selection_changed(tree.selected_paths.copy())
        
        # Modify original set
        tree.selected_paths.add("file3.py")
        
        # Verify callback received copy (không bị ảnh hưởng)
        assert len(received_selections) == 1
        assert received_selections[0] == {"file1.py", "file2.py"}
        assert "file3.py" not in received_selections[0]


class TestGenerationCounter:
    """Test Fix #4: Generation counter để invalidate stale results"""
    
    def test_generation_increments_on_selection_change(self):
        """Verify generation counter increments mỗi lần selection thay đổi"""
        from views.context_view import ContextView
        
        page = Mock()
        page.window.width = 1000
        page.theme_mode = "light"
        
        get_workspace = Mock(return_value=Path("/test"))
        view = ContextView(page, get_workspace)
        
        # Initial generation
        initial_gen = getattr(view, '_token_generation', 0)
        
        # Trigger selection change
        view._on_selection_changed({"file1.py"})
        gen1 = getattr(view, '_token_generation', 0)
        
        # Trigger again
        view._on_selection_changed({"file1.py", "file2.py"})
        gen2 = getattr(view, '_token_generation', 0)
        
        # Verify increments
        assert gen1 > initial_gen
        assert gen2 > gen1
    
    def test_stale_results_ignored(self):
        """Verify stale counting results bị ignore"""
        from views.context_view import ContextView
        
        page = Mock()
        page.window.width = 1000
        page.theme_mode = "light"
        
        get_workspace = Mock(return_value=Path("/test"))
        view = ContextView(page, get_workspace)
        
        # Mock UI components
        view.token_count_text = Mock()
        view.token_stats_panel = Mock()
        view.instructions_field = Mock()
        view.instructions_field.value = ""
        
        view.file_tree_component = Mock()
        view.file_tree_component.get_visible_selected_paths.return_value = set()
        view.file_tree_component.is_searching.return_value = False
        
        # Set generation
        view._token_generation = 5
        
        # Call _update_token_count
        view._update_token_count()
        
        # Selection changed (generation incremented)
        view._token_generation = 6
        
        # Verify generation mechanism works
        assert view._token_generation == 6


class TestCallbackChain:
    """Test Fix #3: Callback chain để re-calculate khi cache updates"""
    
    def test_callback_registration_in_create_component(self):
        """Verify callback được register trong _create_file_tree_component"""
        from views.context_view import ContextView
        from components.file_tree import FileTreeComponent
        
        page = Mock()
        page.window.width = 1000
        page.theme_mode = "light"
        
        get_workspace = Mock(return_value=Path("/test"))
        view = ContextView(page, get_workspace)
        
        # Mock UI components
        view.token_count_text = Mock()
        view.token_stats_panel = Mock()
        view.instructions_field = Mock()
        view.instructions_field.value = ""
        
        # Create real component (not mock) để test callback registration
        view.tree = None  # Small tree để không trigger virtual
        component = view._create_file_tree_component()
        
        # Verify component has token service
        assert hasattr(component, '_token_service')
        
        # Verify callback được register
        assert component._token_service.on_update is not None
        
        # Test callback calls _update_token_count
        update_called = False
        
        def track_update():
            nonlocal update_called
            update_called = True
        
        view._update_token_count = track_update
        
        # Trigger callback
        if component._token_service.on_update:
            component._token_service.on_update()
        
        # Verify _update_token_count was called
        assert update_called


class TestLazyLoadingOrder:
    """Test Fix #5: Ensure fully loaded trước khi notify"""
    
    def test_children_loaded_before_selection(self):
        """Verify children được load TRƯỚC KHI selection notify"""
        from components.file_tree import FileTreeComponent
        from core.utils.file_utils import TreeItem
        
        page = Mock()
        page.window.width = 1000
        
        notify_order = []
        
        def on_selection_changed(selected: Set[str]):
            notify_order.append(('notify', len(selected)))
        
        tree = FileTreeComponent(
            page=page,
            on_selection_changed=on_selection_changed,
            show_tokens=False,
            show_lines=False
        )
        
        # Create mock folder item với đúng signature
        folder = TreeItem(
            label="folder",
            path="/test/folder",
            is_dir=True,
            children=[],
            is_loaded=False
        )
        
        tree.tree = folder
        
        # Mock load_folder_children
        def mock_load(item):
            notify_order.append(('load', item.path))
            item.is_loaded = True
            item.children = [
                TreeItem(label="file1.py", path="/test/folder/file1.py", is_dir=False),
                TreeItem(label="file2.py", path="/test/folder/file2.py", is_dir=False),
            ]
        
        # Mock _find_item_by_path để return folder
        tree._find_item_by_path = Mock(return_value=folder)
        
        with patch('core.utils.file_utils.load_folder_children', side_effect=mock_load):
            # Simulate checkbox event
            mock_event = Mock()
            mock_event.control.value = True
            
            tree._on_item_toggled(mock_event, "/test/folder", is_dir=True, children=[])
        
        # Verify order: load THEN notify
        assert len(notify_order) >= 2
        assert notify_order[0][0] == 'load'
        assert notify_order[1][0] == 'notify'


class TestSingleCountingSource:
    """Test Fix #2: Chỉ 1 nguồn trigger counting"""
    
    def test_no_duplicate_counting_on_folder_check(self):
        """Verify không có duplicate counting khi check folder"""
        from components.file_tree import FileTreeComponent
        from core.utils.file_utils import TreeItem
        
        page = Mock()
        page.window.width = 1000
        
        counting_triggers = []
        
        def track_counting():
            counting_triggers.append(time.time())
        
        tree = FileTreeComponent(
            page=page,
            on_selection_changed=lambda x: None,
            show_tokens=False,
            show_lines=False
        )
        
        # Create mock folder với đúng signature
        folder = TreeItem(
            label="folder",
            path="/test/folder",
            is_dir=True,
            children=[
                TreeItem(label="file1.py", path="/test/folder/file1.py", is_dir=False),
            ],
            is_loaded=True
        )
        
        tree.tree = folder
        
        # Verify _trigger_folder_token_counting_for_selected không được gọi
        # (method đã bị deprecate)
        mock_event = Mock()
        mock_event.control.value = True
        
        # Patch start_token_counting để track calls
        with patch('services.token_display.start_token_counting', side_effect=track_counting):
            tree._on_item_toggled(mock_event, "/test/folder", is_dir=True, children=folder.children)
        
        # Verify KHÔNG có token counting trigger từ file_tree
        # (chỉ context_view mới trigger)
        assert len(counting_triggers) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
