"""PyInstaller runtime hook: Enable license check in production builds."""
import os
os.environ.setdefault("SYNAPSE_LICENSE_CHECK", "1")
