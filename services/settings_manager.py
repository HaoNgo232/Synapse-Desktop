"""DEPRECATED: Da chuyen sang infrastructure.persistence.settings_manager"""

import importlib as _importlib

_mod = _importlib.import_module("infrastructure.persistence.settings_manager")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
