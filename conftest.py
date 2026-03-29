"""
conftest.py - Cấu hình pytest cho Synapse Desktop

Tự động thêm project root vào sys.path để pytest có thể import
các module local mà không cần set PYTHONPATH bên ngoài.
"""

import sys
from pathlib import Path

# Thêm project root vào sys.path nếu chưa có
_project_root = str(Path(__file__).parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
