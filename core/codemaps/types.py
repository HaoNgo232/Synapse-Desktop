"""DEPRECATED: Module da chuyen sang domain.codemap.types

Bridge file - import module moi va alias vao sys.modules tai vi tri cu.
Tat ca code import tu 'core.codemaps.types' se duoc redirect tu dong.
"""

import importlib
import sys

# Import module moi
_mod = importlib.import_module("domain.codemap.types")

# Alias tat ca symbols tu module moi vao namespace hien tai
# De `from core.codemaps.types import X` van hoat dong
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)

# Dong thoi alias trong sys.modules de `import core.codemaps.types` cung hoat dong
sys.modules[__name__] = _mod
