from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QFrame,
)
from PySide6.QtCore import Qt, QSize
from presentation.config.theme import ThemeColors, ThemeFonts
from presentation.components.qt_utils import create_colored_icon
from domain.ports.registry import DomainRegistry


class LicenseActivationDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Activate Synapse Desktop")
        self.setMinimumSize(520, 320)
        self.resize(520, 320)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setStyleSheet(
            f"background-color: {ThemeColors.BG_SURFACE}; color: {ThemeColors.TEXT_PRIMARY};"
        )
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header Info Row
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        self.icon_label = QLabel()
        from shared.utils.path_utils import get_assets_dir

        assets_dir = get_assets_dir()

        icon_path = assets_dir / "gem.svg"
        key_icon = create_colored_icon(str(icon_path), ThemeColors.WARNING)
        self.icon_label.setPixmap(key_icon.pixmap(QSize(28, 28)))
        header_layout.addWidget(self.icon_label)

        title_label = QLabel("License Activation Required")
        title_label.setStyleSheet(
            f"font-size: {ThemeFonts.SIZE_SUBTITLE}px; "
            f"font-weight: 700; "
            f"color: {ThemeColors.TEXT_PRIMARY};"
        )
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Desc
        desc_label = QLabel(
            "Synapse Desktop requires a valid Gumroad license key to run.\n"
            "Please paste your license key below:"
        )
        desc_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_SECONDARY}; font-size: {ThemeFonts.SIZE_BODY}px;"
        )
        layout.addWidget(desc_label)

        # Purchase link
        self.buy_link = QLabel(
            f'<a href="https://gumroad.com" style="color: {ThemeColors.PRIMARY}; text-decoration: none;">'
            "Don't have a license key? Purchase one here</a>"
        )
        self.buy_link.setOpenExternalLinks(True)
        self.buy_link.setStyleSheet(
            f"font-size: {ThemeFonts.SIZE_BODY}px; margin-bottom: 4px;"
        )
        layout.addWidget(self.buy_link)

        # Text input (QPlainTextEdit for long keys)
        self.key_input = QPlainTextEdit()
        self.key_input.setPlaceholderText("A1B2C3D4-E5F60718-9ABCDEF0-1234ABCD")
        self.key_input.setStyleSheet(
            f"""
            QPlainTextEdit {{
                background-color: {ThemeColors.BG_PAGE};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 4px;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FAMILY_MONO};
                font-size: {ThemeFonts.SIZE_CAPTION}px;
                padding: 8px;
            }}
            QPlainTextEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
            """
        )
        layout.addWidget(self.key_input)

        # Error display label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(
            f"color: {ThemeColors.ERROR}; font-size: {ThemeFonts.SIZE_CAPTION}px; font-weight: 500;"
        )
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {ThemeColors.BORDER}; max-height: 1px;")
        layout.addWidget(sep)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Exit App")
        self.cancel_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 4px;
                color: {ThemeColors.TEXT_SECONDARY};
                padding: 6px 16px;
                font-size: {ThemeFonts.SIZE_BODY}px;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_ELEVATED};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            """
        )
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.activate_btn = QPushButton("Activate")
        self.activate_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                border: none;
                border-radius: 4px;
                color: #FFFFFF;
                padding: 6px 20px;
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
        self.activate_btn.clicked.connect(self._on_activate_clicked)
        btn_layout.addWidget(self.activate_btn)

        layout.addLayout(btn_layout)

    def _on_activate_clicked(self) -> None:
        key = self.key_input.toPlainText().strip()
        if not key:
            self.error_label.setText("License key cannot be empty")
            self.error_label.setVisible(True)
            return

        self.error_label.setVisible(False)
        self.key_input.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.activate_btn.setEnabled(False)
        self.activate_btn.setText("Activating...")

        from presentation.utils.qt_utils import schedule_background

        def do_verify():
            service = DomainRegistry.license_service()
            return service.verify_license_key(key)

        def on_finished():
            self.key_input.setEnabled(True)
            self.cancel_btn.setEnabled(True)
            self.activate_btn.setEnabled(True)
            self.activate_btn.setText("Activate")

        def on_result(info):
            if info.is_valid:
                try:
                    DomainRegistry.settings_service().update_setting("license_key", key)
                    self.accept()
                except Exception as e:
                    self.error_label.setText(f"Failed to save settings: {e}")
                    self.error_label.setVisible(True)
            else:
                self.error_label.setText(info.error_message or "Invalid license key")
                self.error_label.setVisible(True)

        def on_error(err_str):
            self.error_label.setText(f"Verification process failed: {err_str}")
            self.error_label.setVisible(True)

        schedule_background(
            do_verify,
            on_result=on_result,
            on_error=on_error,
            on_finished=on_finished,
        )
