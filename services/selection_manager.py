"""DEPRECATED: Module da chuyen sang domain.selection.manager

Bridge file - import module moi va alias vao sys.modules tai vi tri cu.
Tat ca code import tu 'services.selection_manager' se duoc redirect tu dong.
"""

import importlib
import sys

# Import module moi
_mod = importlib.import_module("domain.selection.manager")

# Alias tat ca symbols tu module moi vao namespace hien tai
# De `from services.selection_manager import X` van hoat dong
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)

# Dong thoi alias trong sys.modules de `import services.selection_manager` cung hoat dong
sys.modules[__name__] = _mod
