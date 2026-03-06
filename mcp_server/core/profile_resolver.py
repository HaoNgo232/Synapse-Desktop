"""DEPRECATED: Da chuyen sang infrastructure.mcp.core.profile_resolver"""
import importlib as _importlib

_mod = _importlib.import_module("infrastructure.mcp.core.profile_resolver")
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
