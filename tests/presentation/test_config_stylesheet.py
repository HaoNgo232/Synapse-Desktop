"""
Tests cho stylesheet.py và theme_qss.py.
"""

import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QPushButton

from presentation.config.stylesheet import (
    apply_cursor_pointer,
    setup_button,
    get_global_stylesheet,
)


def test_apply_cursor_pointer(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    apply_cursor_pointer(widget)
    assert widget.cursor().shape() == Qt.CursorShape.PointingHandCursor


def test_setup_button(qtbot):
    btn = QPushButton("Click me")
    qtbot.addWidget(btn)
    setup_button(btn, "Click this button")
    assert btn.cursor().shape() == Qt.CursorShape.PointingHandCursor
    assert btn.toolTip() == "Click this button"

    btn2 = QPushButton("No tooltip")
    qtbot.addWidget(btn2)
    setup_button(btn2)
    assert btn2.cursor().shape() == Qt.CursorShape.PointingHandCursor
    assert btn2.toolTip() == ""


def test_get_global_stylesheet():
    qss = get_global_stylesheet()
    assert isinstance(qss, str)
    assert "QMainWindow" in qss
    assert "QPushButton" in qss


def test_theme_qss_meipass_branch():
    # Test compilation of theme_qss under PyInstaller MEIPASS environment
    # Since these are module-level variables evaluated on import,
    # we need to unload the module and reload it with sys._MEIPASS patched.

    # 1. Unload the module from sys.modules
    modules_to_unload = [
        "presentation.config.theme_qss",
        "presentation.config.stylesheet",
    ]
    saved_modules = {}
    for m in modules_to_unload:
        if m in sys.modules:
            saved_modules[m] = sys.modules[m]
            del sys.modules[m]

    # 2. Patch sys._MEIPASS and sys.frozen
    sys._MEIPASS = "/mock/meipass"
    orig_frozen = getattr(sys, "frozen", None)
    sys.frozen = True

    try:
        # 3. Import again
        import presentation.config.theme_qss as theme_qss

        # Verify the assets directory points to MEIPASS
        assert "/mock/meipass" in theme_qss._ARROW_RIGHT

        qss = theme_qss.generate_app_stylesheet()
        assert isinstance(qss, str)
        assert "arrow-right.svg" in qss
    finally:
        # Clean up
        if hasattr(sys, "_MEIPASS"):
            del sys._MEIPASS
        if orig_frozen is not None:
            sys.frozen = orig_frozen
        elif hasattr(sys, "frozen"):
            del sys.frozen

        # Restore original modules
        for m in modules_to_unload:
            if m in saved_modules:
                sys.modules[m] = saved_modules[m]
            elif m in sys.modules:
                del sys.modules[m]
