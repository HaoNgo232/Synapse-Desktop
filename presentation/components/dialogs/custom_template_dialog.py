"""Forward bridge: re-export tu components.custom_template_dialog"""

import importlib as _importlib

_mod = _importlib.import_module("components.custom_template_dialog")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
