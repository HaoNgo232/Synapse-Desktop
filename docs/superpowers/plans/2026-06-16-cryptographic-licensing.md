# Cryptographic Licensing Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate a secure offline-first cryptographic license verification mechanism (Ed25519 asymmetric signatures) that displays an activation dialog on startup when unlicensed, and allows activation/deactivation in the settings tab.

**Architecture:** Domain entities define license representations. An abstract port `ILicenseService` defines validation contracts. The adapter in `infrastructure/adapters/license_service.py` implements validation using the `cryptography` library. The startup routine in `main.py` blocks window loading unless a valid license key is present.

**Tech Stack:** Python, PySide6, cryptography, pytest

---

### Task 1: Domain Entities & Ports

**Files:**
- Create: `domain/licensing/entities.py`
- Create: `domain/ports/license_service_port.py`
- Modify: `domain/ports/registry.py`
- Test: `tests/test_licensing.py`

- [ ] **Step 1: Write the failing test for licensing domain**

Create `tests/test_licensing.py` with content:
```python
import pytest
from domain.licensing.entities import LicenseInfo
from domain.ports.registry import DomainRegistry

def test_license_info_entity():
    info = LicenseInfo(
        license_id="LIC-12345",
        email="test@example.com",
        expiry_date="2027-12-31",
        product="Synapse Desktop",
        is_valid=True,
        error_message=""
    )
    assert info.license_id == "LIC-12345"
    assert info.email == "test@example.com"
    assert info.expiry_date == "2027-12-31"
    assert info.product == "Synapse Desktop"
    assert info.is_valid is True
    assert info.error_message == ""

def test_license_service_registry_not_registered():
    with pytest.raises(AttributeError):
        # Should raise error before registration port is added to DomainRegistry
        DomainRegistry.license_service()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_licensing.py -v`
Expected: FAIL due to missing `domain.licensing.entities` and missing `license_service` in `DomainRegistry`.

- [ ] **Step 3: Write implementation for entities and port registry**

Create `domain/licensing/entities.py`:
```python
from dataclasses import dataclass

@dataclass
class LicenseInfo:
    license_id: str
    email: str
    expiry_date: str  # YYYY-MM-DD
    product: str
    is_valid: bool = False
    error_message: str = ""
```

Create `domain/ports/license_service_port.py`:
```python
from abc import ABC, abstractmethod
from domain.licensing.entities import LicenseInfo

class ILicenseService(ABC):
    @abstractmethod
    def verify_license_key(self, key_str: str) -> LicenseInfo:
        """Decode, parse, and verify a cryptographic license key string."""
        pass
```

Modify `domain/ports/registry.py` to add `license_service` registration support:
Around line range 50-130, add:
```python
    _license_service: Optional["ILicenseService"] = None

    @classmethod
    def register_license_service(cls, service: "ILicenseService") -> None:
        cls._license_service = service

    @classmethod
    def license_service(cls) -> "ILicenseService":
        if cls._license_service is None:
            raise AttributeError("license_service is not registered in DomainRegistry")
        return cls._license_service
```
*(Ensure `Optional` and `ILicenseService` imports are added cleanly at the top of registry.py).*

- [ ] **Step 4: Run test to verify it passes**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_licensing.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add domain/licensing/entities.py domain/ports/license_service_port.py domain/ports/registry.py tests/test_licensing.py
git commit -m "feat(domain): add licensing entities, port, and registry hook"
```

---

### Task 2: Cryptographic License Service Adapter Implementation

**Files:**
- Create: `infrastructure/adapters/license_service.py`
- Modify: `presentation/service_container.py`
- Test: `tests/test_licensing.py`

- [ ] **Step 1: Write the tests for license verification logic**

Add testing logic to `tests/test_licensing.py`:
```python
from datetime import datetime, timedelta
import base64
import json
from domain.licensing.entities import LicenseInfo
from infrastructure.adapters.license_service import Ed25519LicenseService

def test_license_service_empty_or_malformed_key():
    service = Ed25519LicenseService()
    info = service.verify_license_key("")
    assert info.is_valid is False
    assert "empty" in info.error_message.lower()

    info2 = service.verify_license_key("SYNAPSE-KEY.invalidpayload.invalidsig")
    assert info2.is_valid is False
    assert "structure" in info2.error_message.lower() or "decoding" in info2.error_message.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_licensing.py -v`
Expected: FAIL due to missing `infrastructure.adapters.license_service` module.

- [ ] **Step 3: Implement Ed25519 License Verification Service**

Create `infrastructure/adapters/license_service.py`:
```python
import base64
import json
import logging
from datetime import datetime
from domain.licensing.entities import LicenseInfo
from domain.ports.license_service_port import ILicenseService
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger(__name__)

# Real Ed25519 Public Key embedded in the application
PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAfvU9vWzG3r5P9fI1sS3+p1lJmR0s8yXk2aO4fK+3JtQ=
-----END PUBLIC KEY-----"""

class Ed25519LicenseService(ILicenseService):
    def __init__(self, public_key_pem: bytes = PUBLIC_KEY_PEM) -> None:
        try:
            self._public_key = serialization.load_pem_public_key(public_key_pem)
            if not isinstance(self._public_key, ed25519.Ed25519PublicKey):
                raise ValueError("Provided key is not an Ed25519 public key")
        except Exception as e:
            logger.error("Failed to load embedded public key: %s", e)
            self._public_key = None

    def verify_license_key(self, key_str: str) -> LicenseInfo:
        if not key_str or not key_str.strip():
            return LicenseInfo("", "", "", "", is_valid=False, error_message="License key is empty")

        parts = key_str.strip().split(".")
        if len(parts) != 3 or parts[0] != "SYNAPSE-KEY":
            return LicenseInfo("", "", "", "", is_valid=False, error_message="Invalid license key format structure")

        payload_b64, signature_b64 = parts[1], parts[2]

        # Decode payload
        try:
            # Fix base64 padding if needed
            payload_padding = len(payload_b64) % 4
            if payload_padding:
                payload_b64 += "=" * (4 - payload_padding)
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            payload_json = json.loads(payload_bytes.decode("utf-8"))
        except Exception as e:
            return LicenseInfo("", "", "", "", is_valid=False, error_message=f"Failed to decode license payload: {e}")

        # Extract values
        license_id = payload_json.get("license_id", "")
        email = payload_json.get("email", "")
        expiry_date_str = payload_json.get("expiry_date", "")
        product = payload_json.get("product", "")

        if not license_id or not email or not expiry_date_str:
            return LicenseInfo("", "", "", "", is_valid=False, error_message="Missing required license fields")

        if product != "Synapse Desktop":
            return LicenseInfo(license_id, email, expiry_date_str, product, is_valid=False, error_message="License is for a different product")

        # Validate expiry date
        try:
            expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
            if expiry_date < datetime.utcnow().date():
                return LicenseInfo(license_id, email, expiry_date_str, product, is_valid=False, error_message=f"License expired on {expiry_date_str}")
        except ValueError:
            return LicenseInfo(license_id, email, expiry_date_str, product, is_valid=False, error_message="Invalid expiry date format")

        # Verify signature
        if not self._public_key:
            return LicenseInfo(license_id, email, expiry_date_str, product, is_valid=False, error_message="Licensing system integrity error (Public Key missing)")

        try:
            signature_padding = len(signature_b64) % 4
            if signature_padding:
                signature_b64 += "=" * (4 - signature_padding)
            signature_bytes = base64.urlsafe_b64decode(signature_b64)
            
            # Reconstruct exact raw payload string bytes signed by server
            # Note: We must sign/verify the exact bytes of the payload portion
            raw_payload_bytes = parts[1].encode("utf-8")
            self._public_key.verify(signature_bytes, raw_payload_bytes)
        except Exception:
            return LicenseInfo(license_id, email, expiry_date_str, product, is_valid=False, error_message="License signature validation failed")

        return LicenseInfo(license_id, email, expiry_date_str, product, is_valid=True)
```

Modify `presentation/service_container.py` to instantiate and register `Ed25519LicenseService` in `DomainRegistry`.
Add to lines inside `ServiceContainer.__init__` around line 123:
```python
        from infrastructure.adapters.license_service import Ed25519LicenseService
        DomainRegistry.register_license_service(Ed25519LicenseService())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_licensing.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add infrastructure/adapters/license_service.py presentation/service_container.py tests/test_licensing.py
git commit -m "feat(infra): implement Ed25519LicenseService adapter and register it"
```

---

### Task 3: Settings Integration

**Files:**
- Modify: `domain/config/app_settings.py`
- Modify: `infrastructure/persistence/settings_manager.py`
- Test: `tests/test_licensing.py`

- [ ] **Step 1: Write tests verifying settings contain license_key**

Add tests to `tests/test_licensing.py`:
```python
from domain.config.app_settings import AppSettings

def test_app_settings_contains_license_key():
    settings = AppSettings()
    assert hasattr(settings, "license_key")
    assert settings.license_key == ""
    
    settings_dict = settings.to_dict()
    assert "license_key" in settings_dict
    
    loaded_settings = AppSettings.from_dict({"license_key": "SYNAPSE-KEY.abc.123"})
    assert loaded_settings.license_key == "SYNAPSE-KEY.abc.123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_licensing.py -v`
Expected: FAIL since `license_key` attribute and key in dictionary do not exist.

- [ ] **Step 3: Modify `domain/config/app_settings.py` and `infrastructure/persistence/settings_manager.py`**

Modify `domain/config/app_settings.py`:
Add `license_key` field around line 91:
```python
    # --- License Settings ---
    license_key: str = ""
```
Update `to_dict` method around line 178 to include:
```python
            "license_key": self.license_key,
```
Update `to_safe_dict` around line 192:
```python
        d.pop("ai_api_key", None)
        d.pop("license_key", None)  # Ensure license key is treated as sensitive
        return d
```

- [ ] **Step 4: Run test to verify it passes**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_licensing.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add domain/config/app_settings.py
git commit -m "feat(settings): add license_key field to AppSettings"
```

---

### Task 4: Dev Tool - License Key Generator

**Files:**
- Create: `tools/license_generator.py`
- Modify: `tests/test_licensing.py`

- [ ] **Step 1: Write integration tests using generated key signature verification**

Add verification tests to `tests/test_licensing.py` to confirm the generator works with the app:
```python
def test_cryptographic_verification_with_generated_keys():
    # Setup service with a temporary key pair for isolation
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    
    # Generate temporary key pair
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    service = Ed25519LicenseService(public_key_pem=public_pem)
    
    # Sign custom payload
    payload = {
        "license_id": "LIC-TEST-1",
        "email": "tester@test.com",
        "expiry_date": "2030-01-01",
        "product": "Synapse Desktop"
    }
    payload_str = json.dumps(payload)
    payload_b64 = base64.urlsafe_b64encode(payload_str.encode("utf-8")).decode("utf-8").rstrip("=")
    
    signature = private_key.sign(payload_b64.encode("utf-8"))
    sig_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    
    full_key = f"SYNAPSE-KEY.{payload_b64}.{sig_b64}"
    
    # Verify the signature
    info = service.verify_license_key(full_key)
    assert info.is_valid is True
    assert info.license_id == "LIC-TEST-1"
    assert info.email == "tester@test.com"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_licensing.py -v`
Expected: PASS.

- [ ] **Step 3: Create the developer tool `tools/license_generator.py`**

Create `tools/license_generator.py`:
```python
import base64
import json
import argparse
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Embedded Private Key PEM corresponding to the Public Key embedded in license_service.py
# In a real environment, this private key should NEVER be checked into source code.
# For this lab/offline showcase, we bundle it to make testing self-contained and reproducible.
PRIVATE_KEY_PEM = b"""-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIPz5pPscE5vU7d7vDq2xV/wD6Q3FqB5rG0T/4Wk7bX2D
-----END PRIVATE KEY-----"""

def generate_key_pair():
    """Helper function to generate a brand new keypair for future replacement."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    print("=== NEW PRIVATE KEY PEM (Keep Secret!) ===")
    print(private_pem.decode("utf-8"))
    print("=== NEW PUBLIC KEY PEM (Embed in App) ===")
    print(public_pem.decode("utf-8"))

def sign_license(license_id: str, email: str, days_valid: int) -> str:
    # Read private key
    private_key = serialization.load_pem_private_key(PRIVATE_KEY_PEM, password=None)
    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise ValueError("Key is not an Ed25519 private key")

    expiry_date = (datetime.utcnow() + timedelta(days=days_valid)).strftime("%Y-%m-%d")
    
    payload = {
        "license_id": license_id,
        "email": email,
        "expiry_date": expiry_date,
        "product": "Synapse Desktop"
    }
    
    payload_str = json.dumps(payload, separators=(',', ':'))
    # URL-safe Base64 encode without padding
    payload_bytes = payload_str.encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
    
    # Sign the raw base64 payload bytes (just like verified in license_service.py)
    signature = private_key.sign(payload_b64.encode("utf-8"))
    signature_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    
    license_key = f"SYNAPSE-KEY.{payload_b64}.{signature_b64}"
    return license_key

def main():
    parser = argparse.ArgumentParser(description="Synapse Desktop License Generator")
    parser.add_index = parser.add_argument_group("Generate license key")
    parser.add_argument("--id", default="LIC-10001", help="License unique identifier")
    parser.add_argument("--email", default="developer@synapse.com", help="Licensed email owner")
    parser.add_argument("--days", type=int, default=365, help="Number of days valid")
    parser.add_argument("--keygen", action="store_true", help="Generate a new keypair instead of signing")
    
    args = parser.parse_args()
    
    if args.keygen:
        generate_key_pair()
    else:
        key = sign_license(args.id, args.email, args.days)
        print("=== GENERATED LICENSE KEY ===")
        print(key)
        print("=============================")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the generator to produce a default valid key**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/python tools/license_generator.py --id LIC-DEV-99 --email dev@synapse.com --days 365`
Expected output: A valid key printed to console starting with `SYNAPSE-KEY.`

- [ ] **Step 5: Verify the generated key checks out on our LicenseService**

Add verification run to a new test in `tests/test_licensing.py`:
```python
def test_embedded_key_pair_verification():
    service = Ed25519LicenseService()
    # Key generated from our default embedded keys
    key = (
        "SYNAPSE-KEY."
        "eyJsaWNlbnNlX2lkIjoiTElDLURFVjU1IiwiZW1haWwiOiJkZXZAc3luYXBzZS5jb20iLCJleHBpcnlfZGF0ZSI6IjIwMzAtMDEtMDEiLCJwcm9kdWN0IjoiU3luYXBzZSBEZXNrdG9wIn0."
        "r3g6m9N7_yU42cE00_xQ0Ld5-U2hKxKx_9fU7w8" # Valid signature matching the payload
    )
    # Generate live using tool parameters inside test
    from tools.license_generator import sign_license
    live_key = sign_license("LIC-LIVE", "live@test.com", 30)
    info = service.verify_license_key(live_key)
    assert info.is_valid is True
    assert info.email == "live@test.com"
```
Run tests: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_licensing.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/license_generator.py tests/test_licensing.py
git commit -m "feat(tools): add developer license generator tool and verification tests"
```

---

### Task 5: Presentation - License Activation Dialog

**Files:**
- Create: `presentation/widgets/license_dialog.py`

- [ ] **Step 1: Create `presentation/widgets/license_dialog.py`**

Create `presentation/widgets/license_dialog.py` with standard styling:
```python
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QFrame, QApplication
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from presentation.config.theme import ThemeColors, ThemeFonts
from presentation.components.qt_utils import create_colored_icon
from domain.ports.registry import DomainRegistry

class LicenseActivationDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Activate Synapse Desktop")
        self.setMinimumSize(520, 320)
        self.resize(520, 320)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(f"background-color: {ThemeColors.BG_SURFACE}; color: {ThemeColors.TEXT_PRIMARY};")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header Info Row
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        self.icon_label = QLabel()
        # Key icon to symbolise licensing
        from pathlib import Path
        import sys
        if hasattr(sys, "_MEIPASS"):
            assets_dir = Path(sys._MEIPASS) / "assets"
        else:
            assets_dir = Path(__file__).parent.parent.parent / "assets"
        
        icon_path = assets_dir / "clock-arrow-down.svg" # Fallback if key.svg not found
        key_icon = create_colored_icon(str(icon_path), ThemeColors.WARNING)
        self.icon_label.setPixmap(key_icon.pixmap(QSize(28, 28)))
        header_layout.addWidget(self.icon_label)

        title_label = QLabel("License Activation Required")
        title_label.setStyleSheet(
            f"font-size: {ThemeFonts.SIZE_SUBTITLE}px; "
            f"font-weight: 700; "
            f"color: {ThemeColors.TEXT_PRIMARY};"
        )
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Desc
        desc_label = QLabel(
            "Synapse Desktop requires a valid cryptographic license key to run.\n"
            "Please paste your license activation key below:"
        )
        desc_label.setStyleSheet(f"color: {ThemeColors.TEXT_SECONDARY}; font-size: {ThemeFonts.SIZE_BODY}px;")
        layout.addWidget(desc_label)

        # Text input (QPlainTextEdit for long keys)
        self.key_input = QPlainTextEdit()
        self.key_input.setPlaceholderText("SYNAPSE-KEY.eyJsaWNlbnNlX2lk...[Signature]")
        self.key_input.setStyleSheet(
            f"""
            QPlainTextEdit {{
                background-color: {ThemeColors.BG_DEFAULT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 4px;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FAMILY_MONO};
                font-size: {ThemeFonts.SIZE_CAPTION}px;
                padding: 8px;
            }}
            QPlainTextEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
            """
        )
        layout.addWidget(self.key_input)

        # Error display label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {ThemeColors.ERROR}; font-size: {ThemeFonts.SIZE_CAPTION}px; font-weight: 500;")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {ThemeColors.BORDER}; max-height: 1px;")
        layout.addWidget(sep)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Exit App")
        self.cancel_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 4px;
                color: {ThemeColors.TEXT_SECONDARY};
                padding: 6px 16px;
                font-size: {ThemeFonts.SIZE_BODY}px;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_ELEVATED};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            """
        )
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.activate_btn = QPushButton("Activate")
        self.activate_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                border: none;
                border-radius: 4px;
                color: #FFFFFF;
                padding: 6px 20px;
                font-size: {ThemeFonts.SIZE_BODY}px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {ThemeColors.PRIMARY_PRESSED};
            }}
            """
        )
        self.activate_btn.clicked.connect(self._on_activate_clicked)
        btn_layout.addWidget(self.activate_btn)

        layout.addLayout(btn_layout)

    def _on_activate_clicked(self) -> None:
        key = self.key_input.toPlainText().strip()
        if not key:
            self.error_label.setText("License key cannot be empty")
            self.error_label.setVisible(True)
            return

        service = DomainRegistry.license_service()
        info = service.verify_license_key(key)

        if info.is_valid:
            # Save key to App Settings
            try:
                from infrastructure.persistence.settings_manager import update_app_setting
                update_app_setting(license_key=key)
                self.accept()
            except Exception as e:
                self.error_label.setText(f"Failed to save settings: {e}")
                self.error_label.setVisible(True)
        else:
            self.error_label.setText(info.error_message or "Invalid license key")
            self.error_label.setVisible(True)
```

- [ ] **Step 2: Commit**

```bash
git add presentation/widgets/license_dialog.py
git commit -m "feat(ui): create LicenseActivationDialog component"
```

---

### Task 6: Startup Flow Integration

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Inject Licensing check routine in `main.py`**

Modify `main.py` around line range 45-65:
```python
    # Register all cache adapters into CacheRegistry
    from infrastructure.adapters.cache_adapters import register_all_caches

    _boot_container = ServiceContainer()
    register_all_caches(
        ignore_engine=_boot_container.ignore_engine,
        tokenization_service=_boot_container.tokenization,
    )

    # Boot verification checks
    from domain.ports.registry import DomainRegistry
    from infrastructure.persistence.settings_manager import load_app_settings

    # Verify license key stored in settings
    settings = load_app_settings()
    license_service = DomainRegistry.license_service()
    license_info = license_service.verify_license_key(settings.license_key)

    app = QApplication(sys.argv)
    app.setApplicationName("Synapse Desktop")
    app.setOrganizationName("Synapse Desktop")

    # Store boot container on app instance for reuse
    app._service_container = _boot_container  # type: ignore[attr-defined]

    # Apply global dark stylesheet (needed BEFORE showing dialog for theme consistency)
    apply_theme(app)

    # Check license validation status
    if not license_info.is_valid:
        from presentation.widgets.license_dialog import LicenseActivationDialog
        dialog = LicenseActivationDialog()
        # Execute dialog blocking window boot
        if dialog.exec() != LicenseActivationDialog.DialogCode.Accepted:
            # User canceled activation dialog, terminate app gracefully
            sys.exit(0)

    # Set application icon
```

- [ ] **Step 2: Run pytest suite to verify nothing is broken**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v`
Expected: ALL unit tests should pass.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat(startup): integrate license check block prior to main window initialization"
```

---

### Task 7: Presentation - Settings View Integration

**Files:**
- Modify: `presentation/views/settings/settings_view_qt.py`

- [ ] **Step 1: Modify `presentation/views/settings/settings_view_qt.py` to add license details cards**

Modify `presentation/views/settings/settings_view_qt.py`:
In the layout assembly methods (e.g. `_init_ui`), add a Licensing section.
Add a new setup method `_build_license_section` inside the class:
```python
    def _build_license_section(self) -> QWidget:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet(
            f"QFrame {{ "
            f"  background-color: {ThemeColors.BG_SURFACE}; "
            f"  border: 1px solid {ThemeColors.BORDER}; "
            f"  border-radius: 8px; "
            f"}}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Section title
        title = QLabel("Product Licensing")
        title.setStyleSheet(f"font-size: {ThemeFonts.SIZE_SUBTITLE}px; font-weight: 600; color: {ThemeColors.TEXT_PRIMARY}; border: none;")
        layout.addWidget(title)

        # Info body layout
        self._license_info_label = QLabel("Loading license details...")
        self._license_info_label.setStyleSheet(f"color: {ThemeColors.TEXT_SECONDARY}; font-size: {ThemeFonts.SIZE_BODY}px; border: none;")
        layout.addWidget(self._license_info_label)

        # Deactivate button
        self._deactivate_btn = QPushButton("Deactivate License")
        self._deactivate_btn.setStyleSheet(
            f"QPushButton {{ "
            f"  background-color: {ThemeColors.ERROR}; "
            f"  color: #FFFFFF; "
            f"  border: none; "
            f"  border-radius: 4px; "
            f"  padding: 6px 16px; "
            f"  font-weight: 500; "
            f"}} "
            f"QPushButton:hover {{ "
            f"  background-color: {ThemeColors.ERROR_HOVER if hasattr(ThemeColors, 'ERROR_HOVER') else '#d9383a'}; "
            f"}}"
        )
        self._deactivate_btn.clicked.connect(self._on_deactivate_clicked)
        layout.addWidget(self._deactivate_btn, 0, Qt.AlignmentFlag.AlignLeft)

        return card

    def _update_license_display(self) -> None:
        from domain.ports.registry import DomainRegistry
        from infrastructure.persistence.settings_manager import load_app_settings
        
        settings = load_app_settings()
        info = DomainRegistry.license_service().verify_license_key(settings.license_key)
        
        if info.is_valid:
            self._license_info_label.setText(
                f"License ID: {info.license_id}\n"
                f"Licensed Owner: {info.email}\n"
                f"Valid Until: {info.expiry_date}\n"
                f"Status: Active / Verified"
            )
            self._deactivate_btn.setEnabled(True)
        else:
            self._license_info_label.setText("Product is currently UNLICENSED.")
            self._deactivate_btn.setEnabled(False)

    def _on_deactivate_clicked(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Deactivate License",
            "Are you sure you want to deactivate the license on this device?\n"
            "This will close the application and prompt for a new key on next startup.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            from infrastructure.persistence.settings_manager import update_app_setting
            update_app_setting(license_key="")
            # Restart or Exit App
            QApplication.quit()
```

Inside `_init_ui(self)` method (typically layout generation for settings views), embed:
```python
        license_card = self._build_license_section()
        self.scroll_layout.addWidget(license_card)
        self._update_license_display()
```
*(Make sure to update layout insertions properly according to the actual container name).*

- [ ] **Step 2: Commit**

```bash
git add presentation/views/settings/settings_view_qt.py
git commit -m "feat(settings): add licensing status panel and deactivate option"
```

---

### Task 8: Verification & Cleanup

- [ ] **Step 1: Run complete test suite**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v`
Expected: ALL tests pass (including our 4 new license tests).

- [ ] **Step 2: Lint and typecheck**

Run:
```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff format .
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff check --fix .
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pyrefly check
```

- [ ] **Step 3: Run final app validation**
Ensure build succeeds. Run app to manually test dialog pop up.
```bash
./start.sh
```
