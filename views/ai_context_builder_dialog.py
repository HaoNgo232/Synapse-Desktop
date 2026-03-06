"""DEPRECATED: Da chuyen sang presentation.views.ai_context_builder_dialog"""

import importlib as _importlib

_mod = _importlib.import_module("presentation.views.ai_context_builder_dialog")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
