"""
TopBar Component - Thanh tiêu đề hợp nhất của ứng dụng.

Chứa: Branding, Breadcrumb đường dẫn, Memory monitor, và các action chính.
"""

import sys
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QFrame,
    QSizePolicy,
    QMenu,
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QIcon

from presentation.config.theme import ThemeColors, ThemeFonts
from infrastructure.adapters.memory_monitor import MemoryStats, format_memory_display


class TopBar(QFrame):
    """
    Unified Top Bar (48px height).
    [App Icon + "Synapse"] — [Breadcrumb path] — [RAM] — [Recent ▾] [Open Folder]
    """

    # Signals để giao tiếp với MainWindow/Controller
    open_folder_requested = Signal()
    recent_folder_selected = Signal(str)
    clear_memory_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet(
            f"background-color: {ThemeColors.BG_SURFACE};"
            f"border-bottom: 1px solid {ThemeColors.BORDER};"
        )
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # ── App branding ──
        app_icon = QLabel("💎")
        app_icon.setStyleSheet("font-size: 18px;")
        app_icon.setToolTip("Synapse Desktop")
        layout.addWidget(app_icon)

        app_title = QLabel("Synapse")
        app_title.setStyleSheet(
            f"font-size: {ThemeFonts.SIZE_SUBTITLE}px; "
            f"font-weight: 700; "
            f"color: {ThemeColors.TEXT_PRIMARY}; "
            f"letter-spacing: 0.5px;"
        )
        layout.addWidget(app_title)

        # ── Separator ──
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(24)
        sep.setStyleSheet(f"background-color: {ThemeColors.BORDER}; max-width: 1px;")
        layout.addWidget(sep)

        # ── Folder breadcrumb ──
        folder_icon = QLabel("📁")
        folder_icon.setStyleSheet("font-size: 14px;")
        layout.addWidget(folder_icon)

        self._folder_path_label = QLabel("No folder selected")
        self._folder_path_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_SECONDARY}; "
            f"font-family: {ThemeFonts.FAMILY_MONO}; "
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
        )
        self._folder_path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._folder_path_label.setToolTip("Current workspace folder")
        layout.addWidget(self._folder_path_label, stretch=1)

        # ── Memory indicator ──
        self._memory_label = QLabel("🧠 --")
        self._memory_label.setStyleSheet(
            f"font-size: {ThemeFonts.SIZE_CAPTION}px; "
            f"font-family: {ThemeFonts.FAMILY_MONO}; "
            f"color: {ThemeColors.TEXT_MUTED};"
        )
        self._memory_label.setToolTip("Memory usage | Token cache | Files loaded")
        layout.addWidget(self._memory_label)

        # ── Clear memory button ──
        clear_btn = QToolButton()
        clear_btn.setText("🧹")
        clear_btn.setToolTip("Clear cache & free memory")
        clear_btn.setStyleSheet(
            f"QToolButton {{ font-size: 14px; padding: 4px 6px; border-radius: 4px; border: none; }}"
            f"QToolButton:hover {{ background-color: {ThemeColors.BG_ELEVATED}; }}"
        )
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self.clear_memory_requested.emit)
        layout.addWidget(clear_btn)

        # ── Recent folders button ──
        self._recent_btn = QToolButton()
        self._recent_btn.setToolTip("Recent folders (Ctrl+R)")
        self._recent_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._recent_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Load icon assets
        icon_path = self._get_asset_path("clock-arrow-down.svg")
        if icon_path:
            self._recent_btn.setIcon(QIcon(str(icon_path)))
        else:
            self._recent_btn.setText("🕒")
            
        self._recent_btn.setIconSize(QSize(18, 18))
        self._recent_btn.setStyleSheet(
            f"""
            QToolButton {{
                background-color: transparent;
                color: {ThemeColors.TEXT_SECONDARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: {ThemeFonts.SIZE_BODY // 2}px;
                padding: 6px 10px;
                font-size: {ThemeFonts.SIZE_BODY}px;
                font-weight: 500;
            }}
            QToolButton:hover {{
                background-color: {ThemeColors.BG_ELEVATED};
                color: {ThemeColors.TEXT_PRIMARY};
                border-color: {ThemeColors.BORDER_LIGHT};
            }}
            QToolButton::menu-indicator {{ width: 0px; }}
        """
        )
        self._recent_menu = QMenu(self._recent_btn)
        self._recent_btn.setMenu(self._recent_menu)
        layout.addWidget(self._recent_btn)

        # ── Open Folder button ──
        open_btn = QPushButton("📁 Open Folder")
        open_btn.setToolTip("Open workspace folder (Ctrl+O)")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 6px 18px;
                font-size: {ThemeFonts.SIZE_BODY}px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {ThemeColors.PRIMARY_PRESSED};
            }}
        """
        )
        open_btn.clicked.connect(self.open_folder_requested.emit)
        layout.addWidget(open_btn)

    def set_workspace_path(self, path: Optional[Path]) -> None:
        """Cập nhật hiển thị đường dẫn workspace."""
        if path:
            self._folder_path_label.setText(str(path))
            self._folder_path_label.setStyleSheet(
                f"color: {ThemeColors.TEXT_PRIMARY}; "
                f"font-family: {ThemeFonts.FAMILY_MONO}; "
                f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
            )
        else:
            self._folder_path_label.setText("No folder selected")
            self._folder_path_label.setStyleSheet(
                f"color: {ThemeColors.TEXT_SECONDARY}; "
                f"font-family: {ThemeFonts.FAMILY_MONO}; "
                f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
            )

    def update_memory_stats(self, stats: MemoryStats) -> None:
        """Cập nhật hiển thị thông số bộ nhớ."""
        display_text = f"🧠 {format_memory_display(stats)}"
        self._memory_label.setText(display_text)

        if stats.warning and "Critical" in stats.warning:
            color = ThemeColors.ERROR
        elif stats.warning:
            color = ThemeColors.WARNING
        else:
            color = ThemeColors.TEXT_MUTED

        self._memory_label.setStyleSheet(
            f"font-size: {ThemeFonts.SIZE_CAPTION}px; "
            f"font-family: {ThemeFonts.FAMILY_MONO}; "
            f"color: {color};"
        )

    def refresh_recent_menu(self, recent_folders: List[str]) -> None:
        """Cập nhật danh sách thư mục gần đây."""
        self._recent_menu.clear()
        if not recent_folders:
            action = self._recent_menu.addAction("No recent folders")
            action.setEnabled(False)
            return

        from infrastructure.persistence.recent_folders import get_folder_display_name
        
        for folder_path in recent_folders:
            display_name = get_folder_display_name(folder_path)
            action = self._recent_menu.addAction(f"📁 {display_name}")
            action.triggered.connect(
                lambda checked=False, p=folder_path: self.recent_folder_selected.emit(p)
            )

    def _get_asset_path(self, asset_name: str) -> Optional[Path]:
        """Lấy đường dẫn asset, xử lý trường hợp chạy từ source/EXE."""
        if hasattr(sys, "_MEIPASS"):
            path = Path(sys._MEIPASS) / "assets" / asset_name
        else:
            # presentation/components/app_layout/top_bar.py -> presentation/assets/
            path = Path(__file__).parent.parent.parent / "assets" / asset_name
        
        return path if path.exists() else None
