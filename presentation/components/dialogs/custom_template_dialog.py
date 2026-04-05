"""
Custom Template Dialog Component.

Cho phep nguoi dung tao va luu cac custom markdown templates vao thu muc config.
"""

import os
import re

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QMessageBox,
)
from PySide6.QtCore import Qt

from presentation.config.theme import ThemeColors
from domain.prompt.template_manager import CUSTOM_TEMPLATES_DIR


class CustomTemplateDialog(QDialog):
    """Dialog tao moi Custom Template."""

    def __init__(self, parent=None, template_id: str = None):
        super().__init__(parent)
        self.template_id = template_id
        if self.template_id:
            self.setWindowTitle("Edit Custom Template")
        else:
            self.setWindowTitle("Create Custom Template")
        self.setMinimumWidth(900)
        self.setMinimumHeight(700)
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {ThemeColors.BG_SURFACE};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QLabel {{
                color: {ThemeColors.TEXT_PRIMARY};
                font-weight: 500;
            }}
            QLineEdit, QTextEdit {{
                background-color: {ThemeColors.BG_ELEVATED};
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 4px;
                padding: 6px;
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
            QPushButton {{
                background-color: {ThemeColors.BG_ELEVATED};
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_HOVER};
            }}
            QPushButton#saveBtn {{
                background-color: {ThemeColors.PRIMARY};
                color: white;
                border: none;
            }}
            QPushButton#saveBtn:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            """
        )
        self._build_ui()
        if self.template_id:
            self._load_existing_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Name
        name_layout = QVBoxLayout()
        name_layout.setSpacing(4)
        name_layout.addWidget(QLabel("Template Name *"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Code Reviewer")
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)

        # Description
        desc_layout = QVBoxLayout()
        desc_layout.setSpacing(4)
        desc_layout.addWidget(QLabel("Description"))
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText(
            "Brief description of this template's purpose"
        )
        desc_layout.addWidget(self.desc_input)
        layout.addLayout(desc_layout)

        # Content
        content_layout = QVBoxLayout()
        content_layout.setSpacing(4)
        content_layout.addWidget(QLabel("Prompt Content *"))
        self.content_input = QTextEdit()
        self.content_input.setPlaceholderText("You are an expert in...")
        content_layout.addWidget(self.content_input, stretch=1)
        layout.addLayout(content_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Save Template")
        self.btn_save.setObjectName("saveBtn")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.clicked.connect(self._on_save_clicked)
        btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

    def _load_existing_data(self):
        """Load dữ liệu template cũ vào fields."""
        from domain.prompt.template_manager import get_template_info, load_template

        try:
            info = get_template_info(self.template_id)
            content = load_template(self.template_id)

            self.name_input.setText(info.display_name)
            self.desc_input.setText(info.description)
            self.content_input.setPlainText(content)
            
            self.btn_save.setText("Update Template")
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", f"Không thể load dữ liệu template: {e}")

    def _generate_filename(self, name: str) -> str:
        """Sinh ten file tu ten template, tranh ki tu dac biet."""
        clean_name = re.sub(r"[^a-zA-Z0-9\s-]", "", name).strip()
        filename = re.sub(r"[\s-]+", "_", clean_name).lower()
        if not filename:
            filename = "custom_template"
        return f"{filename}.md"

    def _on_save_clicked(self):
        name = self.name_input.text().strip()
        desc = self.desc_input.text().strip()
        content = self.content_input.toPlainText().strip()

        if not name or not content:
            QMessageBox.warning(
                self, "Lỗi", "Vui lòng nhập đầy đủ Tên và Nội dung cho Template."
            )
            return

        filename = self._generate_filename(name)
        new_template_id = filename.replace(".md", "")
        file_path = CUSTOM_TEMPLATES_DIR / filename

        # Kiem tra trung lap: Neu la create moi hoac edit sang ten moi ma trung file da co
        if file_path.exists() and (not self.template_id or self.template_id != new_template_id):
            reply = QMessageBox.question(
                self,
                "Ghi đè",
                f"Template '{filename}' đã tồn tại.\nBạn có muốn ghi đè lên template hiện có không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # Ghi file theo format cua LocalCustomTemplateProvider
        frontmatter = f"<!-- name: {name}, desc: {desc} -->\n"
        full_content = frontmatter + content

        try:
            # Dam bao thu muc ton tai
            os.makedirs(CUSTOM_TEMPLATES_DIR, exist_ok=True)
            
            # Ghi file moi/update truoc
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(full_content)
                
            # Neu dang edit va doi ten (dan den doi filename) thanh cong -> xoa file cu
            if self.template_id and self.template_id != new_template_id:
                old_path = CUSTOM_TEMPLATES_DIR / f"{self.template_id}.md"
                if old_path.exists():
                    try:
                        old_path.unlink()
                    except OSError:
                        # Neu khong xoa duoc file cu cung khong block user, chi log lai
                        pass

            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self, "Lỗi lưu file", f"Đã xảy ra lỗi khi lưu Template: {str(e)}"
            )
