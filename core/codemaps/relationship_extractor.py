"""DEPRECATED: Module da chuyen sang domain.codemap.relationship_extractor

Bridge file - import module moi va alias vao sys.modules tai vi tri cu.
Tat ca code import tu 'core.codemaps.relationship_extractor' se duoc redirect tu dong.
"""

import importlib
import sys

# Import module moi
_mod = importlib.import_module("domain.codemap.relationship_extractor")

# Alias tat ca symbols tu module moi vao namespace hien tai
# De `from core.codemaps.relationship_extractor import X` van hoat dong
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)

# Dong thoi alias trong sys.modules de `import core.codemaps.relationship_extractor` cung hoat dong
sys.modules[__name__] = _mod
