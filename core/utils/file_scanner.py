"""DEPRECATED: Da chuyen sang infrastructure.filesystem.file_scanner"""

import importlib as _importlib

_mod = _importlib.import_module("infrastructure.filesystem.file_scanner")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
