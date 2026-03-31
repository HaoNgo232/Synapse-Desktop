from unittest.mock import MagicMock
from pathlib import Path
from application.services.prompt_build_service import PromptBuildService
from domain.relationships.port import IRelationshipGraphProvider


def test_ensure_built_not_called_when_semantic_index_disabled():
    """
    Kiểm tra lỗi: ensure_built vẫn bị gọi ngay khi semantic_index đã tắt (toggle OFF).
    Mục đích: Nếu người dùng tắt Semantic Index, hệ thống không được phí tài nguyên xây dựng đồ thị.
    """
    # Mock GraphService
    mock_graph_service = MagicMock(spec=IRelationshipGraphProvider)

    # Khởi tạo PromptBuildService với mock
    service = PromptBuildService(graph_service=mock_graph_service)

    workspace = Path("/tmp/fake_workspace")
    file_paths = [workspace / "main.py"]

    # 1. Chạy với semantic_index=False
    # Chúng ta kỳ vọng mock_graph_service.ensure_built KHÔNG được gọi.
    service.build_prompt_full(
        file_paths=file_paths,
        workspace=workspace,
        instructions="Analyze this",
        output_format="xml",
        include_git_changes=False,
        use_relative_paths=True,
        semantic_index=False,  # Đã TẮT toggle
    )

    # Kiểm tra xem ensure_built có bị gọi không
    # Nếu bug tồn tại, nó sẽ bị gọi 1 lần (hoặc nhiều hơn)
    assert not mock_graph_service.ensure_built.called, (
        "Lỗi: ensure_built vẫn bị gọi mặc dù semantic_index=False"
    )


def test_ensure_built_called_when_semantic_index_enabled():
    """
    Kiểm tra xem ensure_built CÓ được gọi khi semantic_index đã bật (toggle ON).
    """
    mock_graph_service = MagicMock(spec=IRelationshipGraphProvider)
    service = PromptBuildService(graph_service=mock_graph_service)

    workspace = Path("/tmp/fake_workspace")
    file_paths = [workspace / "main.py"]

    # Chạy với semantic_index=True
    service.build_prompt_full(
        file_paths=file_paths,
        workspace=workspace,
        instructions="Analyze this",
        output_format="xml",
        include_git_changes=False,
        use_relative_paths=True,
        semantic_index=True,  # Đã BẬT toggle
    )

    # Kỳ vọng ensure_built PHẢI được gọi
    assert mock_graph_service.ensure_built.called, (
        "Lỗi: ensure_built không được gọi khi semantic_index=True"
    )
