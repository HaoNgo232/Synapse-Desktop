from unittest.mock import MagicMock
from pathlib import Path
from application.services.prompt_build_service import PromptBuildService


def test_semantic_index_is_disabled_and_fast():
    # Arrangement
    mock_token_svc = MagicMock()
    mock_graph_svc = MagicMock()
    mock_graph_svc.get_graph.return_value = None

    svc = PromptBuildService(
        tokenization_service=mock_token_svc, graph_service=mock_graph_svc
    )

    # Action
    res = svc._compute_semantic_index(Path("/fake/path"))

    # Assert
    assert res == "", "Must return empty string for fast load"
    mock_graph_svc.ensure_built.assert_not_called()
