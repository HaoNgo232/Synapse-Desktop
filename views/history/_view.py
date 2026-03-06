"""DEPRECATED: Da chuyen sang presentation.views.history.view"""

import importlib as _importlib

_mod = _importlib.import_module("presentation.views.history.view")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
