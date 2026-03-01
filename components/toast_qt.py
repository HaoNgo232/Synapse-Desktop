"""
Global Toast Notification System — Synapse Desktop

Overlay top-center toast notifications with glassmorphism,
background elevation, and slide + fade animation.

Usage:
    from components.toast_qt import init_toast_manager, show_toast, ToastType

    # Initialize once in MainWindow.__init__
    init_toast_manager(main_window)

    # Call from anywhere in the app
    show_toast(ToastType.SUCCESS, "Copied!", "12,345 tokens")
    show_toast(ToastType.ERROR, "No files selected")
"""

from enum import Enum
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QToolButton,
    QGraphicsOpacityEffect,
)
from PySide6.QtCore import (
    Qt,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    Slot,
    Signal,
)

from core.theme import ThemeColors, ThemeRadius


# ── Toast Type Enum ──────────────────────────────────────────────


class ToastType(Enum):
    """Toast notification types with corresponding accent colors."""

    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ── Toast Config ─────────────────────────────────────────────────

_TOAST_CONFIG = {
    ToastType.SUCCESS: {
        "accent": ThemeColors.SUCCESS,  # #4ADE80
        "icon": "\u2713",  # Checkmark
        "duration": 5000,  # 5 giay
    },
    ToastType.ERROR: {
        "accent": ThemeColors.ERROR,  # #F87171
        "icon": "\u26a0",  # Warning triangle
        "duration": 8000,  # 8 giay (lau hon de user doc)
    },
    ToastType.WARNING: {
        "accent": ThemeColors.WARNING,  # #FBBF24
        "icon": "\u26a0",  # Warning triangle
        "duration": 6000,
    },
    ToastType.INFO: {
        "accent": ThemeColors.INFO,  # #60A5FA
        "icon": "\u2139",  # Info circle
        "duration": 5000,
    },
}

# ── Kich thuoc va khoang cach ────────────────────────────────────

_TOAST_WIDTH = 360
_TOAST_MARGIN = 16  # Khoang cach toi canh cua so
_TOAST_GAP = 8  # Khoang cach giua cac toast
_MAX_VISIBLE = 5  # So luong toast toi da dong thoi
_ANIMATION_DURATION = 300  # ms cho slide + fade


# ── ToastNotification Widget ────────────────────────────────────


class ToastNotification(QFrame):
    """
    Single toast notification widget.

    Contains: accent strip (4px left), icon, title/message, close button.
    Features shadow, fade-in/slide animation, and auto-dismiss timer.
    """

    # Signal to notify ToastManager when toast is closed
    closed = Signal(object)  # emit self

    def __init__(
        self,
        parent: QWidget,
        toast_type: ToastType,
        message: str,
        title: Optional[str] = None,
        tooltip: Optional[str] = None,
        duration: Optional[int] = None,
    ) -> None:
        super().__init__(parent)

        self._toast_type = toast_type
        self._config = _TOAST_CONFIG[toast_type]
        self._duration = duration or self._config["duration"]

        # Flag de tranh dismiss nhieu lan
        self._is_closing = False

        # Reference cho reposition animation (khai bao truoc de tranh lint)
        self._reposition_anim: Optional[QPropertyAnimation] = None

        # Cau hinh widget
        self.setFixedWidth(_TOAST_WIDTH)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.ArrowCursor)

        if tooltip:
            self.setToolTip(tooltip)

        # Xay dung UI
        self._build_ui(message, title)

        # Opacity effect cho fade animation (khong co shadow de tranh QPainter conflict)
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        # Auto-dismiss timer
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._start_close_animation)
        self._dismiss_timer.start(int(self._duration))

    def _build_ui(self, message: str, title: Optional[str]) -> None:
        """Xay dung layout: [accent strip] [icon] [title/message] [close btn]."""
        # Main container layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Accent strip (4px) — ve truc tiep trong paintEvent

        # Content area
        content_frame = QFrame()
        content_frame.setStyleSheet(
            f"""
            QFrame {{
                background-color: {ThemeColors.BG_ELEVATED};
                border: 1px solid {ThemeColors.BORDER_LIGHT};
                border-left: 4px solid {self._config["accent"]};
                border-radius: {ThemeRadius.LG}px;
            }}
        """
        )
        content_layout = QHBoxLayout(content_frame)
        content_layout.setContentsMargins(12, 10, 8, 10)
        content_layout.setSpacing(10)

        # Icon
        icon_label = QLabel(str(self._config["icon"]))
        icon_label.setFixedSize(28, 28)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(
            f"""
            QLabel {{
                font-size: 16px;
                color: {self._config["accent"]};
                background: transparent;
                border: none;
            }}
        """
        )
        content_layout.addWidget(icon_label)

        # Text column (title + message)
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        if title:
            title_label = QLabel(title)
            title_label.setWordWrap(True)
            title_label.setStyleSheet(
                f"""
                QLabel {{
                    font-size: 13px;
                    font-weight: 700;
                    color: {ThemeColors.TEXT_PRIMARY};
                    background: transparent;
                    border: none;
                }}
            """
            )
            text_layout.addWidget(title_label)

        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet(
            f"""
            QLabel {{
                font-size: 12px;
                font-weight: {"500" if title else "600"};
                color: {ThemeColors.TEXT_SECONDARY if title else ThemeColors.TEXT_PRIMARY};
                background: transparent;
                border: none;
            }}
        """
        )
        text_layout.addWidget(msg_label)

        content_layout.addLayout(text_layout, stretch=1)

        # Close button
        close_btn = QToolButton()
        close_btn.setText("\u2715")  # X character
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"""
            QToolButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
                color: {ThemeColors.TEXT_MUTED};
                font-size: 12px;
                font-weight: 700;
            }}
            QToolButton:hover {{
                background: {ThemeColors.BG_HOVER};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
        """
        )
        close_btn.clicked.connect(self._start_close_animation)
        content_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignTop)

        main_layout.addWidget(content_frame)

    # ── Animation ────────────────────────────────────────────────

    def start_show_animation(self) -> None:
        """Bat dau animation hien thi: fade in + slide up."""
        # Fade in qua QGraphicsOpacityEffect
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(_ANIMATION_DURATION)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Slide down (dich xuong 20px tu vi tri hien tai)
        start_pos = self.pos() - QPoint(0, 20)
        end_pos = self.pos()

        self._slide_anim = QPropertyAnimation(self, b"pos")
        self._slide_anim.setDuration(_ANIMATION_DURATION)
        self._slide_anim.setStartValue(start_pos)
        self._slide_anim.setEndValue(end_pos)
        self._slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Chay dong thoi
        self._show_group = QParallelAnimationGroup(self)
        self._show_group.addAnimation(self._fade_anim)
        self._show_group.addAnimation(self._slide_anim)
        self._show_group.start()

    @Slot()
    def _start_close_animation(self) -> None:
        """Bat dau animation dong: fade out + slide down."""
        if self._is_closing:
            return
        self._is_closing = True

        # Dung timer
        self._dismiss_timer.stop()

        # Fade out qua QGraphicsOpacityEffect
        fade = QPropertyAnimation(self._opacity_effect, b"opacity")
        fade.setDuration(200)
        fade.setStartValue(self._opacity_effect.opacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.Type.InCubic)

        # Slide up
        slide = QPropertyAnimation(self, b"pos")
        slide.setDuration(200)
        slide.setStartValue(self.pos())
        slide.setEndValue(self.pos() - QPoint(0, 10))
        slide.setEasingCurve(QEasingCurve.Type.InCubic)

        self._close_group = QParallelAnimationGroup(self)
        self._close_group.addAnimation(fade)
        self._close_group.addAnimation(slide)
        self._close_group.finished.connect(self._on_close_finished)
        self._close_group.start()

    @Slot()
    def _on_close_finished(self) -> None:
        """Xu ly khi animation dong hoan thanh."""
        self.closed.emit(self)
        self.deleteLater()


# ── ToastManager ─────────────────────────────────────────────────


class ToastManager:
    """
    Manage display and stacking of toast notifications.

    Singleton pattern — only one instance, attached to MainWindow.
    Toasts are displayed top-center of the parent widget,
    stacking downward when multiple toasts are visible.
    """

    _instance: Optional["ToastManager"] = None

    def __init__(self, parent: QWidget) -> None:
        """
        Initialize ToastManager with a parent widget (typically MainWindow).

        Args:
            parent: Parent widget — toasts are rendered as overlays on this widget.
        """
        self._parent = parent
        self._active_toasts: List[ToastNotification] = []

    @classmethod
    def instance(cls) -> Optional["ToastManager"]:
        """Lay singleton instance."""
        return cls._instance

    @classmethod
    def initialize(cls, parent: QWidget) -> "ToastManager":
        """
        Initialize the singleton instance. Call once in MainWindow.__init__.

        Args:
            parent: MainWindow instance.

        Returns:
            ToastManager instance.
        """
        cls._instance = cls(parent)
        return cls._instance

    def show(
        self,
        toast_type: ToastType,
        message: str,
        title: Optional[str] = None,
        tooltip: Optional[str] = None,
        duration: Optional[int] = None,
    ) -> ToastNotification:
        """
        Hien thi mot toast notification moi.

        Args:
            toast_type: Loai toast (SUCCESS, ERROR, WARNING, INFO).
            message: Noi dung thong bao chinh.
            title: Tieu de (optional, hien thi phia tren message).
            tooltip: Tooltip chi tiet (optional, hien khi hover).
            duration: Thoi gian hien thi (ms). None = dung default cua toast_type.

        Returns:
            ToastNotification widget da tao.
        """
        # Gioi han so luong toast hien thi.
        # Force-remove excess toasts synchronously to prevent accumulation
        # when show() is called rapidly (e.g., user clicking copy buttons fast).
        while len(self._active_toasts) >= _MAX_VISIBLE:
            oldest = self._active_toasts[0]
            oldest._dismiss_timer.stop()
            oldest._is_closing = True
            oldest.hide()
            self._active_toasts.remove(oldest)
            oldest.deleteLater()

        # Tao toast moi
        toast = ToastNotification(
            parent=self._parent,
            toast_type=toast_type,
            message=message,
            title=title,
            tooltip=tooltip,
            duration=duration,
        )
        toast.closed.connect(self._on_toast_closed)
        self._active_toasts.append(toast)

        # Tinh vi tri va hien thi
        self._reposition_toasts()
        toast.show()
        toast.start_show_animation()

        return toast

    @Slot(object)
    def _on_toast_closed(self, toast: ToastNotification) -> None:
        """Xu ly khi mot toast bi dong."""
        if toast in self._active_toasts:
            self._active_toasts.remove(toast)
            # Re-position cac toast con lai (animate len xuong)
            self._animate_reposition()

    def _reposition_toasts(self) -> None:
        """
        Tinh toan va dat vi tri cho tat ca toast hien tai.

        Toast moi nhat o tren cung (top-center), cac toast cu hon
        duoc day xuong duoi.
        """
        if not self._parent:
            return

        parent_rect = self._parent.rect()
        x = (parent_rect.width() - _TOAST_WIDTH) // 2
        y_top = _TOAST_MARGIN

        # Dat vi tri tu tren xuong duoi (toast moi nhat o tren cung)
        for i, toast in enumerate(reversed(self._active_toasts)):
            toast.adjustSize()
            toast_height = toast.sizeHint().height()
            toast.move(x, y_top)
            y_top += toast_height + _TOAST_GAP

    def _animate_reposition(self) -> None:
        """Animate cac toast di chuyen khi mot toast bi dong."""
        if not self._parent:
            return

        parent_rect = self._parent.rect()
        x = (parent_rect.width() - _TOAST_WIDTH) // 2
        y_top = _TOAST_MARGIN

        for i, toast in enumerate(reversed(self._active_toasts)):
            toast.adjustSize()
            toast_height = toast.sizeHint().height()
            target_y = y_top

            if toast.pos().y() != target_y:
                # Animate toast di chuyen den vi tri moi
                anim = QPropertyAnimation(toast, b"pos")
                anim.setDuration(200)
                anim.setStartValue(toast.pos())
                anim.setEndValue(QPoint(x, target_y))
                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                # Luu reference de tranh bi GC
                toast._reposition_anim = anim
                anim.start()

            y_top += toast_height + _TOAST_GAP

    def reposition_on_resize(self) -> None:
        """Goi khi parent widget resize de cap nhat vi tri toast."""
        self._reposition_toasts()

    def dismiss_all(self, force: bool = False) -> None:
        """Dong tat ca toast dang hien thi.

        Args:
            force: If True, skip animation and remove immediately.
                   Use when new toasts will be created right after
                   to prevent animation conflicts and accumulation.
        """
        if force:
            # Force-remove all toasts synchronously — no animation.
            # This prevents animation conflicts when user clicks rapidly.
            for toast in list(self._active_toasts):
                toast._dismiss_timer.stop()
                toast._is_closing = True
                toast.hide()
                toast.deleteLater()
            self._active_toasts.clear()
        else:
            for toast in list(self._active_toasts):
                toast._start_close_animation()


# ── Module-Level Convenience API ─────────────────────────────────


def init_toast_manager(parent: QWidget) -> ToastManager:
    """
    Initialize the global ToastManager. Call once in MainWindow.__init__.

    Args:
        parent: MainWindow instance.

    Returns:
        ToastManager instance.
    """
    return ToastManager.initialize(parent)


def show_toast(
    toast_type: ToastType,
    message: str,
    title: Optional[str] = None,
    tooltip: Optional[str] = None,
    duration: Optional[int] = None,
) -> Optional[ToastNotification]:
    """
    Show a toast notification. Can be called from anywhere in the app.

    Args:
        toast_type: Toast type (SUCCESS, ERROR, WARNING, INFO).
        message: Main notification content.
        title: Title text (optional, displayed above message).
        tooltip: Detailed tooltip (optional, shown on hover).
        duration: Display duration in ms (optional, uses type default).

    Returns:
        ToastNotification widget, or None if manager is not initialized.
    """
    manager = ToastManager.instance()
    if manager is None:
        # Fallback: log warning neu manager chua duoc init
        from core.logging_config import log_warning

        log_warning(
            "[Toast] ToastManager not initialized. Call init_toast_manager() first."
        )
        return None
    return manager.show(toast_type, message, title, tooltip, duration)


def toast_success(
    message: str, title: Optional[str] = None, **kwargs
) -> Optional[ToastNotification]:
    """Shortcut cho show_toast(ToastType.SUCCESS, ...)."""
    return show_toast(ToastType.SUCCESS, message, title, **kwargs)


def toast_error(
    message: str, title: Optional[str] = None, **kwargs
) -> Optional[ToastNotification]:
    """Shortcut cho show_toast(ToastType.ERROR, ...)."""
    return show_toast(ToastType.ERROR, message, title, **kwargs)


def toast_warning(
    message: str, title: Optional[str] = None, **kwargs
) -> Optional[ToastNotification]:
    """Shortcut cho show_toast(ToastType.WARNING, ...)."""
    return show_toast(ToastType.WARNING, message, title, **kwargs)


def toast_info(
    message: str, title: Optional[str] = None, **kwargs
) -> Optional[ToastNotification]:
    """Shortcut cho show_toast(ToastType.INFO, ...)."""
    return show_toast(ToastType.INFO, message, title, **kwargs)
