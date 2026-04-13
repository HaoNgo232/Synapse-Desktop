"""
UI Tests cho tính năng Template - Kiểm tra menu và dialog chỉnh sửa.
"""

import pytest
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QWidgetAction
from domain.prompt.template_manager import TemplateInfo


class TestTemplateUI:
    @pytest.fixture
    def mock_custom_template(self):
        return TemplateInfo(
            template_id="my_custom_template",
            display_name="My Custom Template",
            description="Test description",
            is_custom=True,
        )

    def test_populate_menu_adds_edit_button(self, context_view, mock_custom_template):
        """Kiem tra menu hien thi nut Edit cho custom template."""
        view = context_view

        with patch(
            "domain.prompt.template_manager.list_templates",
            return_value=[mock_custom_template],
        ):
            view._populate_template_menu()

        menu = view._template_menu
        # Tim action co text "My Custom Template" (no la mot menu)
        custom_menu_action = next(
            (a for a in menu.actions() if a.text() == "My Custom Template"), None
        )
        assert custom_menu_action is not None
        assert custom_menu_action.menu() is not None

        sub_menu = custom_menu_action.menu()
        actions = sub_menu.actions()

        # Kiem tra co du Insert, Edit, Delete
        action_texts = [a.text() for a in actions]
        assert "Edit" in action_texts
        assert "Insert" in action_texts
        assert "Delete" in action_texts

        # Kiem tra data cua nut Edit
        edit_action = next(a for a in actions if a.text() == "Edit")
        assert edit_action.data() == {"action": "edit", "id": "my_custom_template"}

    def test_on_template_selected_opens_edit_dialog(self, context_view):
        """Kiem tra khi click Edit se mo dialog voi template_id dung."""
        view = context_view
        mock_action = MagicMock()
        mock_action.data.return_value = {"action": "edit", "id": "my_custom_template"}

        with patch.object(view, "_show_custom_template_dialog") as mock_dialog:
            view._on_template_selected(mock_action)
            mock_dialog.assert_called_once_with("my_custom_template")

    def test_custom_template_dialog_initialization(self, qtbot):
        """Kiem tra CustomTemplateDialog khoi tao dung che do Edit."""
        from presentation.components.dialogs.custom_template_dialog import (
            CustomTemplateDialog,
        )

        # Test Create mode
        dialog_create = CustomTemplateDialog()
        qtbot.addWidget(dialog_create)
        assert dialog_create.windowTitle() == "Create Custom Template"
        assert dialog_create.template_id is None

        # Test Edit mode
        with patch("domain.prompt.template_manager.get_template_info") as mock_info:
            with patch("domain.prompt.template_manager.load_template") as mock_load:
                mock_info.return_value = TemplateInfo("tid", "Name", "Desc", True)
                mock_load.return_value = "Content"

                dialog_edit = CustomTemplateDialog(template_id="my_id")
                qtbot.addWidget(dialog_edit)

                assert dialog_edit.windowTitle() == "Edit Custom Template"
                assert dialog_edit.template_id == "my_id"
                assert dialog_edit.name_input.text() == "Name"
                assert dialog_edit.desc_input.text() == "Desc"
                assert dialog_edit.content_input.toPlainText() == "Content"
                assert dialog_edit.btn_save.text() == "Update Template"

    def test_tier_selector_in_menu(self, context_view):
        """Kiem tra TierSelector (Lite/Pro) xuat hien dau menu template."""
        view = context_view
        view._populate_template_menu()

        menu = view._template_menu
        first_action = menu.actions()[0]

        # No phai la QWidgetAction chua TierSelector
        assert isinstance(first_action, QWidgetAction)
        from presentation.components.tier_selector import TierSelector

        assert isinstance(first_action.defaultWidget(), TierSelector)
