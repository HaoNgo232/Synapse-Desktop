"""
AppSettings - Backward compatibility shim.

File này đã được chuyển sang application/config/app_settings.py.
Import từ application/config/app_settings để tuân theo Clean Architecture.
"""

from application.config.app_settings import AppSettings

__all__ = ["AppSettings"]
