"""Project root constant cho Synapse Desktop.

Dung de resolve paths den resources, templates, scripts, etc.
thay vi dung __file__ (de tranh phu thuoc vao vi tri file).
"""

from pathlib import Path

# Tim project root bang cach di len tu shared/constants/project.py
# shared/constants/project.py -> shared/constants/ -> shared/ -> PROJECT_ROOT
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
