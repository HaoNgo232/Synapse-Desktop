"""Forward bridge: re-export tu config.output_format"""

import importlib as _importlib

_mod = _importlib.import_module("config.output_format")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
