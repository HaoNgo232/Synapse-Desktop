"""
Toggle Switch Widget — Custom animated toggle for on/off settings.

Style:
- Width 44px, height 22px, fully rounded
- OFF: bg #3E3E5E, knob left
- ON: bg #7C6FFF, knob right
- Smooth 150ms animation
"""

from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, Property, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QBrush


class ToggleSwitch(QWidget):
    """Animated toggle switch widget."""

    toggled = Signal(bool)

    # Colors
    _BG_OFF = QColor("#3E3E5E")
    _BG_ON = QColor("#7C6FFF")
    _KNOB_COLOR = QColor("#E0E0F0")
    _HOVER_BORDER = QColor("#5E5EFF")

    # Dimensions
    WIDTH = 44
    HEIGHT = 22
    KNOB_MARGIN = 2
    KNOB_SIZE = HEIGHT - KNOB_MARGIN * 2  # 18px

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._knob_x = float(self._knob_end() if checked else self.KNOB_MARGIN)
        self._hovered = False

        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Animation for knob position
        self._animation = QPropertyAnimation(self, b"knob_position", self)
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

    def _knob_end(self) -> float:
        return float(self.WIDTH - self.KNOB_SIZE - self.KNOB_MARGIN)

    # --- Qt Property for animation ---
    def _get_knob_position(self) -> float:
        return self._knob_x

    def _set_knob_position(self, val: float) -> None:
        self._knob_x = val
        self.update()

    knob_position = Property(float, _get_knob_position, _set_knob_position)

    # --- Public API ---
    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        if self._checked == checked:
            return
        self._checked = checked
        target = self._knob_end() if checked else float(self.KNOB_MARGIN)
        self._animation.stop()
        self._animation.setStartValue(self._knob_x)
        self._animation.setEndValue(target)
        self._animation.start()

    def toggle(self) -> None:
        self.setChecked(not self._checked)
        self.toggled.emit(self._checked)

    # --- Events ---
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(self.WIDTH, self.HEIGHT)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        radius = h / 2.0

        # Background track
        progress = (self._knob_x - self.KNOB_MARGIN) / (
            self._knob_end() - self.KNOB_MARGIN
        )
        progress = max(0.0, min(1.0, progress))

        r = int(
            self._BG_OFF.red() + (self._BG_ON.red() - self._BG_OFF.red()) * progress
        )
        g = int(
            self._BG_OFF.green()
            + (self._BG_ON.green() - self._BG_OFF.green()) * progress
        )
        b = int(
            self._BG_OFF.blue() + (self._BG_ON.blue() - self._BG_OFF.blue()) * progress
        )
        bg_color = QColor(r, g, b)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bg_color))
        p.drawRoundedRect(0, 0, w, h, radius, radius)

        # Hover border
        if self._hovered:
            p.setPen(QPen(self._HOVER_BORDER, 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(0, 0, w, h, radius, radius)

        # Knob
        knob_y = float(self.KNOB_MARGIN)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(self._KNOB_COLOR))
        p.drawEllipse(int(self._knob_x), int(knob_y), self.KNOB_SIZE, self.KNOB_SIZE)

        p.end()
