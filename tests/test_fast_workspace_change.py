from unittest.mock import MagicMock
from pathlib import Path


def test_semantic_index_is_disabled_and_fast():
    # Arrangement
    mock_graph_svc = MagicMock()
    mock_graph_svc.get_graph.return_value = None

    # Action
    from application.services.prompt_helpers import compute_semantic_index

    res = compute_semantic_index(Path("/fake/path"), mock_graph_svc)

    # Assert
    assert res == "", "Must return empty string for fast load"
    mock_graph_svc.ensure_built.assert_not_called()
