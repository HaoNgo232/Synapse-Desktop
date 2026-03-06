"""DEPRECATED: Module da chuyen sang domain.workflow.code_reviewer

Bridge file - import module moi va alias vao sys.modules tai vi tri cu.
Tat ca code import tu 'core.workflows.code_reviewer' se duoc redirect tu dong.
"""

import importlib
import sys

# Import module moi
_mod = importlib.import_module("domain.workflow.code_reviewer")

# Alias tat ca symbols tu module moi vao namespace hien tai
# De `from core.workflows.code_reviewer import X` van hoat dong
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)

# Dong thoi alias trong sys.modules de `import core.workflows.code_reviewer` cung hoat dong
sys.modules[__name__] = _mod
