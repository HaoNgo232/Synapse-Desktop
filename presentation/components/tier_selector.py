"""
Tier Selector Component - Một segmented control nhỏ gọn để chuyển đổi giữa Lite và Pro.

Tuân thủ SOLID:
- Single Responsibility: Chỉ đảm nhận việc hiển thị và emit signal khi thay đổi tier.
- Interface Segregation: Cung cấp API đơn giản (get_tier, set_tier, tier_changed).
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, Signal
from presentation.config.theme import ThemeColors


class TierSelector(QWidget):
    """
    Component chọn tier (Lite/Pro) với thiết kế segmented control hiện đại.
    """

    # Signal phát ra khi tier thay đổi (str: 'lite' hoặc 'pro')
    tier_changed = Signal(str)

    def __init__(self, initial_tier: str = "lite", parent=None):
        super().__init__(parent)
        self._current_tier = (
            initial_tier.lower() if initial_tier in ["lite", "pro"] else "lite"
        )
        self._init_ui()

    def _init_ui(self):
        # Layout ngang, không có khoảng cách giữa các nút để tạo hiệu ứng segmented
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Style chung và trạng thái active/inactive
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.BG_ELEVATED};
                color: {ThemeColors.TEXT_SECONDARY};
                border: 1px solid {ThemeColors.BORDER};
                padding: 4px 10px;
                font-size: 10px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_HOVER};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QPushButton[active="true"] {{
                background-color: {ThemeColors.PRIMARY};
                color: white;
                border-color: {ThemeColors.PRIMARY};
            }}
            #lite_btn {{
                border-top-left-radius: 6px;
                border-bottom-left-radius: 6px;
                border-right: none;
            }}
            #pro_btn {{
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }}
        """)

        self._lite_btn = QPushButton("LITE")
        self._lite_btn.setObjectName("lite_btn")
        self._lite_btn.setFixedWidth(40)
        self._lite_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._pro_btn = QPushButton("PRO")
        self._pro_btn.setObjectName("pro_btn")
        self._pro_btn.setFixedWidth(40)
        self._pro_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        layout.addWidget(self._lite_btn)
        layout.addWidget(self._pro_btn)

        # Kết nối sự kiện
        self._lite_btn.clicked.connect(lambda: self.set_tier("lite", emit=True))
        self._pro_btn.clicked.connect(lambda: self.set_tier("pro", emit=True))

        # Cập nhật trạng thái hiển thị ban đầu
        self._update_button_states()

    def _update_button_states(self):
        """Cập nhật trạng thái 'active' để QSS tự động đổi màu."""
        is_lite = self._current_tier == "lite"

        # Sử dụng Dynamic Property của Qt để thay đổi style
        self._lite_btn.setProperty("active", "true" if is_lite else "false")
        self._pro_btn.setProperty("active", "false" if is_lite else "true")

        # Ép Qt nạp lại style khi property thay đổi
        self._lite_btn.style().unpolish(self._lite_btn)
        self._lite_btn.style().polish(self._lite_btn)
        self._pro_btn.style().unpolish(self._pro_btn)
        self._pro_btn.style().polish(self._pro_btn)

    def set_tier(self, tier: str, emit: bool = False):
        """Thiết lập tier hiện tại và cập nhật UI."""
        tier = tier.lower()
        if tier not in ["lite", "pro"] or tier == self._current_tier:
            # Vẫn cần update UI nếu nhấn lại nút cũ để tránh bị uncheck (vì checkable)
            self._update_button_states()
            return

        self._current_tier = tier
        self._update_button_states()

        if emit:
            self.tier_changed.emit(tier)

    def get_tier(self) -> str:
        """Lấy tier đang được chọn."""
        return self._current_tier
