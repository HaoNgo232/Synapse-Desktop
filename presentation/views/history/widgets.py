"""Forward bridge: re-export tu views.history._widgets"""

import importlib as _importlib

_mod = _importlib.import_module("views.history._widgets")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
