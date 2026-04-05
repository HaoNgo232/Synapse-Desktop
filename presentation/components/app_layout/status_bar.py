"""
StatusBar Component - Thanh trạng thái dưới cùng của ứng dụng.

Hiển thị: Workspace path, Git branch, Token count, Version.
"""

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QStatusBar, QLabel
from PySide6.QtCore import Qt

from presentation.config.theme import ThemeColors, ThemeFonts


class SynapseStatusBar(QStatusBar):
    """
    Status bar footer (28-32px).
    [Workspace path] — [Git branch] — [Token stats] — [Version]
    """

    def __init__(self, version: str, parent=None) -> None:
        super().__init__(parent)
        self.version = version
        self._build_ui()

    def _build_ui(self) -> None:
        """Khởi tạo giao diện các labels trong status bar."""
        # Workspace path
        self._status_workspace = QLabel("No workspace")
        self._status_workspace.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED}; "
            f"font-family: {ThemeFonts.FAMILY_MONO}; "
            f"font-size: {ThemeFonts.SIZE_CAPTION}px; "
            f"padding-left: 8px;"
        )
        self.addWidget(self._status_workspace, stretch=1)

        # Git branch
        self._status_git = QLabel("")
        self._status_git.setStyleSheet(
            f"color: {ThemeColors.TEXT_SECONDARY}; "
            f"font-family: {ThemeFonts.FAMILY_MONO}; "
            f"font-size: {ThemeFonts.SIZE_CAPTION}px; "
            f"padding-right: 12px;"
        )
        self.addWidget(self._status_git)
        self._status_git.setVisible(False)

        # Token summary (selected files + token total)
        self._status_tokens = QLabel("0 files | 0 tokens")
        self._status_tokens.setStyleSheet(
            f"color: {ThemeColors.TEXT_SECONDARY}; "
            f"font-family: {ThemeFonts.FAMILY_MONO}; "
            f"font-size: {ThemeFonts.SIZE_CAPTION}px; "
            f"padding-right: 12px;"
        )
        self._status_tokens.setToolTip("Selected files and estimated token total")
        self.addWidget(self._status_tokens)

        # Version
        version_label = QLabel(f"v{self.version}")
        version_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED}; "
            f"font-size: {ThemeFonts.SIZE_CAPTION}px; "
            f"padding-right: 8px;"
        )
        version_label.setToolTip("Synapse Desktop version")
        self.addPermanentWidget(version_label)

    def set_workspace(self, path: Optional[Path]) -> None:
        """Cập nhật hiển thị workspace path."""
        if path:
            self._status_workspace.setText(f"📁 {path}")
        else:
            self._status_workspace.setText("No workspace")

    def set_git_branch(self, branch: Optional[str]) -> None:
        """Cập nhật branch name hiện tại."""
        if branch:
            self._status_git.setText(f"⎇ {branch}")
            self._status_git.setVisible(True)
        else:
            self._status_git.setVisible(False)

    def set_token_stats(self, selected_count: int, total_tokens: int) -> None:
        """Cập nhật thông số token."""
        self._status_tokens.setText(f"{selected_count} files | {total_tokens:,} tokens")
