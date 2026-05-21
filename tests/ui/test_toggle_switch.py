"""
Unit tests cho ToggleSwitch widget.
Kiểm tra trạng thái khởi tạo, chức năng setChecked, phương thức toggle,
và xử lý các sự kiện chuột (click, hover).
"""

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot
from presentation.components.toggle_switch import ToggleSwitch


def test_toggle_switch_initialization(qtbot: QtBot) -> None:
    """
    Kiểm tra khởi tạo ToggleSwitch với trạng thái Checked mặc định hoặc tùy chỉnh.
    """
    # Khởi tạo mặc định (False)
    switch_off = ToggleSwitch()
    qtbot.addWidget(switch_off)
    assert switch_off.isChecked() is False

    # Khởi tạo với Checked = True
    switch_on = ToggleSwitch(checked=True)
    qtbot.addWidget(switch_on)
    assert switch_on.isChecked() is True


def test_toggle_switch_set_checked(qtbot: QtBot) -> None:
    """
    Kiểm tra hàm setChecked thay đổi trạng thái của switch chính xác.
    """
    switch = ToggleSwitch()
    qtbot.addWidget(switch)

    # Đặt Checked thành True
    switch.setChecked(True)
    assert switch.isChecked() is True

    # Đặt Checked thành False
    switch.setChecked(False)
    assert switch.isChecked() is False


def test_toggle_switch_toggle_method(qtbot: QtBot) -> None:
    """
    Kiểm tra phương thức toggle() đảo ngược trạng thái Checked và phát ra Signal toggled.
    """
    switch = ToggleSwitch(checked=False)
    qtbot.addWidget(switch)

    # Sử dụng bộ lắng nghe signal của pytest-qt
    with qtbot.waitSignal(switch.toggled, timeout=1000) as blocker:
        switch.toggle()

    # Xác nhận signal toggled(True) đã được phát ra
    assert blocker.args == [True]
    assert switch.isChecked() is True

    # Toggle lại lần nữa
    with qtbot.waitSignal(switch.toggled, timeout=1000) as blocker:
        switch.toggle()

    assert blocker.args == [False]
    assert switch.isChecked() is False


def test_toggle_switch_mouse_click(qtbot: QtBot) -> None:
    """
    Kiểm tra giả lập click chuột trái lên switch sẽ thay đổi trạng thái và phát ra signal.
    """
    switch = ToggleSwitch(checked=False)
    qtbot.addWidget(switch)

    with qtbot.waitSignal(switch.toggled, timeout=1000) as blocker:
        # Giả lập click chuột trái vào widget
        qtbot.mouseClick(switch, Qt.MouseButton.LeftButton)

    assert blocker.args == [True]
    assert switch.isChecked() is True


def test_toggle_switch_hover_events(qtbot: QtBot) -> None:
    """
    Kiểm tra các sự kiện rê chuột vào (enter) và ra khỏi (leave) switch cập nhật hovered state.
    """
    switch = ToggleSwitch()
    qtbot.addWidget(switch)
    assert switch._hovered is False

    # Giả lập sự kiện rê chuột vào widget
    switch.enterEvent(None)
    assert switch._hovered is True

    switch.leaveEvent(None)
    assert switch._hovered is False


def test_toggle_switch_size_hint(qtbot: QtBot) -> None:
    """
    Kiểm tra sizeHint trả về kích thước mong muốn của toggle switch.
    """
    switch = ToggleSwitch()
    qtbot.addWidget(switch)
    size = switch.sizeHint()
    assert size.width() == 44
    assert size.height() == 22
