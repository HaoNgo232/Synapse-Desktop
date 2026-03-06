"""DEPRECATED: Da chuyen sang presentation.config.theme_qss"""

import importlib as _importlib

_mod = _importlib.import_module("presentation.config.theme_qss")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
