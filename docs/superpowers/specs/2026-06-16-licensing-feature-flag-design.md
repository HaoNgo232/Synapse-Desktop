# Licensing Feature Flag — Merge to Master with Toggle

## Problem & Context

Synapse Desktop has a fully implemented licensing system on the `feature/licensing-integration` branch (Ed25519 signature verification, activation dialog, settings panel). The licensing code is currently isolated from `master`, creating a diverging dual-branch maintenance burden.

The goal is to merge licensing into `master` as the single source of truth, while providing a simple mechanism to disable license checks during development and enable them only in production builds distributed via Gumroad.

## Decision: Environment Variable Feature Flag

Use `SYNAPSE_LICENSE_CHECK` environment variable to gate licensing enforcement at runtime.

| Context | Value | Behavior |
|---------|-------|----------|
| Development (`./start.sh`, `python main.py`) | Unset or `"0"` | License check skipped, app starts freely |
| Production build (AppImage, Windows EXE) | `"1"` | License check enforced, activation dialog shown if invalid |

### Why Environment Variable (not config file)?

- Consistent with existing `SYNAPSE_DEBUG` pattern already in the project
- Cannot be accidentally toggled by end users (embedded in AppRun/EXE launcher)
- No file to ship or manage separately
- Trivial to override for testing: `SYNAPSE_LICENSE_CHECK=1 python main.py`

## Proposed Changes

### 1. Merge `feature/licensing-integration` into `master`

Bring all licensing code into `master` as-is. No code deletions.

### 2. Gate license enforcement in `main.py`

#### [MODIFY] [main.py](file:///home/hao/Desktop/labs/Synapse-Desktop/main.py)

Wrap the boot license verification block (lines 91–104) with the feature flag check:

```python
# Boot verification — only when SYNAPSE_LICENSE_CHECK is enabled
# and --no-license CLI argument is not passed
if os.environ.get("SYNAPSE_LICENSE_CHECK") == "1" and "--no-license" not in sys.argv:
    from domain.ports.registry import DomainRegistry
    from infrastructure.persistence.settings_manager import load_app_settings

    settings = load_app_settings()
    license_service = DomainRegistry.license_service()
    license_info = license_service.verify_license_key(settings.license_key)

    if not license_info.is_valid:
        from presentation.widgets.license_dialog import LicenseActivationDialog

        dialog = LicenseActivationDialog()
        if dialog.exec() != LicenseActivationDialog.DialogCode.Accepted:
            sys.exit(0)
```

### 3. Gate licensing UI in Settings

#### [MODIFY] [settings_view_qt.py](file:///home/hao/Desktop/labs/Synapse-Desktop/presentation/views/settings/settings_view_qt.py)

Conditionally show the licensing status panel in settings only when `SYNAPSE_LICENSE_CHECK=1` and `--no-license` is not in `sys.argv`:

```python
import os
import sys

if os.environ.get("SYNAPSE_LICENSE_CHECK") == "1" and "--no-license" not in sys.argv:
    # ... build licensing card (existing code)
```

### 4. Set flag in production build scripts

#### [MODIFY] [build-appimage.sh](file:///home/hao/Desktop/labs/Synapse-Desktop/build-appimage.sh)

In the `AppRun` script (line 81–88), add the environment variable before exec:

```bash
cat > "$APPDIR/AppRun" << 'EOF'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${LD_LIBRARY_PATH}"
export SYNAPSE_LICENSE_CHECK=1
exec "${HERE}/usr/bin/Synapse-Desktop" "$@"
EOF
```

#### [MODIFY] [build-windows.ps1](file:///home/hao/Desktop/labs/Synapse-Desktop/build-windows.ps1)

Add `--runtime-hook` that sets the env var at EXE startup, or embed via PyInstaller spec file:

```python
# runtime_hook_license.py (new file, bundled by PyInstaller)
import os
os.environ["SYNAPSE_LICENSE_CHECK"] = "1"
```

Add to PyInstaller args:

```powershell
$pyinstallerArgs += @("--runtime-hook", "$SCRIPT_DIR\runtime_hook_license.py")
```

### 5. Dev script — explicit licensing OFF

#### [MODIFY] [start.sh](file:///home/hao/Desktop/labs/Synapse-Desktop/start.sh)

No changes needed (flag defaults to OFF when unset). Optionally add a comment for clarity:

```bash
# License check is OFF by default in dev mode.
# To test licensing: SYNAPSE_LICENSE_CHECK=1 python3 main.py
```

### 6. New file: Runtime hook for Windows EXE

#### [NEW] [runtime_hook_license.py](file:///home/hao/Desktop/labs/Synapse-Desktop/runtime_hook_license.py)

```python
"""PyInstaller runtime hook: Enable license check in production builds."""
import os
os.environ.setdefault("SYNAPSE_LICENSE_CHECK", "1")
```

## Files NOT Changed

All of these remain untouched — the flag only gates **calling points**, not the services themselves:

- `domain/licensing/entities.py` — LicenseInfo dataclass
- `domain/ports/license_service_port.py` — ILicenseService interface
- `domain/ports/registry.py` — DomainRegistry (license_service still registered)
- `infrastructure/adapters/license_service.py` — Ed25519LicenseService
- `presentation/widgets/license_dialog.py` — LicenseActivationDialog
- `presentation/service_container.py` — Still registers Ed25519LicenseService
- `tools/license_generator.py` — Dev tool for generating test keys
- `tests/test_licensing.py` — All licensing tests

## Developer Workflow

```
# Normal development — no licensing
./start.sh
# or
python main.py

# Test licensing flow
SYNAPSE_LICENSE_CHECK=1 python main.py

# Generate a test license key
python tools/license_generator.py

# Build production (licensing auto-enabled)
./build-appimage.sh          # Linux
.\build-windows.ps1 -OneFile  # Windows
```

## Verification Plan

### Automated Tests
```bash
# All existing licensing tests must pass
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_licensing.py -v

# All other tests unaffected
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v
```

### Manual Verification
1. Run `python main.py` — app starts without license dialog ✓
2. Run `SYNAPSE_LICENSE_CHECK=1 python main.py` — license dialog appears ✓
3. Activate with a valid key — app starts normally ✓
4. Open Settings with flag ON — licensing panel visible ✓
5. Open Settings with flag OFF — licensing panel hidden ✓
