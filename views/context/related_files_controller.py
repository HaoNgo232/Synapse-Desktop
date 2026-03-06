"""DEPRECATED: Da chuyen sang presentation.views.context.related_files_controller"""

import importlib as _importlib

_mod = _importlib.import_module("presentation.views.context.related_files_controller")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
