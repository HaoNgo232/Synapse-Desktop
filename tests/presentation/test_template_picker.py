import pytest
import re
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QWidget
from domain.prompt.template_manager import TemplateInfo
from tests.ui.conftest import context_view, reset_toast_manager, FakeFileTreeWidget, FakeTokenStatsPanel

def test_picker_shows_exactly_7_builtin(context_view):
    """Kiểm tra template picker hiển thị chính xác 7 templates built-in."""
    view = context_view
    
    # Mock list_templates trả về 7 templates mặc định
    builtin_templates = [
        TemplateInfo(template_id=f"t_{i}", display_name=f"Template {i}", description=f"Desc {i}", is_custom=False)
        for i in range(7)
    ]
    
    with patch("domain.prompt.template_manager.list_templates", return_value=builtin_templates):
        view._populate_template_menu()
        
    menu = view._template_menu
    actions = menu.actions()
    
    # Lọc ra các builtin template actions (loại bỏ separator và custom actions như Manage/Add...)
    builtin_actions = []
    for action in actions:
        if action.isSeparator() or action.text() == "Manage/Add Custom Template...":
            continue
        data = action.data()
        if data and isinstance(data, str) and data.startswith("t_"):
            builtin_actions.append(action)
            
    assert len(builtin_actions) == 7

def test_no_tier_ui_elements_present(context_view):
    """Kiểm tra không còn UI elements nào liên quan đến tier (lite, pro, tier)."""
    view = context_view
    
    # 1. Kiểm tra tất cả các widgets trong context_view
    from PySide6.QtWidgets import QLabel, QPushButton, QCheckBox, QRadioButton
    
    # Kích hoạt vẽ menu để đảm bảo mọi thứ đã populate
    view._populate_template_menu()
    
    for widget in view.findChildren(QWidget):
        text = ""
        if isinstance(widget, (QLabel, QPushButton, QCheckBox, QRadioButton)):
            text = widget.text().lower()
        
        tooltip = widget.toolTip().lower()
        
        # Dùng regex \b để bắt các từ đứng độc lập
        assert not re.search(r'\b(lite|pro|tier)\b', text), f"Found invalid tier word in widget text: {text}"
        assert not re.search(r'\b(lite|pro|tier)\b', tooltip), f"Found invalid tier word in widget tooltip: {tooltip}"

    # 2. Kiểm tra menu actions
    for action in view._template_menu.actions():
        text = action.text().lower()
        tooltip = action.toolTip().lower()
        
        assert not re.search(r'\b(lite|pro|tier)\b', text), f"Found invalid tier word in action text: {text}"
        assert not re.search(r'\b(lite|pro|tier)\b', tooltip), f"Found invalid tier word in action tooltip: {tooltip}"

def test_custom_templates_shown_at_bottom(context_view):
    """Kiểm tra custom templates hiển thị ở cuối danh sách với text '(Custom)' bên cạnh."""
    view = context_view
    
    # Mock list_templates trả về 2 builtin và 2 custom templates
    templates = [
        TemplateInfo(template_id="b_1", display_name="Builtin 1", description="D1", is_custom=False),
        TemplateInfo(template_id="b_2", display_name="Builtin 2", description="D2", is_custom=False),
        TemplateInfo(template_id="c_1", display_name="Custom 1", description="D3", is_custom=True),
        TemplateInfo(template_id="c_2", display_name="Custom 2", description="D4", is_custom=True),
    ]
    
    with patch("domain.prompt.template_manager.list_templates", return_value=templates):
        view._populate_template_menu()
        
    menu = view._template_menu
    actions = menu.actions()
    
    # Lấy các action có chứa template ID thực (bỏ qua separator và Manage...)
    template_actions = []
    for action in actions:
        if action.isSeparator() or action.text() == "Manage/Add Custom Template...":
            continue
        template_actions.append(action)
        
    assert len(template_actions) == 4
    
    # 2 template đầu tiên phải là builtin
    assert template_actions[0].text() == "Builtin 1"
    assert template_actions[1].text() == "Builtin 2"
    
    # 2 template sau phải là custom và có chữ (Custom) bên cạnh tên
    # Sử dụng menuAction().text() cho submenu của custom template
    assert template_actions[2].text() == "Custom 1 (Custom)"
    assert template_actions[3].text() == "Custom 2 (Custom)"

def test_template_selection_injects_to_instructions(context_view):
    """Kiểm tra việc chọn template sẽ inject content của nó vào instructions field."""
    view = context_view
    
    mock_action = MagicMock()
    mock_action.data.return_value = "my_template_id"
    
    with patch("domain.prompt.template_manager.load_template", return_value="Refactor this code to follow SOLID.") as mock_load:
        view._on_template_selected(mock_action)
        mock_load.assert_called_once_with("my_template_id")
        
    assert view._instructions_field.toPlainText() == "Refactor this code to follow SOLID."

def test_no_hardcoded_template_count(context_view):
    """Kiểm tra không hardcode số lượng template trong code UI."""
    view = context_view
    
    # Thử với 3 templates
    templates_3 = [
        TemplateInfo(template_id=f"t_{i}", display_name=f"Template {i}", description=f"Desc {i}", is_custom=False)
        for i in range(3)
    ]
    with patch("domain.prompt.template_manager.list_templates", return_value=templates_3):
        view._populate_template_menu()
        
    actions = [a for a in view._template_menu.actions() if not a.isSeparator() and a.text() != "Manage/Add Custom Template..."]
    assert len(actions) == 3
    
    # Thử với 10 templates
    templates_10 = [
        TemplateInfo(template_id=f"t_{i}", display_name=f"Template {i}", description=f"Desc {i}", is_custom=False)
        for i in range(10)
    ]
    with patch("domain.prompt.template_manager.list_templates", return_value=templates_10):
        view._populate_template_menu()
        
    actions = [a for a in view._template_menu.actions() if not a.isSeparator() and a.text() != "Manage/Add Custom Template..."]
    assert len(actions) == 10
