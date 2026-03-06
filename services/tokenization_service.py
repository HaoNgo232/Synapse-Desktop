"""DEPRECATED: Module da chuyen sang application.services.tokenization_service

Bridge file - redirect imports tu vi tri cu sang vi tri moi.
"""

import importlib
import sys

_mod = importlib.import_module("application.services.tokenization_service")

for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)

sys.modules[__name__] = _mod
