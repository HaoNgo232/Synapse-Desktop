"""
Unit/Integration tests cho tính năng tự động trim context và định dạng compress trong PromptBuildService.

File này kiểm thử:
1. Trimming context khi số lượng token vượt quá giới hạn max_tokens.
2. Tạo prompt với định dạng output_format="compress" (Smart Context).
"""

from pathlib import Path
from typing import Set, Dict, List, Tuple
from unittest.mock import patch, MagicMock
import pytest

from application.services.prompt_build_service import PromptBuildService
from infrastructure.adapters.encoder_registry import get_tokenization_service
from infrastructure.filesystem.file_utils import TreeItem


class TestPromptTrimmingAndCompress:
    """Kiểm thử tính năng trim context và nén context của PromptBuildService."""

    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Path:
        """Tạo workspace giả lập cho test."""
        (tmp_path / "main.py").write_text("def run():\n    print('Hello World')\n" * 10, encoding="utf-8")
        (tmp_path / "utils.py").write_text("def format_msg(msg):\n    return f'[{msg}]'\n" * 10, encoding="utf-8")
        return tmp_path

    def test_prompt_context_trimming(self, workspace: Path) -> None:
        """Kiểm tra khi tổng tokens vượt quá max_tokens, prompt sẽ tự động trim và đính kèm notes."""
        tokenization_service = get_tokenization_service()
        service = PromptBuildService(tokenization_service=tokenization_service)

        file_paths: List[Path] = [workspace / "main.py", workspace / "utils.py"]

        # 1. Đếm token bình thường trước khi trim
        normal_result = service.build_prompt_full(
            file_paths=file_paths,
            workspace=workspace,
            instructions="Hãy phân tích code này và sửa lỗi",
            output_format="xml",
            include_git_changes=False,
            use_relative_paths=True,
        )
        assert normal_result.trimmed is False

        # 2. Đặt giới hạn max_tokens nhỏ hơn tổng số tokens
        max_limit: int = int(normal_result.total_tokens * 0.75)  # Chỉ lấy 75% số token

        trimmed_result = service.build_prompt_full(
            file_paths=file_paths,
            workspace=workspace,
            instructions="Hãy phân tích code này và sửa lỗi",
            output_format="xml",
            include_git_changes=False,
            use_relative_paths=True,
            max_tokens=max_limit,
        )

        # Trimmer hoạt động và thu hẹp context thành công
        assert trimmed_result.trimmed is True
        assert len(trimmed_result.trimmed_notes) > 0
        assert "<trimmed_context_notes>" in trimmed_result.prompt_text

    def test_smart_context_compress_format(self, workspace: Path) -> None:
        """Kiểm tra việc tạo prompt với định dạng nén (compress)."""
        tokenization_service = get_tokenization_service()
        service = PromptBuildService(tokenization_service=tokenization_service)

        file_paths: List[Path] = [workspace / "main.py"]

        result = service.build_prompt_full(
            file_paths=file_paths,
            workspace=workspace,
            instructions="Phân tích file main",
            output_format="compress",
            include_git_changes=False,
            use_relative_paths=True,
        )

        # Định dạng compress phải sinh ra cấu trúc XML có tag <smart_context>
        assert "<smart_context>" in result.prompt_text
        assert "main.py" in result.prompt_text
