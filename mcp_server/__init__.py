"""
MCP Server Package - Backward compatibility wrapper.

Code thuc da migrate sang infrastructure.mcp.*
"""

from infrastructure.mcp.config_installer import auto_update_installed_configs

__all__ = ["auto_update_installed_configs"]
