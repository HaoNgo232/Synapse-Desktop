"""Forward bridge: re-export tu mcp_server.handlers.workspace_handler

Cho phep import tu vi tri moi (Clean Architecture) trong khi code goc
van nam tai vi tri cu. Se duoc thay the bang code thuc khi migrate xong.
"""

import importlib as _importlib

_mod = _importlib.import_module("mcp_server.handlers.workspace_handler")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
