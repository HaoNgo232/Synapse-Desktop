"""DEPRECATED: Module da chuyen sang domain.prompt.formatters.system_prompts

Bridge file - import module moi va alias vao sys.modules tai vi tri cu.
Tat ca code import tu 'core.prompting.formatters.system_prompts' se duoc redirect tu dong.
"""

import importlib
import sys

# Import module moi
_mod = importlib.import_module("domain.prompt.formatters.system_prompts")

# Alias tat ca symbols tu module moi vao namespace hien tai
# De `from core.prompting.formatters.system_prompts import X` van hoat dong
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)

# Dong thoi alias trong sys.modules de `import core.prompting.formatters.system_prompts` cung hoat dong
sys.modules[__name__] = _mod
