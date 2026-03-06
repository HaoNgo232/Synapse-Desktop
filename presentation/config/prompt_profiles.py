"""Forward bridge: re-export tu config.prompt_profiles"""

import importlib as _importlib

_mod = _importlib.import_module("config.prompt_profiles")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
