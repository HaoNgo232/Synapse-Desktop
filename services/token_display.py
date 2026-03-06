"""DEPRECATED: Da chuyen sang infrastructure.adapters.token_display"""

import importlib as _importlib

_mod = _importlib.import_module("infrastructure.adapters.token_display")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
