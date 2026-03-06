"""Forward bridge: re-export tu core.theme"""

import importlib as _importlib

_mod = _importlib.import_module("core.theme")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
