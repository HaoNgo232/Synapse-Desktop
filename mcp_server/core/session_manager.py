"""DEPRECATED: Da chuyen sang infrastructure.mcp.core.session_manager"""
import importlib as _importlib

_mod = _importlib.import_module("infrastructure.mcp.core.session_manager")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
