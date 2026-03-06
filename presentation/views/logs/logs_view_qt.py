"""Forward bridge: re-export tu views.logs_view_qt"""

import importlib as _importlib

_mod = _importlib.import_module("views.logs_view_qt")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
