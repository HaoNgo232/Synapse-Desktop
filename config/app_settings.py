"""DEPRECATED: Da chuyen sang presentation.config.app_settings"""

import importlib as _importlib

_mod = _importlib.import_module("presentation.config.app_settings")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
