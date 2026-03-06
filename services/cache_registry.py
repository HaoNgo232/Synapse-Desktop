"""DEPRECATED: Da chuyen sang infrastructure.adapters.cache_registry"""

import importlib as _importlib

_mod = _importlib.import_module("infrastructure.adapters.cache_registry")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
