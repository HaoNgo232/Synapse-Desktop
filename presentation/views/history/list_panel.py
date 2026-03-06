"""Forward bridge: re-export tu views.history._list_panel"""

import importlib as _importlib

_mod = _importlib.import_module("views.history._list_panel")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
