"""DEPRECATED: Da chuyen sang presentation.components.file_tree.file_tree_filter"""

import importlib as _importlib

_mod = _importlib.import_module("presentation.components.file_tree.file_tree_filter")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
