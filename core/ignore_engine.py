"""DEPRECATED: Da chuyen sang infrastructure.filesystem.ignore_engine"""

import importlib as _importlib

_mod = _importlib.import_module("infrastructure.filesystem.ignore_engine")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
