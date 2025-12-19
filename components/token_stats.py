"""
Token Stats Component - Hien thi thong ke tokens chi tiet

Port tu: /home/hao/Desktop/labs/overwrite/src/webview-ui/src/components/context-tab/token-stats.tsx
"""

import flet as ft
from dataclasses import dataclass
from typing import List, Optional

from core.theme import ThemeColors


@dataclass
class TokenStats:
    """Thong ke tokens chi tiet"""

    file_count: int = 0
    file_tokens: int = 0
    instruction_tokens: int = 0
    total_tokens: int = 0
    total_with_xml_tokens: int = 0


@dataclass
class SkippedFile:
    """File bi skip khi tinh tokens"""

    path: str
    reason: str  # 'binary', 'too-large', 'error'
    message: Optional[str] = None


class TokenStatsPanel:
    """
    Component hien thi thong ke tokens chi tiet.

    Hien thi:
    - So files duoc chon
    - File tokens (actual)
    - User instruction tokens
    - Total tokens (Copy Context)
    - Total tokens (Copy + OPX)
    - Skipped files (neu co)
    """

    def __init__(self):
        self.stats = TokenStats()
        self.skipped_files: List[SkippedFile] = []

        # UI elements
        self.container: Optional[ft.Container] = None
        self.file_count_text: Optional[ft.Text] = None
        self.file_tokens_text: Optional[ft.Text] = None
        self.instruction_tokens_text: Optional[ft.Text] = None
        self.total_tokens_text: Optional[ft.Text] = None
        self.total_xml_tokens_text: Optional[ft.Text] = None
        self.skipped_column: Optional[ft.Column] = None

    def build(self) -> ft.Container:
        """Build token stats panel UI"""

        self.file_count_text = ft.Text(
            "Selected files: 0", size=12, color=ThemeColors.TEXT_SECONDARY
        )
        self.file_tokens_text = ft.Text(
            "File tokens: 0", size=12, color=ThemeColors.TEXT_SECONDARY
        )
        self.instruction_tokens_text = ft.Text(
            "Instruction tokens: 0", size=12, color=ThemeColors.TEXT_SECONDARY
        )
        self.total_tokens_text = ft.Text(
            "Total (Copy): 0",
            size=12,
            weight=ft.FontWeight.W_500,
            color=ThemeColors.TEXT_PRIMARY,
        )
        self.total_xml_tokens_text = ft.Text(
            "Total (+ OPX): 0",
            size=12,
            weight=ft.FontWeight.W_500,
            color=ThemeColors.PRIMARY,
        )

        self.skipped_column = ft.Column(controls=[], spacing=4, visible=False)

        self.container = ft.Container(
            content=ft.Column(
                [
                    # Stats grid
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    self.file_count_text,
                                    self.file_tokens_text,
                                ],
                                spacing=4,
                                expand=True,
                            ),
                            ft.Column(
                                [
                                    self.instruction_tokens_text,
                                    self.total_tokens_text,
                                ],
                                spacing=4,
                                expand=True,
                            ),
                            ft.Column(
                                [
                                    self.total_xml_tokens_text,
                                ],
                                spacing=4,
                            ),
                        ],
                        spacing=16,
                    ),
                    # Skipped files warning
                    self.skipped_column,
                ],
                spacing=8,
            ),
            padding=12,
            bgcolor=ThemeColors.BG_ELEVATED,
            border=ft.border.all(1, ThemeColors.BORDER),
            border_radius=6,
        )

        return self.container

    def update_stats(
        self,
        file_count: int,
        file_tokens: int,
        instruction_tokens: int,
        xml_overhead: int = 150,  # OPX instructions tokens
    ):
        """
        Update token stats.

        Args:
            file_count: So files duoc chon
            file_tokens: Tong tokens cua files
            instruction_tokens: Tokens cua user instructions
            xml_overhead: Tokens cua OPX XML instructions (default 150)
        """
        self.stats = TokenStats(
            file_count=file_count,
            file_tokens=file_tokens,
            instruction_tokens=instruction_tokens,
            total_tokens=file_tokens + instruction_tokens,
            total_with_xml_tokens=file_tokens + instruction_tokens + xml_overhead,
        )

        self._refresh_ui()

    def set_skipped_files(self, skipped: List[SkippedFile]):
        """Set danh sach files bi skip"""
        self.skipped_files = skipped
        self._refresh_skipped_ui()

    def _refresh_ui(self):
        """Refresh stats display"""
        assert self.file_count_text is not None
        assert self.file_tokens_text is not None
        assert self.instruction_tokens_text is not None
        assert self.total_tokens_text is not None
        assert self.total_xml_tokens_text is not None

        self.file_count_text.value = f"Selected files: {self.stats.file_count}"
        self.file_tokens_text.value = f"File tokens: {self.stats.file_tokens:,}"
        self.instruction_tokens_text.value = (
            f"Instruction tokens: {self.stats.instruction_tokens:,}"
        )
        self.total_tokens_text.value = f"Total (Copy): {self.stats.total_tokens:,}"
        self.total_xml_tokens_text.value = (
            f"Total (+ OPX): {self.stats.total_with_xml_tokens:,}"
        )

    def _refresh_skipped_ui(self):
        """Refresh skipped files display"""
        if not self.skipped_column:
            return

        self.skipped_column.controls.clear()

        if not self.skipped_files:
            self.skipped_column.visible = False
            return

        self.skipped_column.visible = True

        # Header
        self.skipped_column.controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.WARNING_AMBER, size=14, color=ThemeColors.WARNING
                        ),
                        ft.Text(
                            f"Skipped Files ({len(self.skipped_files)})",
                            size=11,
                            weight=ft.FontWeight.W_600,
                            color=ThemeColors.WARNING,
                        ),
                    ],
                    spacing=4,
                ),
                margin=ft.margin.only(top=8),
            )
        )

        # File list
        for file in self.skipped_files[:5]:  # Max 5 files
            reason_text = {
                "binary": "Binary file",
                "too-large": "Too large",
                "error": "Error",
            }.get(file.reason, file.reason)

            self.skipped_column.controls.append(
                ft.Text(
                    f"  {file.path.split('/')[-1]} - {reason_text}",
                    size=10,
                    color=ThemeColors.TEXT_MUTED,
                    italic=True,
                )
            )

        if len(self.skipped_files) > 5:
            self.skipped_column.controls.append(
                ft.Text(
                    f"  ... and {len(self.skipped_files) - 5} more",
                    size=10,
                    color=ThemeColors.TEXT_MUTED,
                    italic=True,
                )
            )
