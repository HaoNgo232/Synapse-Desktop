"""
File Panel Component.
Chứa nhãn "Files" và FileTreeWidget.
"""

from pathlib import Path
from typing import Optional, Set

from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget
from PySide6.QtCore import Signal

from presentation.config.theme import ThemeColors
from presentation.components.file_tree.file_tree_widget import FileTreeWidget
from domain.filesystem.ignore_engine import IgnoreEngine
from application.interfaces.tokenization_port import ITokenizationService


class FilePanel(QFrame):
    # Signals
    selection_changed = Signal(set)
    file_preview_requested = Signal(str)
    token_counting_done = Signal()
    exclude_patterns_changed = Signal()

    def __init__(
        self,
        ignore_engine: IgnoreEngine,
        tokenization_service: ITokenizationService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("class", "surface")
        self._ignore_engine = ignore_engine
        self._tokenization_service = tokenization_service
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 12)
        layout.setSpacing(6)

        # Header: "Files" title
        header = QHBoxLayout()
        header.setSpacing(6)

        files_label = QLabel("Files")
        files_label.setStyleSheet(
            f"font-weight: 700; font-size: 13px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        header.addWidget(files_label)
        header.addStretch()
        layout.addLayout(header)

        # File tree widget
        self.file_tree_widget = FileTreeWidget(
            ignore_engine=self._ignore_engine,
            tokenization_service=self._tokenization_service,
        )

        # Connect internal signals to exposed signals
        self.file_tree_widget.selection_changed.connect(self.selection_changed.emit)
        self.file_tree_widget.file_preview_requested.connect(
            self.file_preview_requested.emit
        )
        self.file_tree_widget.token_counting_done.connect(self.token_counting_done.emit)
        self.file_tree_widget.exclude_patterns_changed.connect(
            self.exclude_patterns_changed.emit
        )

        layout.addWidget(self.file_tree_widget, stretch=1)

    def load_tree(self, workspace_path: Path) -> None:
        self.file_tree_widget.load_tree(workspace_path)

    def get_selected_paths(self) -> Set[str]:
        return set(self.file_tree_widget.get_selected_paths())

    def get_all_selected_paths(self) -> Set[str]:
        return self.file_tree_widget.get_all_selected_paths()

    def set_selected_paths(self, paths: Set[str]) -> None:
        self.file_tree_widget.set_selected_paths(paths)

    def add_paths_to_selection(self, paths: Set[str]) -> int:
        return self.file_tree_widget.add_paths_to_selection(paths)

    def remove_paths_from_selection(self, paths: Set[str]) -> int:
        return self.file_tree_widget.remove_paths_from_selection(paths)

    def get_expanded_paths(self) -> list[str]:
        return self.file_tree_widget.get_expanded_paths()

    def set_expanded_paths(self, paths: list[str]) -> None:
        self.file_tree_widget.set_expanded_paths(set(paths))

    def get_total_tokens(self) -> int:
        return self.file_tree_widget.get_total_tokens()

    def cleanup(self) -> None:
        self.file_tree_widget.cleanup()
