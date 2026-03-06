"""DEPRECATED: Module da chuyen sang domain.prompt.file_collector

Bridge file - import module moi va alias vao sys.modules tai vi tri cu.
Tat ca code import tu 'core.prompting.file_collector' se duoc redirect tu dong.
"""

import importlib
import sys

# Import module moi
_mod = importlib.import_module("domain.prompt.file_collector")

# Alias tat ca symbols tu module moi vao namespace hien tai
# De `from core.prompting.file_collector import X` van hoat dong
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)

# Dong thoi alias trong sys.modules de `import core.prompting.file_collector` cung hoat dong
sys.modules[__name__] = _mod
