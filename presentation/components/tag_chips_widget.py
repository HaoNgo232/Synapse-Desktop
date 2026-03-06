"""Forward bridge: re-export tu components.tag_chips_widget"""

import importlib as _importlib

_mod = _importlib.import_module("components.tag_chips_widget")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
