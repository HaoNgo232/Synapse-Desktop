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
            # Use UTC to prevent local clock spoofing where possible
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
