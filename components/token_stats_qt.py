"""DEPRECATED: Da chuyen sang presentation.components.token_stats_qt"""

import importlib as _importlib

_mod = _importlib.import_module("presentation.components.token_stats_qt")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
