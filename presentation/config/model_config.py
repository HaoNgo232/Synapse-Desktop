"""Forward bridge: re-export tu config.model_config"""

import importlib as _importlib

_mod = _importlib.import_module("config.model_config")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
