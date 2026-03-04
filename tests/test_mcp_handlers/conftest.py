"""Pytest configuration for MCP handlers tests"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True)
def reset_cwd(monkeypatch):
    """Ensure CWD is not modified by tests"""
    import os

    original_cwd = os.getcwd()
    yield
    os.chdir(original_cwd)


@pytest.fixture(autouse=True)
def suppress_logging():
    """Suppress logging during tests"""
    import logging

    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)
